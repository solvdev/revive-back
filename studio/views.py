# studio/views.py
# from math import ceil
import calendar
import re
import secrets
import time as pytime
import unicodedata
from calendar import monthrange
from collections import Counter
from datetime import date, datetime
from datetime import time as dtime
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import pandas as pd
import pytz
from accounts.models import Client
from accounts.serializers import ClientSerializer
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import localtime
from django.utils.timezone import now
from django.utils.timezone import now as tz_now
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from studio.alerts import get_clients_with_consecutive_no_shows

from .management.mails.mails import (
    send_booking_confirmation_email,
    send_individual_booking_pending_email,
    send_subscription_confirmation_email,
)
from .mixins import SedeFilterMixin
from .permissions import SedeAccessPermission, IsSedeOwnerOrReadOnly

# from .mixins import SedeFilterMixin, SedeValidationMixin
from .models import (
    Booking,
    BulkBooking,
    ClassType,
    TimeSlot,
    Membership,
    MonthlyRevenue,
    Payment,
    PlanIntent,
    Promotion,
    PromotionInstance,
    Schedule,
    Sede,
    TimeSlot,
    Venta,
)
from .serializers import (
    BookingAttendanceUpdateSerializer,
    BookingHistorialSerializer,
    BookingMiniSerializer,
    BookingSerializer,
    BulkBookingResultSerializer,
    BulkBookingSerializer,
    ClassTypeSerializer,
    MembershipSerializer,
    MonthlyRevenueSerializer,
    PaymentSerializer,
    PlanIntentSerializer,
    PromotionInstanceSerializer,
    PromotionSerializer,
    ScheduleSerializer,
    ScheduleWithBookingsSerializer,
    SedeSerializer,
    TimeSlotSerializer,
    VentaSerializer,
)
from .utils import recalculate_all_monthly_revenue, recalculate_monthly_revenue


# Función que verifica si el cliente tiene una membresía activa
def has_active_membership(client):
    # Verificamos si el cliente tiene un pago reciente con una membresía activa
    today = now().date()
    latest_payment = (
        Payment.objects.filter(
            client=client, 
            valid_from__lte=today,  # La vigencia ya empezó
            valid_until__gte=today   # Y aún no ha expirado
        )
        .order_by("-valid_until")  # Ordenar por vigencia más lejana
        .first()
    )
    return latest_payment is not None


@api_view(["GET"])
def clases_por_mes(request):
    """
    Devuelve resumen de clases válidas, no-shows y penalización sugerida por cliente en el mes.
    Solo penaliza los no-show sin causa justificada (sin cancellation_reason).
    OPTIMIZED VERSION: Uses single query with joins and aggregations.
    """

    year = int(request.query_params.get("year", now().year))
    month = int(request.query_params.get("month", now().month))

    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)

    # Get clients that have either:
    # 1. Active payments in the period, OR
    # 2. Classes in the period (even without active payments)
    clients_with_payments = Client.objects.filter(
        status="A", payment__valid_until__gte=first_day
    ).distinct()

    # Also get clients with classes in the period (even without payments)
    clients_with_classes = Client.objects.filter(
        status="A", booking__class_date__range=[first_day, last_day]
    ).distinct()

    # Combine both querysets
    all_clients = (clients_with_payments | clients_with_classes).distinct()

    # Apply sede filtering if sede_ids are provided
    if hasattr(request, "sede_ids") and request.sede_ids:
        print(f"🔍 CLASES_POR_MES: Aplicando filtro de sede: {request.sede_ids}")
        all_clients = all_clients.filter(sede_id__in=request.sede_ids)
        print(f"🔍 CLASES_POR_MES: Clientes después del filtro: {all_clients.count()}")
    else:
        print(
            f"🔍 CLASES_POR_MES: No hay filtro de sede aplicado. sede_ids: {getattr(request, 'sede_ids', 'NO EXISTE')}"
        )

    # Process each client with optimized queries
    clients_data = []
    for client in all_clients:
        # Get the most recent active payment for the period
        active_payment = (
            client.payment_set.filter(valid_until__gte=first_day)
            .select_related("membership")
            .order_by("-date_paid")
            .first()
        )

        # If no payment found, try to find any payment that was valid during the period
        if not active_payment:
            active_payment = (
                client.payment_set.filter(
                    valid_until__gte=first_day,
                    date_paid__lte=last_day
                    + timedelta(days=30),  # Allow payments made up to 30 days after
                )
                .select_related("membership")
                .order_by("-date_paid")
                .first()
            )

        # Count valid classes (attended + cancelled) - single query
        valid_classes = client.booking_set.filter(
            class_date__range=[first_day, last_day],
            attendance_status__in=["attended", "cancelled"],
        ).count()

        # Count no-show classes without justification - single query
        no_show_classes = (
            client.booking_set.filter(
                class_date__range=[first_day, last_day],
                attendance_status="no_show",
            )
            .filter(
                Q(cancellation_reason__isnull=True) | Q(cancellation_reason__exact="")
            )
            .count()
        )

        # Determine membership info based on payment status
        if active_payment:
            membership_name = active_payment.membership.name
            expected_classes = active_payment.membership.classes_per_month or 0
        else:
            # No active payment - check if client has trial available
            if not client.trial_used and valid_classes > 0:
                membership_name = "Clase de prueba gratuita"
                expected_classes = 1
            elif valid_classes > 0:
                membership_name = "Clases sin membresía activa"
                expected_classes = 0
            else:
                # Skip clients with no classes and no payment
                continue

        clients_data.append(
            {
                "id": client.id,
                "first_name": client.first_name,
                "last_name": client.last_name,
                "membership_name": membership_name,
                "expected_classes": expected_classes,
                "valid_classes": valid_classes,
                "no_show_classes": no_show_classes,
            }
        )

    # Process the data
    full_data = []
    for client_data in clients_data:
        # Get no-show dates separately (can't be done in the main query easily)
        no_show_dates = list(
            Booking.objects.filter(
                client_id=client_data["id"],
                class_date__range=[first_day, last_day],
                attendance_status="no_show",
            )
            .filter(
                Q(cancellation_reason__isnull=True) | Q(cancellation_reason__exact="")
            )
            .values_list("class_date", flat=True)
            .distinct()
        )

        penalizacion = client_data["no_show_classes"] * 35

        full_data.append(
            {
                "client_id": client_data["id"],
                "client_name": f"{client_data['first_name']} {client_data['last_name']}",
                "membership": client_data["membership_name"],
                "expected_classes": client_data["expected_classes"],
                "valid_classes": client_data["valid_classes"],
                "no_show_classes": client_data["no_show_classes"],
                "date_no_show": no_show_dates,
                "penalty": penalizacion,
            }
        )

    return Response(full_data)


@api_view(["GET"])
def get_daily_closing_summary(request):
    """
    Endpoint para obtener cierres contables diarios.
    Parámetros opcionales:
    - start_date: fecha de inicio (YYYY-MM-DD)
    - end_date: fecha de fin (YYYY-MM-DD)
    - date: fecha específica (YYYY-MM-DD)
    """

    # Obtener parámetros de fecha
    date_param = request.query_params.get("date")
    start_date_param = request.query_params.get("start_date")
    end_date_param = request.query_params.get("end_date")

    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            start_date = end_date = target_date
        except ValueError:
            return Response(
                {"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=400
            )
    elif start_date_param and end_date_param:
        try:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=400
            )
    else:
        # Por defecto, últimos 30 días
        end_date = localtime(now()).date()
        start_date = end_date - timedelta(days=30)

    # Generar lista de fechas
    current_date = start_date
    daily_closings = []

    while current_date <= end_date:
        # Obtener pagos del día
        pagos = Payment.objects.filter(date_paid__date=current_date)
        ventas = Venta.objects.filter(date_sold__date=current_date)
        bookings = Booking.objects.filter(class_date=current_date)

        # Calcular totales por método de pago
        efectivo = (
            pagos.filter(
                Q(payment_method__iexact="efectivo") | Q(payment_method__iexact="cash")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        transferencia = (
            pagos.filter(
                Q(payment_method__iexact="transferencia")
                | Q(payment_method__iexact="transfer")
                | Q(payment_method__iexact="deposito")
                | Q(payment_method__iexact="depósito")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        visalink = (
            pagos.filter(
                Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="card")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Calcular totales
        total_pagos = pagos.aggregate(Sum("amount"))["amount__sum"] or 0
        total_ventas = ventas.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        total_dia = total_pagos + total_ventas

        # Estadísticas de clases
        asistencias = bookings.filter(attendance_status="attended").count()
        no_shows = bookings.filter(attendance_status="no_show").count()
        clases_individuales = bookings.filter(schedule__is_individual=True).count()
        paquetes_vendidos = pagos.count()

        daily_closings.append(
            {
                "fecha": current_date.isoformat(),
                "dia_semana": current_date.strftime("%A"),
                "efectivo": float(efectivo),
                "transferencia": float(transferencia),
                "visalink": float(visalink),
                "total_pagos": float(total_pagos),
                "total_ventas": float(total_ventas),
                "total_dia": float(total_dia),
                "asistencias": asistencias,
                "no_shows": no_shows,
                "clases_individuales": clases_individuales,
                "paquetes_vendidos": paquetes_vendidos,
                "detalle_pagos": [
                    {
                        "cliente": pago.client.full_name,
                        "membresia": pago.membership.name,
                        "monto": float(pago.amount),
                        "metodo": pago.payment_method or "No especificado",
                        "observaciones": f"Pago #{pago.id}",
                    }
                    for pago in pagos.select_related("client", "membership")
                ],
            }
        )

        current_date += timedelta(days=1)

    return Response(
        {
            "periodo": {"inicio": start_date.isoformat(), "fin": end_date.isoformat()},
            "cierres_diarios": daily_closings,
            "resumen_periodo": {
                "total_efectivo": sum(c["efectivo"] for c in daily_closings),
                "total_transferencia": sum(c["transferencia"] for c in daily_closings),
                "total_visalink": sum(c["visalink"] for c in daily_closings),
                "total_general": sum(c["total_dia"] for c in daily_closings),
                "total_asistencias": sum(c["asistencias"] for c in daily_closings),
                "total_paquetes": sum(c["paquetes_vendidos"] for c in daily_closings),
            },
        }
    )


@api_view(["GET"])
def get_comprehensive_closing_summary(request):
    """
    Endpoint completo que devuelve cierres contables diarios y semanales.
    Parámetros opcionales:
    - start_date: fecha de inicio (YYYY-MM-DD)
    - end_date: fecha de fin (YYYY-MM-DD)
    - date: fecha específica (YYYY-MM-DD)
    - month: mes específico (YYYY-MM)
    - year: año específico
    """

    # Obtener parámetros de fecha
    date_param = request.query_params.get("date")
    start_date_param = request.query_params.get("start_date")
    end_date_param = request.query_params.get("end_date")
    month_param = request.query_params.get("month")
    year_param = request.query_params.get("year")

    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            start_date = end_date = target_date
        except ValueError:
            return Response(
                {"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=400
            )
    elif month_param:
        try:
            year, month = map(int, month_param.split("-"))
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        except ValueError:
            return Response(
                {"error": "Formato de mes inválido. Use YYYY-MM"}, status=400
            )
    elif year_param:
        try:
            year = int(year_param)
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        except ValueError:
            return Response({"error": "Año inválido"}, status=400)
    elif start_date_param and end_date_param:
        try:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=400
            )
    else:
        # Por defecto, últimos 30 días
        end_date = localtime(now()).date()
        start_date = end_date - timedelta(days=30)

    # Función para obtener el lunes de una semana
    def get_monday_of_week(target_date):
        days_since_monday = target_date.weekday()
        return target_date - timedelta(days=days_since_monday)

    # Función para obtener el sábado de una semana
    def get_saturday_of_week(target_date):
        days_until_saturday = 5 - target_date.weekday()
        return target_date + timedelta(days=days_until_saturday)

    # Generar datos diarios
    current_date = start_date
    daily_closings = []

    while current_date <= end_date:
        # Obtener pagos del día
        pagos = Payment.objects.filter(date_paid__date=current_date)
        ventas = Venta.objects.filter(date_sold__date=current_date)
        bookings = Booking.objects.filter(class_date=current_date)

        # Calcular totales por método de pago
        efectivo = (
            pagos.filter(
                Q(payment_method__iexact="efectivo") | Q(payment_method__iexact="cash")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        transferencia = (
            pagos.filter(
                Q(payment_method__iexact="transferencia")
                | Q(payment_method__iexact="transfer")
                | Q(payment_method__iexact="deposito")
                | Q(payment_method__iexact="depósito")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        visalink = (
            pagos.filter(
                Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="card")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Calcular totales
        total_pagos = pagos.aggregate(Sum("amount"))["amount__sum"] or 0
        total_ventas = ventas.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        total_dia = total_pagos + total_ventas

        # Estadísticas de clases
        asistencias = bookings.filter(attendance_status="attended").count()
        no_shows = bookings.filter(attendance_status="no_show").count()
        clases_individuales = bookings.filter(schedule__is_individual=True).count()
        paquetes_vendidos = pagos.count()

        daily_closings.append(
            {
                "fecha": current_date.isoformat(),
                "dia_semana": current_date.strftime("%A"),
                "efectivo": float(efectivo),
                "transferencia": float(transferencia),
                "visalink": float(visalink),
                "total_pagos": float(total_pagos),
                "total_ventas": float(total_ventas),
                "total_dia": float(total_dia),
                "asistencias": asistencias,
                "no_shows": no_shows,
                "clases_individuales": clases_individuales,
                "paquetes_vendidos": paquetes_vendidos,
                "detalle_pagos": [
                    {
                        "cliente": pago.client.full_name,
                        "membresia": pago.membership.name,
                        "monto": float(pago.amount),
                        "metodo": pago.payment_method or "No especificado",
                        "observaciones": f"Pago #{pago.id}",
                    }
                    for pago in pagos.select_related("client", "membership")
                ],
            }
        )

        current_date += timedelta(days=1)

    # Generar datos semanales (Lunes a Sábado)
    weekly_closings = []
    current_date = get_monday_of_week(start_date)
    week_number = 1

    while current_date <= end_date:
        week_end = get_saturday_of_week(current_date)

        # Ajustar si el sábado excede el rango
        if week_end > end_date:
            week_end = end_date

        # Obtener datos de la semana
        pagos = Payment.objects.filter(
            date_paid__date__gte=current_date, date_paid__date__lte=week_end
        )
        ventas = Venta.objects.filter(
            date_sold__date__gte=current_date, date_sold__date__lte=week_end
        )
        bookings = Booking.objects.filter(
            class_date__gte=current_date, class_date__lte=week_end
        )

        # Calcular totales por método de pago
        efectivo = (
            pagos.filter(
                Q(payment_method__iexact="efectivo") | Q(payment_method__iexact="cash")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        transferencia = (
            pagos.filter(
                Q(payment_method__iexact="transferencia")
                | Q(payment_method__iexact="transfer")
                | Q(payment_method__iexact="deposito")
                | Q(payment_method__iexact="depósito")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        visalink = (
            pagos.filter(
                Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="card")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Calcular totales
        total_pagos = pagos.aggregate(Sum("amount"))["amount__sum"] or 0
        total_ventas = ventas.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        total_semana = total_pagos + total_ventas

        # Estadísticas de clases
        asistencias = bookings.filter(attendance_status="attended").count()
        no_shows = bookings.filter(attendance_status="no_show").count()
        clases_individuales = bookings.filter(schedule__is_individual=True).count()
        paquetes_vendidos = pagos.count()

        weekly_closings.append(
            {
                "semana": week_number,
                "fecha_inicio": current_date.isoformat(),
                "fecha_fin": week_end.isoformat(),
                "rango": f"{current_date.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}",
                "efectivo": float(efectivo),
                "transferencia": float(transferencia),
                "visalink": float(visalink),
                "total_pagos": float(total_pagos),
                "total_ventas": float(total_ventas),
                "total_semana": float(total_semana),
                "asistencias": asistencias,
                "no_shows": no_shows,
                "clases_individuales": clases_individuales,
                "paquetes_vendidos": paquetes_vendidos,
                "dias_laborables": (week_end - current_date).days + 1,
                "detalle_pagos": [
                    {
                        "cliente": pago.client.full_name,
                        "membresia": pago.membership.name,
                        "monto": float(pago.amount),
                        "metodo": pago.payment_method or "No especificado",
                        "fecha": pago.date_paid.date().isoformat(),
                        "observaciones": f"Pago #{pago.id}",
                    }
                    for pago in pagos.select_related("client", "membership")
                ],
            }
        )

        # Avanzar a la siguiente semana (lunes)
        current_date += timedelta(days=7)
        week_number += 1

    return Response(
        {
            "periodo": {"inicio": start_date.isoformat(), "fin": end_date.isoformat()},
            "cierres_diarios": daily_closings,
            "cierres_semanales": weekly_closings,
            "resumen_periodo": {
                "total_efectivo": sum(c["efectivo"] for c in daily_closings),
                "total_transferencia": sum(c["transferencia"] for c in daily_closings),
                "total_visalink": sum(c["visalink"] for c in daily_closings),
                "total_general": sum(c["total_dia"] for c in daily_closings),
                "total_asistencias": sum(c["asistencias"] for c in daily_closings),
                "total_paquetes": sum(c["paquetes_vendidos"] for c in daily_closings),
                "semanas_totales": len(weekly_closings),
                "dias_totales": len(daily_closings),
            },
        }
    )


@api_view(["GET"])
def get_weekly_closing_summary(request):
    """
    Endpoint para obtener cierres contables semanales (Lunes a Sábado).
    Parámetros opcionales:
    - year: año específico
    - month: mes específico
    - week: semana específica del año
    """

    # Obtener parámetros
    year_param = request.query_params.get("year")
    month_param = request.query_params.get("month")
    week_param = request.query_params.get("week")

    print(f"Year param: {year_param}")
    print(f"Month param: {month_param}")
    print(f"Week param: {week_param}")

    if year_param:
        try:
            year = int(year_param)
        except ValueError:
            return Response({"error": "Año inválido"}, status=400)
    else:
        year = localtime(now()).year

    if month_param:
        try:
            month = int(month_param)
            # Calcular rango del mes
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        except ValueError:
            return Response({"error": "Mes inválido"}, status=400)
    else:
        # Por defecto, año completo
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

    # Función para obtener el lunes de una semana
    def get_monday_of_week(target_date):
        days_since_monday = target_date.weekday()
        return target_date - timedelta(days=days_since_monday)

    # Función para obtener el sábado de una semana
    def get_saturday_of_week(target_date):
        days_until_saturday = 5 - target_date.weekday()
        return target_date + timedelta(days=days_until_saturday)

    # Generar semanas (Lunes a Sábado)
    weekly_closings = []
    current_date = get_monday_of_week(start_date)
    week_number = 1

    while current_date <= end_date:
        week_end = get_saturday_of_week(current_date)

        # Ajustar si el sábado excede el rango
        if week_end > end_date:
            week_end = end_date

        # Obtener datos de la semana
        pagos = Payment.objects.filter(
            date_paid__date__gte=current_date, date_paid__date__lte=week_end
        )
        ventas = Venta.objects.filter(
            date_sold__date__gte=current_date, date_sold__date__lte=week_end
        )
        bookings = Booking.objects.filter(
            class_date__gte=current_date, class_date__lte=week_end
        )

        # Calcular totales por método de pago
        efectivo = (
            pagos.filter(
                Q(payment_method__iexact="efectivo") | Q(payment_method__iexact="cash")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        transferencia = (
            pagos.filter(
                Q(payment_method__iexact="transferencia")
                | Q(payment_method__iexact="transfer")
                | Q(payment_method__iexact="deposito")
                | Q(payment_method__iexact="depósito")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        visalink = (
            pagos.filter(
                Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="visalink")
                | Q(payment_method__iexact="card")
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Calcular totales
        total_pagos = pagos.aggregate(Sum("amount"))["amount__sum"] or 0
        total_ventas = ventas.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        total_semana = total_pagos + total_ventas

        # Estadísticas de clases
        asistencias = bookings.filter(attendance_status="attended").count()
        no_shows = bookings.filter(attendance_status="no_show").count()
        clases_individuales = bookings.filter(schedule__is_individual=True).count()
        paquetes_vendidos = pagos.count()

        weekly_closings.append(
            {
                "semana": week_number,
                "año": year,
                "fecha_inicio": current_date.isoformat(),
                "fecha_fin": week_end.isoformat(),
                "rango": f"{current_date.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}",
                "efectivo": float(efectivo),
                "transferencia": float(transferencia),
                "visalink": float(visalink),
                "total_pagos": float(total_pagos),
                "total_ventas": float(total_ventas),
                "total_semana": float(total_semana),
                "asistencias": asistencias,
                "no_shows": no_shows,
                "clases_individuales": clases_individuales,
                "paquetes_vendidos": paquetes_vendidos,
                "dias_laborables": (week_end - current_date).days + 1,
                "detalle_pagos": [
                    {
                        "cliente": pago.client.full_name,
                        "membresia": pago.membership.name,
                        "monto": float(pago.amount),
                        "metodo": pago.payment_method or "No especificado",
                        "fecha": pago.date_paid.date().isoformat(),
                        "observaciones": f"Pago #{pago.id}",
                    }
                    for pago in pagos.select_related("client", "membership")
                ],
            }
        )

        # Avanzar a la siguiente semana (lunes)
        current_date += timedelta(days=7)
        week_number += 1

    return Response(
        {
            "periodo": {
                "año": year,
                "inicio": start_date.isoformat(),
                "fin": end_date.isoformat(),
            },
            "cierres_semanales": weekly_closings,
            "resumen_periodo": {
                "total_efectivo": sum(c["efectivo"] for c in weekly_closings),
                "total_transferencia": sum(c["transferencia"] for c in weekly_closings),
                "total_visalink": sum(c["visalink"] for c in weekly_closings),
                "total_general": sum(c["total_semana"] for c in weekly_closings),
                "total_asistencias": sum(c["asistencias"] for c in weekly_closings),
                "total_paquetes": sum(c["paquetes_vendidos"] for c in weekly_closings),
                "semanas_totales": len(weekly_closings),
            },
        }
    )


class BookingViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSedeOwnerOrReadOnly]
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.validated_data["client"]
        schedule = serializer.validated_data["schedule"]

        # Verificar si quien crea es admin o secretaria
        is_manual_checkin = (
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name__in=["admin", "secretaria"]).exists()
        )

        # Extraer y convertir el valor de membership_id
        selected_membership = request.data.get("membership_id", None)
        try:
            selected_membership = (
                int(selected_membership) if selected_membership is not None else None
            )
        except ValueError:
            selected_membership = None

        # Verificar asistencia si viene en el request
        attendance_status = "pending"
        if is_manual_checkin and request.data.get("attendance_status") == "attended":
            attendance_status = "attended"

        # 1) Validar cupo en el horario
        current_bookings = (
            Booking.objects.filter(
                schedule=schedule,
                class_date=request.data.get("class_date"),
                status="active",
            )
            .exclude(attendance_status="cancelled")
            .count()
        )
        if current_bookings >= schedule.capacity:
            return Response(
                {"detail": "No hay cupo disponible para este horario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) Si seleccionó clase individual
        if selected_membership == 1:
            booking = serializer.save(
                membership=Membership.objects.get(pk=1), status="pending"
            )
            send_individual_booking_pending_email(booking)
            return Response(
                {
                    "detail": "Tu reserva para la clase individual está pendiente de confirmación. Realiza el depósito del 40% (aprox. Q36) para confirmar tu clase.",
                    "booking_id": booking.id,
                },
                status=status.HTTP_201_CREATED,
            )

        # 3) Si aún tiene clase de prueba gratuita
        if not client.trial_used:
            booking = serializer.save(attendance_status=attendance_status)
            if attendance_status == "attended":
                client.trial_used = True
                client.save(update_fields=["trial_used"])
            
            # Enviar email de confirmación (con manejo de errores)
            try:
                send_booking_confirmation_email(booking, client)
            except Exception as e:
                # Log el error pero no fallar la creación del booking
                print(f"Error enviando email de confirmación: {e}")
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # 4) Si no tiene membresía activa y ya usó su clase de prueba
        if not client.active_membership and not is_manual_checkin and client.trial_used:
            return Response(
                {
                    "detail": "No tienes una membresía activa y ya usaste tu clase de prueba gratuita. Por favor adquiere un plan para continuar."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5) Validar límite de clases según membresía o promoción
        today = now().date()
        latest_payment = (
            Payment.objects.filter(
                client=client, 
                valid_from__lte=today, 
                valid_until__gte=today
            )
            .order_by("-valid_until")
            .first()
        )

        if latest_payment:
            today = now().date()

            # 1) Plan del pago vigente
            membership_plan = latest_payment.membership

            # 2) Calcular total_permitidas (plan + extras, o promo + extras)
            total_permitidas = 0
            if latest_payment.promotion_id:
                promotion = latest_payment.promotion

                promo_instance = (
                    PromotionInstance.objects.filter(
                        promotion=promotion, clients=client
                    )
                    .order_by("-created_at")
                    .first()
                )

                if not promo_instance:
                    return Response(
                        {
                            "detail": "Esta promoción no está asociada correctamente a tu cuenta."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not promo_instance.is_active():
                    return Response(
                        {"detail": "La promoción que adquiriste ya no está activa."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                total_permitidas = (promotion.clases_por_cliente or 0) + (
                    latest_payment.extra_classes or 0
                )

            elif (
                membership_plan
                and membership_plan.classes_per_month
                and membership_plan.classes_per_month > 0
            ):
                total_permitidas = membership_plan.classes_per_month + (
                    latest_payment.extra_classes or 0
                )

            # 3) Contar válidas **por payment** (no por fechas)
            from django.db.models import Q

            monthly_bookings = (
                Booking.objects.filter(
                    client=client,
                    status="active",
                    payment=latest_payment,
                )
                .filter(
                    Q(attendance_status="attended")
                    | Q(attendance_status="pending", class_date__gte=today)
                )
                .count()
            )

            # 4) No-shows ligados a ese payment (para reposición)
            no_shows_in_window = Booking.objects.filter(
                client=client,
                status="active",
                payment=latest_payment,
                attendance_status="no_show",
            ).count()

            # 5) Límite efectivo (una reposición si hubo ≥1 no_show; ajusta a gusto)
            reposiciones_permitidas = 1 if no_shows_in_window > 0 else 0
            limite_efectivo = (total_permitidas or 0) + reposiciones_permitidas

            # Logs útiles
            print(f"Último pago: {latest_payment}")
            print(f"Fecha pago: {latest_payment.date_paid}")
            print(f"Vigencia hasta: {latest_payment.valid_until}")
            print(f"Hoy: {today}")
            print(f"Total permitidas (plan/promoción + extras): {total_permitidas}")
            print(f"Válidas (por payment): {monthly_bookings}")
            print(f"No-shows (por payment): {no_shows_in_window}")
            print(f"Límite efectivo (con reposición): {limite_efectivo}")

            # 6) Validación final de límite
            if limite_efectivo and monthly_bookings >= limite_efectivo:
                return Response(
                    {
                        "detail": f"Has alcanzado tu límite de clases ({limite_efectivo})."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 6) Crear reserva normal con membresía activa
        booking = serializer.save(
            membership=client.active_membership,
            attendance_status=attendance_status,
            payment=latest_payment,
        )
        if attendance_status == "attended" and not client.trial_used:
            client.trial_used = True
            client.save(update_fields=["trial_used"])
        
        # Enviar email de confirmación (con manejo de errores)
        try:
            send_booking_confirmation_email(booking, client)
        except Exception as e:
            # Log el error pero no fallar la creación del booking
            print(f"Error enviando email de confirmación: {e}")
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(detail=False, methods=["get"], url_path="by-client/(?P<client_id>[^/.]+)")
    def bookings_by_client(self, request, client_id=None):
        """
        OPTIMIZED VERSION: Uses select_related for better performance without pagination.
        """
        # Optimized query with select_related to avoid N+1 queries
        bookings = (
            Booking.objects.filter(client_id=client_id)
            .select_related("schedule", "schedule__class_type", "membership")
            .order_by("-class_date")
        )

        # Use a simpler serializer for better performance
        data = []
        for booking in bookings:
            # Format schedule info
            schedule_info = "—"
            if booking.schedule:
                day_name = booking.class_date.strftime("%A")
                day_name_es = {
                    "Monday": "Lunes",
                    "Tuesday": "Martes",
                    "Wednesday": "Miércoles",
                    "Thursday": "Jueves",
                    "Friday": "Viernes",
                    "Saturday": "Sábado",
                    "Sunday": "Domingo",
                }.get(day_name, day_name)
                schedule_info = f"{day_name_es} {booking.schedule.time_slot} ({'Individual' if booking.schedule.is_individual else 'Grupal'})"

            # Format membership info
            membership_info = "-"
            if booking.membership:
                membership_info = (
                    f"{booking.membership.name} ({booking.membership.price})"
                )

            data.append(
                {
                    "id": booking.id,
                    "client_id": booking.client_id,
                    "class_date": booking.class_date.strftime("%Y-%m-%d"),
                    "attendance_status": booking.attendance_status,
                    "date_booked": (
                        booking.date_booked.strftime("%Y-%m-%d")
                        if booking.date_booked
                        else None
                    ),
                    "schedule": schedule_info,
                    "membership": membership_info,
                    "cancellation_reason": booking.cancellation_reason,
                }
            )

        return Response(data)

    @action(detail=True, methods=["put"], url_path="attendance")
    def mark_attendance(self, request, pk=None):
        try:
            booking = self.get_object()
        except Booking.DoesNotExist:
            return Response(
                {"error": "Reserva no encontrada."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = BookingAttendanceUpdateSerializer(
            booking, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            client = booking.client
            if not client.trial_used:
                client.trial_used = True
                client.save(update_fields=["trial_used"])
            return Response(
                {
                    "message": "Asistencia actualizada correctamente.",
                    "data": serializer.data,
                }
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="historial")
    def historial_asistencia(self, request):
        date_filter = request.query_params.get("date")
        queryset = Booking.objects.filter(status="active").select_related(
            "client", "schedule", "schedule__class_type"
        )

        # Filtrar por sede si se proporciona
        sede_ids = request.query_params.get("sede_ids")
        if sede_ids:
            sede_ids_list = [
                int(id.strip()) for id in sede_ids.split(",") if id.strip()
            ]
            queryset = queryset.filter(schedule__sede_id__in=sede_ids_list)
        else:
            # Verificar headers de sede
            sede_header = request.headers.get("X-Sedes-Selected")
            sede_id_header = request.headers.get("X-Sede-ID")
            
            if sede_header:
                sede_ids_list = [
                    int(id.strip()) for id in sede_header.split(",") if id.strip()
                ]
                queryset = queryset.filter(schedule__sede_id__in=sede_ids_list)
            elif sede_id_header:
                # Nuevo header X-Sede-ID para sede individual
                try:
                    sede_id = int(sede_id_header.strip())
                    queryset = queryset.filter(schedule__sede_id=sede_id)
                except ValueError:
                    pass  # Si hay error, no filtrar por sede

        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, "%Y-%m-%d").date()
                queryset = queryset.filter(class_date=date_obj)
            except ValueError:
                return Response(
                    {"error": "Formato de fecha inválido. Usa YYYY-MM-DD."}, status=400
                )

        queryset = queryset.order_by("-class_date")
        serializer = BookingHistorialSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["put"], url_path="cancel")
    def cancel_booking(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get("reason", "")
        cancelled_by = request.data.get("by", "client")  # client, instructor, admin

        # Store original data before cancellation for email
        original_schedule = booking.schedule
        original_date = booking.class_date

        print(f"Original schedule: {original_schedule}")
        print(f"Original date: {original_date}")

        booking.status = "cancelled"
        booking.cancellation_type = cancelled_by
        booking.cancellation_reason = reason
        booking.save()

        # Send cancellation email
        try:
            from .management.mails.mails import send_booking_cancellation_email

            send_booking_cancellation_email(booking, reason)
        except Exception as e:
            # Log error but don't fail the request
            import traceback

            print(f"Error sending cancellation email: {e}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")

        return Response({"message": "Reserva cancelada correctamente."})

    @action(detail=True, methods=["put"], url_path="reschedule")
    def reschedule_booking(self, request, pk=None):
        booking = self.get_object()
        new_schedule_id = request.data.get("schedule_id")
        new_date = request.data.get("class_date")

        try:
            new_schedule = Schedule.objects.get(id=new_schedule_id)
        except Schedule.DoesNotExist:
            return Response({"error": "Nuevo horario no válido."}, status=400)

        # Validar que no exista una reserva duplicada
        if Booking.objects.filter(
            client=booking.client, schedule=new_schedule, class_date=new_date
        ).exists():
            return Response(
                {"error": "Ya tienes una reserva para esa clase."}, status=400
            )

        # Validar capacidad
        count = Booking.objects.filter(
            schedule=new_schedule, class_date=new_date, status="active"
        ).count()
        if count >= new_schedule.capacity:
            return Response({"error": "No hay cupo disponible."}, status=400)

        # Store original data before rescheduling for email
        old_schedule = booking.schedule
        old_date = booking.class_date

        # Actualizar
        booking.schedule = new_schedule
        booking.class_date = new_date
        booking.save()

        # Send reschedule email
        try:
            from .management.mails.mails import send_booking_reschedule_email

            send_booking_reschedule_email(
                booking, old_schedule, new_schedule, old_date, new_date
            )
        except Exception as e:
            # Log error but don't fail the request

            print(f"Error sending reschedule email: {e}")
        return Response({"message": "Clase reagendada correctamente."})

    @action(detail=False, methods=["get"], url_path="available-slots-for-reschedule")
    def available_slots_for_reschedule(self, request):
        """
        Get available slots for rescheduling with detailed information
        """
        date_str = request.query_params.get("date")
        client_id = request.query_params.get("client_id")
        current_booking_id = request.query_params.get("current_booking_id")

        # Si no se proporciona client_id, intentar obtenerlo del current_booking_id
        if not client_id and current_booking_id:
            try:
                current_booking = Booking.objects.get(id=current_booking_id)
                client_id = current_booking.client.id
            except Booking.DoesNotExist:
                return Response({"detail": "Reserva actual no encontrada."}, status=404)

        if not date_str or not client_id:
            return Response(
                {
                    "detail": "Se requieren los parámetros 'date' y 'client_id' (o 'current_booking_id')."
                },
                status=400,
            )

        try:
            requested_date = parse_date(date_str)
            if not requested_date:
                return Response({"detail": "Formato de fecha inválido."}, status=400)
        except Exception as e:
            print(f"Error al parsear la fecha: {e}")
            return Response({"detail": "Formato de fecha inválido."}, status=400)

        # Mapear weekday (0=Monday) a código de día definido en Schedule.DAY_CHOICES
        day_code_map = {
            0: "MON",
            1: "TUE",
            2: "WED",
            3: "THU",
            4: "FRI",
            5: "SAT",
            6: "SUN",
        }
        day_code = day_code_map[requested_date.weekday()]

        # Obtener todas las plantillas de horario (Schedule) para ese día
        schedules = Schedule.objects.filter(day=day_code)

        slots = []
        for schedule in schedules:
            # Contar reservas activas para este schedule en la fecha solicitada
            booking_count = (
                Booking.objects.filter(
                    schedule=schedule, class_date=requested_date, status="active"
                )
                .exclude(attendance_status="cancelled")
                .count()
            )

            available = booking_count < schedule.capacity
            available_slots = max(0, schedule.capacity - booking_count)

            # Verificar si el cliente ya tiene una reserva para este horario
            client_has_booking = Booking.objects.filter(
                client_id=client_id,
                schedule=schedule,
                class_date=requested_date,
                status="active",
            ).exists()

            # Si es el mismo horario de la reserva actual, permitir
            is_current_booking = False
            if current_booking_id:
                current_booking = Booking.objects.filter(
                    id=current_booking_id, schedule=schedule, class_date=requested_date
                ).first()
                is_current_booking = bool(current_booking)

            # Convertir el campo time_slot (e.g. '05:00') en un datetime combinando con requested_date
            start_time = datetime.combine(
                requested_date, datetime.strptime(schedule.time_slot, "%H:%M").time()
            )
            end_time = start_time + timedelta(hours=1)  # Cada slot dura 1 hora

            slot = {
                "schedule_id": schedule.id,
                "class_type": schedule.class_type.name if schedule.class_type else None,
                "is_individual": schedule.is_individual,
                "capacity": schedule.capacity,
                "booked": booking_count,
                "available_slots": available_slots,
                "coach": (
                    schedule.coach.first_name + " " + schedule.coach.last_name
                    if schedule.coach
                    else "Sin asignar"
                ),
                "available": available
                and (not client_has_booking or is_current_booking),
                "client_has_booking": client_has_booking,
                "is_current_booking": is_current_booking,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "can_reschedule_to": available
                and (not client_has_booking or is_current_booking),
            }
            slots.append(slot)

        response_data = {
            "date": requested_date.isoformat(),
            "slots": sorted(slots, key=lambda x: x["start"]),
            "total_available_slots": sum(slot["available_slots"] for slot in slots),
            "total_schedules": len(slots),
        }
        return Response(response_data)

        # return phone[:10] if phone else None

    def import_payments_from_excel(file_obj):

        def strip_accents(text):
            """Quitar acentos y minúsculas."""
            if not text:
                return ""
            text = unicodedata.normalize("NFD", text)
            return (
                "".join(c for c in text if unicodedata.category(c) != "Mn")
                .lower()
                .strip()
            )

        """
        Procesa un archivo Excel para asociar pagos a clientes existentes por nombre completo.
        También actualiza el estado del cliente a Activo si corresponde.
        """
        try:
            df = pd.read_excel(file_obj)
        except Exception as e:
            return {"error": f"Error al leer el archivo: {e}"}

        required_cols = {"name", "membership", "amount", "payment_date"}
        if not required_cols.issubset(df.columns):
            return {
                "error": "El archivo debe tener columnas: 'name', 'membership', 'amount', 'payment_date'."
            }

        memberships = {m.name.lower(): m for m in Membership.objects.all()}
        clients = {(f"{c.first_name} {c.last_name}"): c for c in Client.objects.all()}
        today = timezone.now().date()

        success = 0
        failed = []

        with transaction.atomic():
            for idx, row in df.iterrows():
                try:
                    name_raw = str(row.get("name", "")).strip()
                    membership_name = str(row.get("membership", "")).strip()
                    amount_raw = row.get("amount")
                    payment_date_raw = row.get("payment_date")

                    name_normalized = strip_accents(name_raw)
                    client = clients.get(name_normalized)

                    if not client:
                        failed.append(
                            {
                                "row": idx + 2,
                                "error": f"Cliente no encontrado: {name_raw}",
                            }
                        )
                        continue

                    # Buscar membresía
                    membership = memberships.get(membership_name.lower())
                    if not membership:
                        failed.append(
                            {
                                "row": idx + 2,
                                "error": f"Membresía no encontrada: {membership_name}",
                            }
                        )
                        continue

                    # Parsear monto
                    try:
                        amount = Decimal(str(amount_raw))
                    except Exception:
                        amount = membership.price

                    # Parsear fecha
                    try:
                        if isinstance(payment_date_raw, datetime):
                            date_paid = payment_date_raw
                        else:
                            date_paid = pd.to_datetime(payment_date_raw)
                    except Exception:
                        failed.append(
                            {"row": idx + 2, "error": "Fecha de pago inválida"}
                        )
                        continue

                    # Crear el Payment
                    payment = Payment.objects.create(
                        client=client,
                        membership=membership,
                        amount=amount,
                        date_paid=date_paid,
                        valid_until=date_paid.date() + timedelta(days=30),
                    )

                    # Verificar y actualizar estado activo
                    if payment.valid_until >= today and client.status != "A":
                        client.status = "A"
                        client.save(update_fields=["status"])

                    success += 1

                except Exception as exc:
                    failed.append({"row": idx + 2, "error": str(exc)})

        return {
            "message": f"Pagos importados correctamente: {success}",
            "errors": failed,
        }

    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        permission_classes=[IsAdminUser],
    )
    def import_bookings_from_excel(self, request):
        """
        Importa reservas (attended, no-show y canceladas) desde un archivo
        Excel / CSV exportado de Calendly.  Crea clientes, pagos y bookings
        en lote, evitando duplicados y time-outs.
        """

        # ───────── helpers ──────────────────────────────────────────
        ALL_TZ = set(pytz.all_timezones)

        def is_tz(val: str | None) -> bool:
            return val in ALL_TZ if val else False

        def strip(txt: str | None) -> str:
            if not txt:
                return ""
            return (
                "".join(
                    c
                    for c in unicodedata.normalize("NFD", txt)
                    if unicodedata.category(c) != "Mn"
                )
                .lower()
                .strip()
            )

        def synth_dpi() -> str:
            base = int(pytime.time() * 1000) % 10_000_000_000  # 10 dígitos
            rand = secrets.randbelow(90) + 10  # 2 dígitos (10-99)
            return f"S{base:010d}{rand:02d}"  # 13 chars

        def norm_email(e: str | None) -> str:
            if not e:
                return ""
            e = e.strip().lower()
            local, at, dom = e.partition("@")

            if dom in {"gmail.com", "googlemail.com"}:
                # Recorta alias +algo → nombre+familia  ⇒  nombre
                local = local.split("+", 1)[0]
                # Mantiene los puntos:
                #   claus.melgar+fam ⇒ claus.melgar   (✓ puntos intactos)
            return f"{local}{at}{dom}"

        def utf8(obj) -> str:
            if obj is None or str(obj).lower() in {"nan", "none"}:
                return ""
            return str(obj).encode("utf-8", "ignore").decode("utf-8", "ignore").strip()

        def clean_phone(raw: str | None) -> str | None:
            """Normaliza a formato +502XXXXXXXX.
            - Elimina todos los caracteres no numéricos.
            - Si vienen 8 dígitos → añade prefijo 502.
            - Si ya viene con 502 (11 o 12 dígitos) se conserva.
            - En cualquier otro caso se devuelve tal cual para que QA lo revise.
            """
            if not raw or str(raw).lower() in {"nan", "none"}:
                return None
            digits = re.sub(r"[^0-9]", "", str(raw))
            if len(digits) == 8:  # local
                digits = "502" + digits
            elif digits.startswith("502") and len(digits) in {11, 12}:
                pass  # ya bien
            else:
                # número extraño, se retorna como apareció (sin +)
                return f"+{digits}" if digits else None
            return f"+{digits}"

        # ───────── leer archivo ─────────────────────────────────────
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "Archivo no proporcionado"}, status=400)

        try:
            df = pd.read_excel(
                file_obj,
                dtype={"payment_date": str, "valid_until": str, "class_date": str},
            )
        except Exception:
            file_obj.seek(0)
            try:
                df = pd.read_csv(file_obj, dtype=str)
            except Exception as e:
                return Response({"error": f"Error al leer archivo: {e}"}, status=400)

        required_cols = {
            "first_name",
            "last_name",
            "email",
            "phone",
            "class_date",
            "time_slot",
            "day",
        }
        faltantes = required_cols - set(df.columns)
        if faltantes:
            return Response(
                {"error": f"Faltan columnas: {', '.join(faltantes)}"}, status=400
            )

        # ───────── caches y contenedores bulk ───────────────────────
        bulk_bookings, bulk_payments, bulk_updates = [], [], []
        touched_clients: set[int] = set()
        failed: list[dict] = []
        success = 0

        memberships = {m.name.lower(): m for m in Membership.objects.all()}
        schedules = {(s.day, s.time_slot[:5]): s for s in Schedule.objects.all()}
        clients_e = {
            c.email.lower(): c
            for c in Client.objects.only(
                "id",
                "email",
                "first_name",
                "last_name",
                "dpi",
                "phone",
                "notes",
                "status",
                "trial_used",
            )
        }
        name_phone_cache: dict[tuple[str, str | None], Client] = {}

        status_map = {
            "attended": ("active", "attended"),
            "no_show": ("active", "no_show"),
            "no attended": ("active", "no_show"),
            "no asistio": ("active", "no_show"),
            "no asistió": ("active", "no_show"),
            "pending": ("active", "pending"),
            "cancelled": ("cancelled", "pending"),
            "canceled": ("cancelled", "pending"),
        }

        # ───────── iterar filas ─────────────────────────────────────
        for idx, row in df.iterrows():
            excel_row = idx + 2  # fila real en Excel
            try:
                # ―― normalizar campos ――――――――――――――――――――――――――
                fn = utf8(row.get("first_name"))
                ln = utf8(row.get("last_name"))
                em = norm_email(utf8(row.get("email")))
                ph = clean_phone(row.get("phone"))
                dpi = utf8(row.get("dpi"))
                nt = utf8(row.get("notes"))
                src = utf8(row.get("source")) or "Migración Excel"

                memb_raw = utf8(row.get("membership"))
                att_raw = utf8(row.get("attendance_status")).lower() or "attended"
                b_status, a_status = status_map.get(att_raw, ("active", "pending"))

                fn_n, ln_n = strip(fn), strip(ln)
                key_np = (fn_n + ln_n, ph)

                # ―― resolver / crear cliente ――――――――――――――――――
                cli = None
                if dpi.isdigit():
                    cli = Client.objects.filter(dpi=dpi).first()
                if not cli and em:
                    cli = clients_e.get(em)
                if not cli and ph:
                    cli = name_phone_cache.get(key_np)

                if not cli:
                    dpi_final = dpi if dpi.isdigit() else synth_dpi()
                    while Client.objects.filter(dpi=dpi_final).exists():
                        dpi_final = synth_dpi()
                    cli = Client.objects.create(
                        dpi=dpi_final,
                        first_name=fn,
                        last_name=ln,
                        email=em or f"{dpi_final}@noemail.com",
                        phone=ph,
                        notes=nt,
                        source=src,
                        status="I",
                    )
                    clients_e[cli.email.lower()] = cli
                name_phone_cache[key_np] = cli

                # actualizar campos faltantes
                dirty = False
                if not cli.phone and ph:
                    cli.phone, dirty = ph, True
                if not cli.dpi and dpi.isdigit():
                    cli.dpi, dirty = dpi, True
                if not cli.notes and nt:
                    cli.notes, dirty = nt, True
                if dirty and cli.id not in touched_clients:
                    bulk_updates.append(cli)
                    touched_clients.add(cli.id)

                # ―― schedule ―――――――――――――――――――――――――――――――
                day_code = utf8(row.get("day")).upper()
                time_raw = utf8(row.get("time_slot"))
                time_key = time_raw[:5] if ":" in time_raw else time_raw
                sched = schedules.get((day_code, time_key))
                if not sched:
                    failed.append(
                        {
                            "row": excel_row,
                            "error": f"No hay horario: {day_code} {time_key}",
                        }
                    )
                    continue

                # ―― fecha de clase ―――――――――――――――――――――――――
                try:
                    class_date = pd.to_datetime(utf8(row.get("class_date"))).date()
                except Exception:
                    failed.append({"row": excel_row, "error": "class_date inválido"})
                    continue

                # ―― membresía / pago ―――――――――――――――――――――――
                member = None
                if memb_raw:
                    is_trial = memb_raw.lower() in {"trial", "clase de prueba"}
                    if not is_trial:
                        member = memberships.get(memb_raw.lower())
                        if not member:
                            failed.append(
                                {
                                    "row": excel_row,
                                    "error": f"Membresía no encontrada: {memb_raw}",
                                }
                            )
                            continue

                        pay_raw = utf8(row.get("payment_date"))
                        if is_tz(pay_raw):
                            failed.append(
                                {"row": excel_row, "error": "payment_date contiene TZ"}
                            )
                            continue
                        try:
                            pay_day = pd.to_datetime(pay_raw).date()
                        except Exception:
                            failed.append(
                                {"row": excel_row, "error": "payment_date inválida"}
                            )
                            continue

                        pay_dt = timezone.make_aware(
                            datetime.combine(pay_day, dtime.min)
                        )

                        val_raw = utf8(row.get("valid_until"))
                        if is_tz(val_raw):
                            val_raw = ""
                        try:
                            val_until = (
                                pd.to_datetime(val_raw).date() if val_raw else None
                            )
                        except Exception:
                            val_until = None
                        if not val_until:
                            val_until = pay_day + timedelta(days=30)

                        amt_raw = row.get("amount")
                        try:
                            amt = Decimal(str(amt_raw)) if amt_raw else member.price
                        except (InvalidOperation, TypeError):
                            amt = member.price

                        bulk_payments.append(
                            Payment(
                                client=cli,
                                membership=member,
                                date_paid=pay_dt,
                                valid_until=val_until,
                                amount=amt,
                            )
                        )
                    else:
                        if not cli.trial_used and a_status == "attended":
                            cli.trial_used = True
                            if cli.id not in touched_clients:
                                bulk_updates.append(cli)
                                touched_clients.add(cli.id)

                # ―― crear booking en memoria ――――――――――――――――――
                bulk_bookings.append(
                    Booking(
                        client=cli,
                        schedule=sched,
                        class_date=class_date,
                        attendance_status=a_status,
                        membership=member,
                        status=b_status,
                    )
                )
                success += 1

            except Exception as exc:
                failed.append({"row": excel_row, "error": str(exc)})

        # ───────── bulk DB ops ──────────────────────────────────────
        with transaction.atomic():
            if bulk_updates:
                Client.objects.bulk_update(
                    bulk_updates,
                    ["phone", "dpi", "notes", "status", "trial_used"],
                )
            if bulk_payments:
                Payment.objects.bulk_create(
                    bulk_payments, ignore_conflicts=True, batch_size=500
                )
            if bulk_bookings:
                Booking.objects.bulk_create(
                    bulk_bookings, ignore_conflicts=True, batch_size=500
                )

        return Response(
            {"message": f"Se importaron {success} filas.", "errors": failed},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="clientes-en-riesgo")
    def clientes_en_riesgo(self, request):
        from accounts.serializers import ClientSerializer

        clientes = get_clients_with_consecutive_no_shows(limit=3)
        data = ClientSerializer(clientes, many=True).data
        return Response(data)


class AvailabilityView(APIView):
    permission_classes = [permissions.AllowAny]
    """
    Endpoint que, dado un parámetro 'date' (YYYY-MM-DD), devuelve los slots disponibles
    para ese día, calculando el número de reservas activas y comparándolo con la capacidad.
    """

    def get(self, request, format=None):
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Se requiere el parámetro 'date' en formato YYYY-MM-DD."},
                status=400,
            )

        requested_date = parse_date(date_str)
        if not requested_date:
            return Response({"detail": "Formato de fecha inválido."}, status=400)

        # Mapear weekday (0=Monday) a código de día definido en Schedule.DAY_CHOICES
        day_code_map = {
            0: "MON",
            1: "TUE",
            2: "WED",
            3: "THU",
            4: "FRI",
            5: "SAT",
            6: "SUN",
        }
        day_code = day_code_map[requested_date.weekday()]

        # Filtrar por sede si se proporciona
        sede_ids = request.query_params.get("sede_ids")
        if sede_ids:
            sede_ids_list = [
                int(id.strip()) for id in sede_ids.split(",") if id.strip()
            ]
            schedules = Schedule.objects.filter(day=day_code, sede_id__in=sede_ids_list)
        else:
            # Verificar headers de sede
            sede_header = request.headers.get("X-Sedes-Selected")
            sede_id_header = request.headers.get("X-Sede-ID")
            
            if sede_header:
                sede_ids_list = [
                    int(id.strip()) for id in sede_header.split(",") if id.strip()
                ]
                schedules = Schedule.objects.filter(
                    day=day_code, sede_id__in=sede_ids_list
                )
            elif sede_id_header:
                # Nuevo header X-Sede-ID para sede individual
                try:
                    sede_id = int(sede_id_header.strip())
                    schedules = Schedule.objects.filter(day=day_code, sede_id=sede_id)
                except ValueError:
                    schedules = Schedule.objects.filter(day=day_code)
            else:
                schedules = Schedule.objects.filter(day=day_code)

        slots = []
        for schedule in schedules:
            # Contar reservas activas para este schedule en la fecha solicitada
            booking_count = (
                Booking.objects.filter(
                    schedule=schedule, class_date=requested_date, status="active"
                )
                .exclude(attendance_status="cancelled")
                .count()
            )

            available = booking_count < schedule.capacity
            available_slots = max(0, schedule.capacity - booking_count)

            # Buscar el TimeSlot correspondiente para obtener la duración real
            try:
                time_slot_obj = TimeSlot.objects.get(
                    sede=schedule.sede,
                    start_time=datetime.strptime(schedule.time_slot, "%H:%M").time(),
                    is_active=True
                )
                # Crear datetime naive para evitar problemas de zona horaria
                start_time = datetime.combine(requested_date, time_slot_obj.start_time)
                end_time = datetime.combine(requested_date, time_slot_obj.end_time)
            except TimeSlot.DoesNotExist:
                # Fallback: usar duración de 1 hora si no se encuentra el TimeSlot
                start_time = datetime.combine(
                    requested_date, datetime.strptime(schedule.time_slot, "%H:%M").time()
                )
                end_time = start_time + timedelta(hours=1)

            slot = {
                "schedule_id": schedule.id,
                "class_type": schedule.class_type.name if schedule.class_type else None,
                "is_individual": schedule.is_individual,
                "capacity": schedule.capacity,
                "booked": booking_count,
                "available_slots": available_slots,
                "coach": (
                    schedule.coach.first_name + " " + schedule.coach.last_name
                    if schedule.coach
                    else "Sin asignar"
                ),
                "available": available,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            }
            slots.append(slot)

        response_data = {
            "date": requested_date.isoformat(),
            "slots": sorted(slots, key=lambda x: x["start"]),  # ⬅️ ORDENA POR start
        }
        return Response(response_data)

    def post(self, request, format=None):
        """
        Endpoint para obtener slots disponibles con información detallada para bulk booking.
        Parámetros: date (YYYY-MM-DD), client_id (opcional)
        """
        date_str = request.data.get("date")
        client_id = request.data.get("client_id")

        if not date_str:
            return Response(
                {"detail": "Se requiere el parámetro 'date' en formato YYYY-MM-DD."},
                status=400,
            )

        requested_date = parse_date(date_str)
        if not requested_date:
            return Response({"detail": "Formato de fecha inválido."}, status=400)

        # Mapear weekday (0=Monday) a código de día definido en Schedule.DAY_CHOICES
        day_code_map = {
            0: "MON",
            1: "TUE",
            2: "WED",
            3: "THU",
            4: "FRI",
            5: "SAT",
            6: "SUN",
        }
        day_code = day_code_map[requested_date.weekday()]

        # Obtener todas las plantillas de horario (Schedule) para ese día
        schedules = Schedule.objects.filter(day=day_code)

        slots = []
        for schedule in schedules:
            # Contar reservas activas para este schedule en la fecha solicitada
            booking_count = (
                Booking.objects.filter(
                    schedule=schedule, class_date=requested_date, status="active"
                )
                .exclude(attendance_status="cancelled")
                .count()
            )

            available = booking_count < schedule.capacity
            available_slots = max(0, schedule.capacity - booking_count)

            # Verificar si el cliente ya tiene una reserva para este horario
            client_has_booking = False
            if client_id:
                client_has_booking = Booking.objects.filter(
                    client_id=client_id,
                    schedule=schedule,
                    class_date=requested_date,
                    status="active",
                ).exists()

            # Convertir el campo time_slot (e.g. '05:00') en un datetime combinando con requested_date
            start_time = datetime.combine(
                requested_date, datetime.strptime(schedule.time_slot, "%H:%M").time()
            )
            end_time = start_time + timedelta(hours=1)  # Cada slot dura 1 hora

            slot = {
                "schedule_id": schedule.id,
                "class_type": schedule.class_type.name if schedule.class_type else None,
                "is_individual": schedule.is_individual,
                "capacity": schedule.capacity,
                "booked": booking_count,
                "available_slots": available_slots,
                "coach": (
                    schedule.coach.first_name + " " + schedule.coach.last_name
                    if schedule.coach
                    else "Sin asignar"
                ),
                "available": available and not client_has_booking,
                "client_has_booking": client_has_booking,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "can_book_multiple": available_slots > 1 and not client_has_booking,
            }
            slots.append(slot)

        response_data = {
            "date": requested_date.isoformat(),
            "slots": sorted(slots, key=lambda x: x["start"]),
            "total_available_slots": sum(slot["available_slots"] for slot in slots),
            "total_schedules": len(slots),
        }
        return Response(response_data)


class MembershipViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer
    
    def get_queryset(self):
        """Filter memberships dynamically based on scope and sede."""
        queryset = super().get_queryset()
        
        # Get sede_ids from request if available
        sede_ids = getattr(self.request, 'sede_ids', None)
        
        # Get filter parameters from query string
        scope_filter = self.request.GET.get('scope', None)
        sede_filter = self.request.GET.get('sede', None)
        current_sede = self.request.GET.get('current_sede', None)
        
        # Apply scope filter if provided
        if scope_filter:
            if scope_filter == 'GLOBAL':
                queryset = queryset.filter(scope="GLOBAL")
            elif scope_filter == 'SEDE':
                queryset = queryset.filter(scope="SEDE")
        else:
            # Default behavior: show global + sede-specific for current sede
            if current_sede:
                # Show global memberships + sede-specific memberships for the current sede
                queryset = queryset.filter(
                    Q(scope="GLOBAL") | 
                    Q(scope="SEDE", sede_id=current_sede)
                )
            elif sede_ids:
                # Fallback to sede_ids if available
                queryset = queryset.filter(
                    Q(scope="GLOBAL") | 
                    Q(scope="SEDE", sede_id__in=sede_ids)
                )
            else:
                # If no sede context, show only global memberships
                queryset = queryset.filter(scope="GLOBAL")
        
        # Apply sede filter if provided
        if sede_filter:
            queryset = queryset.filter(sede_id=sede_filter)
            
        return queryset


class PlanIntentViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    permission_classes = [
        permissions.AllowAny
    ]  # Puedes cambiar esto si solo admin puede ver todo
    queryset = PlanIntent.objects.all()
    serializer_class = PlanIntentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_confirmed", "client"]  # <- aquí

    @action(detail=False, methods=["get"], url_path="by-client/(?P<client_id>[^/.]+)")
    def by_client(self, request, client_id=None):
        intents = PlanIntent.objects.filter(client_id=client_id).order_by(
            "-selected_at"
        )
        serializer = self.get_serializer(intents, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="potenciales")
    def clientes_potenciales(self, request):
        from accounts.models import Client
        from accounts.serializers import ClientSerializer

        response_data = []

        # 1) Clientes con clase de prueba pendiente (trial_used=False)
        trial_clients = Client.objects.filter(trial_used=False)

        for client in trial_clients:
            plan_intent = (
                PlanIntent.objects.filter(client=client, is_confirmed=False)
                .order_by("-selected_at")
                .first()
            )
            response_data.append(
                {
                    "client": ClientSerializer(client).data,
                    "plan_intent": (
                        PlanIntentSerializer(plan_intent).data if plan_intent else None
                    ),
                }
            )

        # 2) Clientes que ya usaron su clase de prueba pero tienen plan no confirmado
        with_trial_used = Client.objects.filter(trial_used=True)
        for client in with_trial_used:
            plan_intent = (
                PlanIntent.objects.filter(client=client, is_confirmed=False)
                .order_by("-selected_at")
                .first()
            )
            if plan_intent:
                response_data.append(
                    {
                        "client": ClientSerializer(client).data,
                        "plan_intent": PlanIntentSerializer(plan_intent).data,
                    }
                )

        return Response(response_data)


class PaymentViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.all().order_by("-date_paid")
    serializer_class = PaymentSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_fields = ["client", "payment_method", "membership"]
    search_fields = [
        "client__first_name",
        "client__last_name",
        "payment_method",
        "membership__name",
    ]
    ordering_fields = ["date_paid", "amount", "valid_until"]
    ordering = ["-date_paid"]
    pagination_class = None  # Disable pagination for now, but can be enabled if needed
    permission_classes = [IsAuthenticated, IsSedeOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Role-based access control
        user = self.request.user
        if hasattr(user, "role"):
            # Coaches can only see payments from their assigned clients
            if user.role == "coach":
                # TODO: Implement coach-client relationship filtering
                # For now, coaches see limited data
                queryset = queryset.filter(
                    date_paid__gte=timezone.now() - timedelta(days=30)
                )
            # Secretaria can see all payments but with limited audit info
            elif user.role == "secretaria":
                pass  # Can see all payments
            # Admin can see everything
            elif user.role == "admin":
                pass  # Can see all payments

        # Date range filtering
        date_from = self.request.query_params.get("date_from", None)
        date_to = self.request.query_params.get("date_to", None)

        if date_from:
            queryset = queryset.filter(date_paid__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_paid__date__lte=date_to)

        # Amount range filtering
        amount_min = self.request.query_params.get("amount_min", None)
        amount_max = self.request.query_params.get("amount_max", None)

        if amount_min:
            queryset = queryset.filter(amount__gte=float(amount_min))
        if amount_max:
            queryset = queryset.filter(amount__lte=float(amount_max))

        # Month filtering (for backward compatibility)
        month = self.request.query_params.get("month", None)
        if month:
            year, month_num = month.split("-")
            queryset = queryset.filter(date_paid__year=year, date_paid__month=month_num)

        # Single date filtering (for backward compatibility)
        date = self.request.query_params.get("date", None)
        if date:
            queryset = queryset.filter(date_paid__date=date)

        # Limit results to prevent performance issues
        # If no specific filters are applied, limit to last 1000 records
        has_filters = any(
            [
                date_from,
                date_to,
                amount_min,
                amount_max,
                month,
                date,
                self.request.query_params.get("search"),
                self.request.query_params.get("payment_method"),
                self.request.query_params.get("client"),
            ]
        )

        if not has_filters:
            queryset = queryset[:1000]

        return queryset

    def create(self, request, *args, **kwargs):
        # Validación de duplicados recientes (últimos 5 minutos)
        client_id = request.data.get('client_id')
        membership_id = request.data.get('membership_id')
        amount = request.data.get('amount')
        
        if client_id and membership_id and amount:
            recent_payment = Payment.objects.filter(
                client_id=client_id,
                membership_id=membership_id,
                amount=amount,
                created_at__gte=timezone.now() - timedelta(minutes=5)
            ).first()
            
            if recent_payment:
                return Response({
                    'error': 'Ya existe un pago similar creado recientemente',
                    'message': f'Se encontró un pago duplicado creado hace {int((timezone.now() - recent_payment.created_at).total_seconds() / 60)} minutos',
                    'existing_payment_id': recent_payment.id,
                    'existing_payment_date': recent_payment.created_at
                }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client = serializer.validated_data["client"]
        client_id = client.id
        membership = serializer.validated_data["membership"]
        payment_method = request.data.get("payment_method", None)
        amount = serializer.validated_data["amount"]
        date_paid = serializer.validated_data.get("date_paid", timezone.now())

        today = date_paid.date()
        selected_promotion = None
        promo_instance = None
        valid_until = today + timedelta(days=30)

        # Buscar si tiene una promoción activa asociada al mismo membership
        promo_instance = (
            PromotionInstance.objects.filter(
                clients=client,
                promotion__membership=membership,
                promotion__start_date__lte=today,
                promotion__end_date__gte=today,
            )
            .order_by("-created_at")
            .first()
        )

        if promo_instance:
            selected_promotion = promo_instance.promotion

        # Ahora sí podemos guardar con los datos completos
        payment = serializer.save(
            client_id=client_id,
            membership=membership,
            amount=amount,
            date_paid=date_paid,
            valid_until=valid_until,
            promotion=selected_promotion,
            promotion_instance=promo_instance,
            payment_method=payment_method,
        )

        # Activar cliente y asignar membresía actual si su pago aún es vigente
        if payment.valid_until >= today:
            client.status = "A"
            client.current_membership = membership
            client.save(update_fields=["status", "current_membership"])

        # Confirmar plan intent si existe
        try:
            plan_intent = PlanIntent.objects.filter(
                client_id=client_id, membership_id=membership.id, is_confirmed=False
            ).latest("selected_at")
            plan_intent.is_confirmed = True
            plan_intent.save()
        except PlanIntent.DoesNotExist:
            pass

        # Actualizar ingresos mensuales
        year = payment.date_paid.year
        month = payment.date_paid.month
        monthly, _ = MonthlyRevenue.objects.get_or_create(year=year, month=month)
        monthly.total_amount = F("total_amount") + payment.amount
        monthly.payment_count = F("payment_count") + 1
        monthly.save()

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    def get_total_allowed_classes(client):

        pagos = Payment.objects.filter(client=client)
        total = 0
        for p in pagos:
            clases = 0
            if p.promotion and p.promotion.clases_por_cliente:
                clases = p.promotion.clases_por_cliente
            elif p.membership and p.membership.classes_per_month:
                clases = p.membership.classes_per_month
            total += clases + (p.extra_classes or 0)
        return total

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        amount = instance.amount
        date_paid = instance.date_paid
        client = instance.client

        self.perform_destroy(instance)

        year = date_paid.year
        month = date_paid.month

        try:
            monthly = MonthlyRevenue.objects.get(year=year, month=month)
            monthly.total_amount = F("total_amount") - amount
            monthly.payment_count = F("payment_count") - 1
            monthly.save()
        except MonthlyRevenue.DoesNotExist:
            pass

        if not Payment.objects.filter(
            client=client, valid_until__gte=timezone.now().date()
        ).exists():
            client.status = "I"
            client.current_membership = None
            client.save(update_fields=["status", "current_membership"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="en-gracia")
    def clientes_en_gracia(self, request):
        today = timezone.now().date()
        response = []

        pagos_en_gracia = Payment.objects.filter(
            valid_until__lt=today, valid_until__gte=today - timedelta(days=7)
        ).select_related("client", "membership")

        vistos = set()

        for pago in pagos_en_gracia:
            client_id = pago.client.id
            if client_id in vistos:
                continue
            vistos.add(client_id)

            grace_ends = pago.valid_until + timedelta(days=7)

            response.append(
                {
                    "client": ClientSerializer(pago.client).data,
                    "membership": pago.membership.name,
                    "last_payment_date": pago.date_paid.date(),
                    "valid_until": pago.valid_until,
                    "grace_ends": grace_ends,
                    "can_renew_at_previous_price": True,
                }
            )

        return Response(response)

    @action(detail=True, methods=["put"], url_path="extend-vigencia")
    def extend_vigencia(self, request, pk=None):
        payment = self.get_object()
        today = timezone.now().date()

        if payment.valid_until >= today:
            return Response(
                {"detail": "El pago todavía está vigente. No es necesario extender."},
                status=400,
            )

        new_valid_until = today
        added_days = 0

        while added_days < 6:
            new_valid_until += timedelta(days=1)
            if new_valid_until.weekday() != 6:
                added_days += 1

        payment.valid_until = new_valid_until
        payment.save(update_fields=["valid_until"])

        return Response({"message": "Vigencia extendida exitosamente."})

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)

    # def get_queryset(self):
    #     queryset = Payment.objects.all().order_by("-date_paid")
    #     month_param = self.request.query_params.get("month")
    #     date_param = self.request.query_params.get("date")

    #     if date_param:
    #         try:
    #             parsed_date = parse_date(date_param)
    #             if parsed_date:
    #                 queryset = queryset.filter(date_paid__date=parsed_date)
    #         except Exception as e:
    #             print(f"Error al filtrar por fecha: {e}")
    #             pass
    #     elif month_param:
    #         try:
    #             year, month = map(int, month_param.split("-"))
    #             queryset = queryset.filter(date_paid__year=year, date_paid__month=month)
    #         except Exception as e:
    #             print(f"Error al filtrar por mes: {e}")
    #             pass

    #     return queryset


class VentaViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = Venta.objects.all().order_by("-date_sold")
    serializer_class = VentaSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["client"]
    ordering_fields = ["date_sold", "total_amount"]
    permission_classes = [IsAuthenticated, IsSedeOwnerOrReadOnly]
    ordering = ["-date_sold"]

    def perform_create(self, serializer):
        venta = serializer.save()
        date = venta.date_sold.date()
        year, month = date.year, date.month

        monthly, _ = MonthlyRevenue.objects.get_or_create(year=year, month=month)
        monthly.total_amount = F("total_amount") + venta.total_amount
        monthly.venta_total = F("venta_total") + venta.total_amount
        monthly.venta_count = F("venta_count") + 1
        monthly.save()
        serializer.save(created_by=self.request.user, modified_by=self.request.user)

    def perform_destroy(self, instance):
        date = instance.date_sold.date()
        amount = instance.total_amount
        year, month = date.year, date.month
        super().perform_destroy(instance)

        try:
            monthly = MonthlyRevenue.objects.get(year=year, month=month)
            monthly.total_amount = F("total_amount") - amount
            monthly.venta_total = F("venta_total") - amount
            monthly.venta_count = F("venta_count") - 1
            monthly.save()
        except MonthlyRevenue.DoesNotExist:
            pass

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)


class ScheduleViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = Schedule.objects.select_related("coach", "class_type").all()
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated, IsSedeOwnerOrReadOnly]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["day", "coach"]
    ordering_fields = ["day", "time_slot"]
    ordering = ["day", "time_slot"]

    @action(detail=False, methods=["get"], url_path="today")
    def get_today_classes(self, request):
        coach_id = request.query_params.get("coach_id")
        today = datetime.now().date()
        day_code = today.strftime("%a").upper()[:3]

        # El filtrado por sede se maneja automáticamente por SedeFilterMixin
        if coach_id:
            # Si se especifica un coach_id, mostrar solo sus clases
            schedules = (
                self.get_queryset()
                .filter(day=day_code, coach_id=coach_id)
                .order_by("time_slot")
            )
        elif (
            request.user.is_superuser
            or request.user.groups.filter(name__in=["admin", "secretaria"]).exists()
        ):
            # Secretarias y admins pueden ver TODAS las clases del día
            schedules = self.get_queryset().filter(day=day_code).order_by("time_slot")
        else:
            # Coaches solo ven sus propias clases
            schedules = (
                self.get_queryset()
                .filter(day=day_code, coach=request.user)
                .order_by("time_slot")
            )

        serializer = ScheduleWithBookingsSerializer(
            schedules, many=True, context={"request": request, "today": today}
        )
        return Response(serializer.data)


class MonthlyRevenueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MonthlyRevenue.objects.all()
    serializer_class = MonthlyRevenueSerializer
    permission_classes = [IsAuthenticated, SedeAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["year", "month"]
    ordering_fields = ["year", "month"]
    ordering = ["-year", "-month"]

    @action(detail=False, methods=["post"], url_path="recalculate")
    def recalculate(self, request):
        year = request.data.get("year")
        month = request.data.get("month")
        if not year or not month:
            return Response({"error": "Se requiere 'year' y 'month'."}, status=400)

        try:
            result = recalculate_monthly_revenue(int(year), int(month))
            return Response(
                {"message": "Resumen mensual recalculado exitosamente.", "data": result}
            )
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=["post"], url_path="recalculate-all")
    def recalculate_all(self, request):
        try:
            result = recalculate_all_monthly_revenue()
            return Response(
                {
                    "message": "Todos los resúmenes mensuales recalculados exitosamente.",
                    "data": result,
                }
            )
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=["get"], url_path="total")
    def total_revenue(self, request):
        from django.db.models import Sum

        total = (
            MonthlyRevenue.objects.aggregate(total=Sum("total_amount"))["total"] or 0
        )
        return Response({"total_revenue": float(total)})


@api_view(["GET"])
def get_today_payments_total(request):
    today = localtime(now()).date()
    payments = Payment.objects.filter(date_paid__date=today)
    
    # Apply sede filtering if sede_ids are provided
    if hasattr(request, "sede_ids") and request.sede_ids:
        payments = payments.filter(sede_id__in=request.sede_ids)
    
    total = sum(p.amount for p in payments)
    return Response(
        {"date": today, "total": round(total, 2), "count": payments.count()}
    )


@api_view(["GET"])
def summary_by_class_type(request):
    from .models import Booking

    bookings = Booking.objects.select_related("schedule__class_type").all()
    
    # Apply sede filtering if sede_ids are provided
    if hasattr(request, "sede_ids") and request.sede_ids:
        bookings = bookings.filter(schedule__sede_id__in=request.sede_ids)
    
    counter = Counter()

    for b in bookings:
        if b.schedule and b.schedule.class_type:
            name = b.schedule.class_type.name
            counter[name] += 1

    data = [{"class_type": k, "count": v} for k, v in counter.items()]
    return Response(data)


@api_view(["GET"])
def attendance_summary(request):
    from datetime import timedelta

    from django.utils.timezone import now

    from .models import Booking

    today = now().date()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    bookings = Booking.objects.filter(
        class_date__range=[start_week, end_week], attendance_status="attended"
    )
    
    # Apply sede filtering if sede_ids are provided
    if hasattr(request, "sede_ids") and request.sede_ids:
        bookings = bookings.filter(schedule__sede_id__in=request.sede_ids)

    summary = Counter(b.class_date.strftime("%A") for b in bookings)
    return Response(summary)


# studio/views.py
@api_view(["GET"])
def closure_full_summary(request):
    """
    Endpoint que devuelve métricas diarias, semanales y mensuales.
    Parámetros GET opcionales:
      - year  (int: p.ej. 2025)
      - month (int: 1-12) o 'YYYY-MM'
    Si no se pasan ni year ni month, devuelve datos globales
    y también el histórico diario y semanal.
    """
    raw_year = request.query_params.get("year")
    raw_month = request.query_params.get("month")

    # 1) Determinar rango de fechas
    if not raw_year and not raw_month:
        # global: desde primer pago o booking hasta hoy
        first_dates = []
        first_payment = Payment.objects.order_by("date_paid").first()
        if first_payment and first_payment.date_paid:
            first_dates.append(first_payment.date_paid.date())
        first_booking = Booking.objects.order_by("class_date").first()
        if first_booking and first_booking.class_date:
            first_dates.append(first_booking.class_date)
        first_day = min(first_dates) if first_dates else tz_now().date()
        last_day = tz_now().date()
    else:
        # específico mes/año
        if raw_month and "-" in raw_month:
            year, month = map(int, raw_month.split("-"))
        else:
            year = int(raw_year) if raw_year else tz_now().year
            month = int(raw_month) if raw_month else tz_now().month
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

    # 2) Construir lista diaria
    daily = []
    current = first_day
    while current <= last_day:
        qs = Booking.objects.filter(class_date=current, attendance_status="attended")
        daily.append(
            {
                "fecha": current.isoformat(),
                "asistencias": qs.count(),
                "pruebas": qs.filter(client__trial_used=True).count(),
                "paquetes_vendidos": qs.filter(client__trial_used=False).count(),
                "clases_individuales": qs.filter(schedule__is_individual=True).count(),
            }
        )
        current += timedelta(days=1)

    # 3) Añadir pagos y ventas a cada día
    for entry in daily:
        dt = date.fromisoformat(entry["fecha"])
        pagos = Payment.objects.filter(date_paid__date=dt)
        total_pagos = pagos.aggregate(Sum("amount"))["amount__sum"] or 0
        visalink = (
            pagos.filter(payment_method__iexact="VisaLink").aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        efectivo = (
            pagos.filter(payment_method__iexact="Efectivo").aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        visalink = (
            pagos.filter(payment_method__iexact="Visalink").aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        entry["total_pagos"] = total_pagos
        entry["visalink"] = visalink
        entry["efectivo"] = efectivo
        entry["visalink"] = visalink
        entry["transferencia"] = total_pagos - (visalink + efectivo + visalink)

        ventas = Venta.objects.filter(date_sold__date=dt)
        ventas_sum = ventas.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        entry["ventas"] = ventas_sum
        entry["total"] = total_pagos + ventas_sum

    # 4) Agrupar en semanas de lunes (0) a sábado (5)
    weekly = []
    week_idx = 1

    # Función para obtener el lunes de una semana
    def get_monday_of_week(target_date):
        days_since_monday = target_date.weekday()
        return target_date - timedelta(days=days_since_monday)

    # Función para obtener el sábado de una semana
    def get_saturday_of_week(target_date):
        days_until_saturday = 5 - target_date.weekday()
        return target_date + timedelta(days=days_until_saturday)

    # Generar semanas (Lunes a Sábado)
    current_date = get_monday_of_week(first_day)

    while current_date <= last_day:
        week_end = get_saturday_of_week(current_date)

        # Ajustar si el sábado excede el rango
        if week_end > last_day:
            week_end = last_day

        # Inicializar datos de la semana
        week_data = {
            "week": week_idx,
            "start": current_date,
            "end": week_end,
            "asistencias": 0,
            "pruebas": 0,
            "paquetes_vendidos": 0,
            "clases_individuales": 0,
            "visalink": 0,
            "efectivo": 0,
            "visalink": 0,
            "transferencia": 0,
            "ventas": 0,
            "total": 0,
        }

        # Sumar valores de cada día de la semana
        temp_date = current_date
        while temp_date <= week_end:
            iso = temp_date.isoformat()
            entry = next((d for d in daily if d["fecha"] == iso), None)
            if entry:
                for k in [
                    "asistencias",
                    "pruebas",
                    "paquetes_vendidos",
                    "clases_individuales",
                    "visalink",
                    "efectivo",
                    "visalink",
                    "transferencia",
                    "ventas",
                    "total",
                ]:
                    week_data[k] += entry[k]
            temp_date += timedelta(days=1)

        # Agregar semana a la lista
        weekly.append(
            {
                "week": week_data["week"],
                "rango": f"{week_data['start'].strftime('%d/%m/%Y')} - {week_data['end'].strftime('%d/%m/%Y')}",
                **{
                    k: week_data[k]
                    for k in [
                        "asistencias",
                        "pruebas",
                        "paquetes_vendidos",
                        "clases_individuales",
                        "visalink",
                        "efectivo",
                        "visalink",
                        "transferencia",
                        "ventas",
                        "total",
                    ]
                },
            }
        )

        # Avanzar a la siguiente semana (lunes)
        current_date += timedelta(days=7)
        week_idx += 1

    # 5) Resumen global o mensual
    if not raw_year and not raw_month:
        # resumen global por SQL
        total_pagos = Payment.objects.aggregate(Sum("amount"))["amount__sum"] or 0
        visalink = (
            Payment.objects.filter(payment_method__iexact="VisaLink").aggregate(
                Sum("amount")
            )["amount__sum"]
            or 0
        )
        efectivo = (
            Payment.objects.filter(payment_method__iexact="Efectivo").aggregate(
                Sum("amount")
            )["amount__sum"]
            or 0
        )
        visalink = (
            Payment.objects.filter(payment_method__iexact="Visalink").aggregate(
                Sum("amount")
            )["amount__sum"]
            or 0
        )
        transferencia = total_pagos - (visalink + efectivo + visalink)
        total_ventas = (
            Venta.objects.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        )

        summary = {
            "visalink": visalink,
            "efectivo": efectivo,
            "visalink": visalink,
            "transferencia": transferencia,
            "ventas": total_ventas,
            "total_pagos": total_pagos,
            "total": total_pagos + total_ventas,
        }
    else:
        # resumen mensual sumando daily
        summary = {
            k: sum(d[k] for d in daily)
            for k in [
                "visalink",
                "efectivo",
                "visalink",
                "transferencia",
                "ventas",
                "total",
            ]
        }

    return Response(
        {
            "daily": daily,
            "weekly": weekly,
            "summary": summary,
        }
    )


class PromotionViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = Promotion.objects.all().order_by("-start_date")
    serializer_class = PromotionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["membership", "start_date", "end_date"]


class PromotionInstanceViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = PromotionInstance.objects.all().order_by("-created_at")
    serializer_class = PromotionInstanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["promotion", "created_at"]

    @action(detail=True, methods=["post"], url_path="confirm-payment")
    def confirm_payment(self, request, pk=None):
        instance = self.get_object()
        client_id = request.data.get("client_id")

        if not client_id:
            return Response({"detail": "Falta el ID del cliente."}, status=400)

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "Cliente no encontrado."}, status=404)

        today = timezone.now().date()
        promotion = instance.promotion
        membership = promotion.membership
        amount = promotion.price
        valid_until = today + timedelta(days=30)

        # Crear el pago vinculado a esta instancia
        payment = Payment.objects.create(
            client=client,
            membership=membership,
            promotion=promotion,
            promotion_instance=instance,
            amount=amount,
            date_paid=timezone.now(),
            valid_until=valid_until,
        )

        # Activar cliente si aplica
        if valid_until >= today and client.status != "A":
            client.status = "A"
            client.save(update_fields=["status"])

        # Confirmar plan intent si aplica (reutiliza tu lógica actual)
        try:
            plan_intent = PlanIntent.objects.filter(
                client=client, membership=membership, is_confirmed=False
            ).latest("selected_at")
            plan_intent.is_confirmed = True
            plan_intent.save()
        except PlanIntent.DoesNotExist:
            pass

        # Recalcular ingresos mensuales
        year = payment.date_paid.year
        month = payment.date_paid.month
        revenue, _ = MonthlyRevenue.objects.get_or_create(year=year, month=month)
        revenue.total_amount = F("total_amount") + payment.amount
        revenue.payment_count = F("payment_count") + 1
        revenue.save()

        # Correo opcional
        try:
            send_subscription_confirmation_email(payment)
        except Exception as e:
            print(f"Error al enviar correo: {e}")

        return Response(PaymentSerializer(payment).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_bookings_by_month(request):
    """
    Devuelve TODAS las reservas del cliente autenticado para un mes dado (sin paginado).
    Parámetros (query):
      - year: YYYY  (opcional; default: año actual segun TIME_ZONE)
      - month: 1..12 (opcional; default: mes actual)
      - status: 'active', 'cancelled', 'pending' (opcional; puede ser coma-separado: e.g. 'active,cancelled')
      - order: 'asc' | 'desc' (opcional; default: 'asc' por fecha)
    Respuesta:
    {
      "year": 2025,
      "month": 8,
      "month_label": "Agosto 2025",
      "count": 5,
      "results": [ BookingMiniSerializer... ]
    }
    """
    # Buscar cliente por email del usuario (más confiable)
    client = Client.objects.filter(email__iexact=request.user.email).first()
    if not client:
        # Si no encuentra por email, intentar por username
        client = Client.objects.filter(email__iexact=request.user.username).first()
        if not client:
            return Response(
                {"detail": "Usuario no encontrado", "code": "user_not_found"},
                status=404,
            )

    now_local = timezone.localtime(timezone.now())
    try:
        year = int(request.query_params.get("year", now_local.year))
        month = int(request.query_params.get("month", now_local.month))
        if month < 1 or month > 12:
            raise ValueError
    except ValueError:
        return Response(
            {
                "detail": "Parámetros inválidos: 'year' debe ser YYYY y 'month' entre 1..12."
            },
            status=400,
        )

    # Rango del mes
    last_day = monthrange(year, month)[1]
    first_date = date(year, month, 1)
    last_date = date(year, month, last_day)

    # Base query
    qs = Booking.objects.select_related(
        "schedule", "schedule__class_type", "membership"
    ).filter(client=client, class_date__gte=first_date, class_date__lte=last_date)

    # Filtrar por status si se especifica (soporta varios separados por coma)
    allowed_status = {"active", "cancelled", "pending"}
    status_param = request.query_params.get("status")
    if status_param:
        raw_list = [s.strip().lower() for s in status_param.split(",") if s.strip()]
        chosen = [s for s in raw_list if s in allowed_status]
        if chosen:
            qs = qs.filter(status__in=chosen)

    # Orden
    order = (request.query_params.get("order") or "asc").lower()
    if order == "desc":
        qs = qs.order_by("-class_date", "-date_booked")
    else:
        qs = qs.order_by("class_date", "date_booked")

    # Serializar
    results = BookingMiniSerializer(qs, many=True).data

    # Etiqueta del mes en español
    meses = [
        "",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    month_label = f"{meses[month].capitalize()} {year}"

    return Response(
        {
            "year": year,
            "month": month,
            "month_label": month_label,
            "count": len(results),
            "results": results,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_authenticated_booking(request):
    """
    Endpoint para que usuarios autenticados creen sus propias reservas.
    Solo requiere schedule_id, class_date y membership_id (opcional).
    """
    # Buscar cliente por email del usuario (más confiable)
    client = Client.objects.filter(email__iexact=request.user.email).first()
    if not client:
        return Response(
            {"detail": "Usuario no encontrado", "code": "user_not_found"}, status=404
        )

    schedule_id = request.data.get("schedule_id")
    class_date = request.data.get("class_date")
    membership_id = request.data.get("membership_id")

    if not schedule_id or not class_date:
        return Response(
            {"detail": "Se requieren schedule_id y class_date."}, status=400
        )

    try:
        schedule = Schedule.objects.get(pk=schedule_id)
    except Schedule.DoesNotExist:
        return Response({"detail": "Horario no encontrado."}, status=404)

    # Validar que la fecha no sea en el pasado
    try:
        booking_date = parse_date(class_date)
        if not booking_date:
            return Response({"detail": "Formato de fecha inválido."}, status=400)

        if booking_date < timezone.now().date():
            return Response(
                {"detail": "No se pueden hacer reservas para fechas pasadas."},
                status=400,
            )
    except Exception as e:
        print(f"Error al validar la fecha: {e}")
        return Response({"detail": "Formato de fecha inválido."}, status=400)

    # Verificar si ya existe una reserva para este cliente en este horario y fecha
    existing_booking = Booking.objects.filter(
        client=client, schedule=schedule, class_date=booking_date
    ).first()

    if existing_booking:
        return Response(
            {"detail": "Ya tienes una reserva para este horario en esta fecha."},
            status=400,
        )

    # Verificar cupo disponible
    current_bookings = (
        Booking.objects.filter(
            schedule=schedule, class_date=booking_date, status="active"
        )
        .exclude(attendance_status="cancelled")
        .count()
    )

    if current_bookings >= schedule.capacity:
        return Response(
            {"detail": "No hay cupo disponible para este horario."}, status=400
        )

    # Procesar la reserva según el tipo
    membership = None
    if membership_id:
        try:
            membership = Membership.objects.get(pk=membership_id)
        except Membership.DoesNotExist:
            return Response({"detail": "Membresía no encontrada."}, status=400)

    # Crear la reserva
    try:
        # Get sede from schedule or request headers
        sede_id = schedule.sede_id if schedule.sede_id else request.headers.get('X-Sede-ID')
        
        if membership and membership.id == 1:  # Clase individual
            booking = Booking.objects.create(
                client=client,
                schedule=schedule,
                class_date=booking_date,
                membership=membership,
                status="pending",
                sede_id=sede_id,
            )
            # Send pending payment email
            try:
                send_individual_booking_pending_email(booking)
                print(f"Pending payment email sent for booking {booking.id}")
            except Exception as e:
                print(f"Error sending pending payment email: {e}")
            return Response(
                {
                    "detail": "Tu reserva para la clase individual está pendiente de confirmación. Realiza el depósito del 40% (aprox. Q36) para confirmar tu clase.",
                    "booking_id": booking.id,
                },
                status=201,
            )

        elif not client.trial_used:  # Clase de prueba gratuita
            booking = Booking.objects.create(
                client=client,
                schedule=schedule,
                class_date=booking_date,
                status="active",
                attendance_status="pending",
                sede_id=sede_id,
            )
            client.trial_used = True
            client.save(update_fields=["trial_used"])
            # Send confirmation email
            try:
                send_booking_confirmation_email(booking, client)
                print(f"Confirmation email sent for trial booking {booking.id}")
            except Exception as e:
                print(f"Error sending confirmation email: {e}")
            return Response(
                {
                    "detail": "¡Reserva confirmada! Esta es tu clase de prueba gratuita.",
                    "booking_id": booking.id,
                },
                status=201,
            )

        else:  # Cliente con membresía
            # Verificar si tiene membresía activa
            if not client.active_membership and client.trial_used:
                return Response(
                    {
                        "detail": "No tienes una membresía activa y ya usaste tu clase de prueba gratuita. Por favor adquiere un plan para continuar."
                    },
                    status=400,
                )

            # Verificar límite de clases según membresía
            today = timezone.now().date()
            latest_payment = (
                Payment.objects.filter(
                    client=client, 
                    valid_from__lte=today, 
                    valid_until__gte=today
                )
                .order_by("-valid_until")
                .first()
            )

            if not latest_payment:
                return Response(
                    {
                        "detail": "No tienes una membresía activa. Por favor adquiere un plan para continuar."
                    },
                    status=400,
                )

            # Contar clases usadas este mes
            month_start = date(today.year, today.month, 1)
            month_end = date(
                today.year, today.month, monthrange(today.year, today.month)[1]
            )

            classes_used = (
                Booking.objects.filter(
                    client=client,
                    class_date__gte=month_start,
                    class_date__lte=month_end,
                    status="active",
                )
                .exclude(attendance_status="cancelled")
                .count()
            )

            if (
                latest_payment.membership.classes_per_month
                and classes_used >= latest_payment.membership.classes_per_month
            ):
                return Response(
                    {
                        "detail": "Ya has usado todas las clases de tu membresía este mes."
                    },
                    status=400,
                )

            booking = Booking.objects.create(
                client=client,
                schedule=schedule,
                class_date=booking_date,
                membership=latest_payment.membership,
                status="active",
                attendance_status="pending",
                sede_id=sede_id,
            )

            # Send confirmation email
            try:
                send_booking_confirmation_email(booking, client)
                print(f"Confirmation email sent for membership booking {booking.id}")
            except Exception as e:
                print(f"Error sending confirmation email: {e}")

            return Response(
                {"detail": "¡Reserva confirmada!", "booking_id": booking.id}, status=201
            )

    except Exception as e:
        return Response({"detail": f"Error al crear la reserva: {str(e)}"}, status=500)


class BulkBookingViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    """ViewSet for handling bulk bookings with tracking"""

    permission_classes = [IsAuthenticated, IsSedeOwnerOrReadOnly]
    queryset = BulkBooking.objects.all()
    serializer_class = BulkBookingSerializer

    @action(detail=False, methods=["post"], url_path="create-multiple")
    def create_multiple(self, request):
        """Create multiple bookings at once with tracking"""
        from .serializers import BulkBookingRequestSerializer

        serializer = BulkBookingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        client_id = serializer.validated_data["client_id"]
        bookings_data = serializer.validated_data["bookings"]
        number_of_slots = serializer.validated_data.get("number_of_slots", 1)

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response(
                {"detail": "Cliente no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )

        # Create bulk booking record
        bulk_booking = BulkBooking.objects.create(
            client=client, total_bookings=len(bookings_data), status="processing"
        )

        successful_bookings = []
        failed_bookings = []
        errors = []

        # Process each booking
        for booking_data in bookings_data:
            try:
                with transaction.atomic():
                    # Validate schedule exists
                    try:
                        schedule = Schedule.objects.get(id=booking_data["schedule_id"])
                    except Schedule.DoesNotExist:
                        failed_bookings.append(
                            {
                                "schedule_id": booking_data["schedule_id"],
                                "class_date": booking_data["class_date"],
                                "error": "Horario no encontrado",
                            }
                        )
                        errors.append(
                            f"Horario {booking_data['schedule_id']} no encontrado"
                        )
                        continue

                    # Parse class date
                    try:
                        class_date = datetime.strptime(
                            booking_data["class_date"], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        failed_bookings.append(
                            {
                                "schedule_id": booking_data["schedule_id"],
                                "class_date": booking_data["class_date"],
                                "error": "Formato de fecha inválido",
                            }
                        )
                        errors.append(f"Fecha inválida: {booking_data['class_date']}")
                        continue

                    # Check capacity
                    current_bookings = (
                        Booking.objects.filter(
                            schedule=schedule, class_date=class_date, status="active"
                        )
                        .exclude(attendance_status="cancelled")
                        .count()
                    )

                    available_slots = schedule.capacity - current_bookings

                    if available_slots <= 0:
                        failed_bookings.append(
                            {
                                "schedule_id": booking_data["schedule_id"],
                                "class_date": booking_data["class_date"],
                                "error": "No hay cupo disponible",
                            }
                        )
                        errors.append(f"No hay cupo para {schedule} el {class_date}")
                        continue

                    # Check if requested slots exceed available capacity
                    if number_of_slots > available_slots:
                        failed_bookings.append(
                            {
                                "schedule_id": booking_data["schedule_id"],
                                "class_date": booking_data["class_date"],
                                "error": f"Solo hay {available_slots} cupos disponibles, se solicitaron {number_of_slots}",
                            }
                        )
                        errors.append(
                            f"Solo hay {available_slots} cupos disponibles para {schedule} el {class_date}, se solicitaron {number_of_slots}"
                        )
                        continue

                    # Check if booking already exists
                    if Booking.objects.filter(
                        client=client, schedule=schedule, class_date=class_date
                    ).exists():
                        failed_bookings.append(
                            {
                                "schedule_id": booking_data["schedule_id"],
                                "class_date": booking_data["class_date"],
                                "error": "Ya tienes una reserva para esta clase",
                            }
                        )
                        errors.append(
                            f"Reserva duplicada para {schedule} el {class_date}"
                        )
                        continue

                    # Create the booking
                    booking = Booking.objects.create(
                        client=client,
                        schedule=schedule,
                        class_date=class_date,
                        bulk_booking=bulk_booking,
                    )

                    # Handle membership and payment logic (simplified version)
                    # This follows the same logic as the single booking creation
                    selected_membership = request.data.get("membership_id")

                    if selected_membership == 1:  # Individual class
                        booking.membership = Membership.objects.get(pk=1)
                        booking.status = "pending"
                        booking.save()
                        # No enviar correo individual, se enviará al final
                    elif not client.trial_used:
                        # Trial class
                        client.trial_used = True
                        client.save(update_fields=["trial_used"])
                        # No enviar correo individual, se enviará al final
                    else:
                        # Check active membership
                        today = now().date()
                        latest_payment = (
                            Payment.objects.filter(
                                client=client,
                                valid_from__lte=today,
                                valid_until__gte=today,
                            )
                            .order_by("-valid_until")
                            .first()
                        )

                        if latest_payment:
                            # Validate class limits
                            membership_plan = latest_payment.membership
                            total_permitidas = 0

                            if latest_payment.promotion_id:
                                promotion = latest_payment.promotion
                                promo_instance = (
                                    PromotionInstance.objects.filter(
                                        promotion=promotion, clients=client
                                    )
                                    .order_by("-created_at")
                                    .first()
                                )

                                if promo_instance and promo_instance.is_active():
                                    total_permitidas = (
                                        promotion.clases_por_cliente or 0
                                    ) + (latest_payment.extra_classes or 0)
                            elif membership_plan and membership_plan.classes_per_month:
                                total_permitidas = membership_plan.classes_per_month + (
                                    latest_payment.extra_classes or 0
                                )

                            if total_permitidas > 0:
                                monthly_bookings = (
                                    Booking.objects.filter(
                                        client=client,
                                        status="active",
                                        payment=latest_payment,
                                    )
                                    .filter(
                                        Q(attendance_status="attended")
                                        | Q(
                                            attendance_status="pending",
                                            class_date__gte=today,
                                        )
                                    )
                                    .count()
                                )

                                if monthly_bookings >= total_permitidas:
                                    # Remove the booking if limit exceeded
                                    booking.delete()
                                    failed_bookings.append(
                                        {
                                            "schedule_id": booking_data["schedule_id"],
                                            "class_date": booking_data["class_date"],
                                            "error": "Has alcanzado tu límite de clases",
                                        }
                                    )
                                    errors.append(
                                        f"Límite de clases alcanzado para {schedule} el {class_date}"
                                    )
                                    continue

                            # Set payment and membership
                            booking.payment = latest_payment
                            booking.membership = membership_plan
                            booking.save()
                            # No enviar correo individual, se enviará al final
                        else:
                            # No active membership and trial already used - remove booking
                            if client.trial_used:
                                booking.delete()
                                failed_bookings.append(
                                    {
                                        "schedule_id": booking_data["schedule_id"],
                                        "class_date": booking_data["class_date"],
                                        "error": "No tienes una membresía activa y ya usaste tu clase de prueba gratuita",
                                    }
                                )
                                errors.append(
                                    f"Sin membresía activa y trial usado para {schedule} el {class_date}"
                                )
                                continue
                            else:
                                # Allow trial class
                                booking.status = "active"
                                booking.attendance_status = "pending"
                                booking.save()

                    successful_bookings.append(
                        {
                            "id": booking.id,
                            "schedule": str(schedule),
                            "class_date": booking_data["class_date"],
                            "status": booking.status,
                        }
                    )

            except Exception as e:
                failed_bookings.append(
                    {
                        "schedule_id": booking_data["schedule_id"],
                        "class_date": booking_data["class_date"],
                        "error": str(e),
                    }
                )
                errors.append(f"Error al crear reserva: {str(e)}")

        # Update bulk booking status
        bulk_booking.successful_bookings = len(successful_bookings)
        bulk_booking.failed_bookings = len(failed_bookings)
        bulk_booking.update_status()

        # Send bulk confirmation email if there are successful bookings
        if successful_bookings:
            try:
                from .management.mails.mails import send_bulk_booking_confirmation_email

                # Get all successful booking objects
                successful_booking_objects = bulk_booking.bookings.filter(
                    id__in=[b["id"] for b in successful_bookings]
                )
                send_bulk_booking_confirmation_email(client, successful_booking_objects)
                print(
                    f"Bulk confirmation email sent for {len(successful_booking_objects)} bookings"
                )
            except Exception as e:
                print(f"Error sending bulk confirmation email: {e}")

        # Prepare response
        result_data = {
            "bulk_booking_id": bulk_booking.id,
            "status": bulk_booking.status,
            "total_requested": len(bookings_data),
            "successful": len(successful_bookings),
            "failed": len(failed_bookings),
            "successful_bookings": successful_bookings,
            "failed_bookings": failed_bookings,
        }

        if errors:
            result_data["errors"] = errors

        serializer = BulkBookingResultSerializer(result_data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        """Get summary of a bulk booking"""
        try:
            bulk_booking = self.get_object()
            return Response(
                {
                    "id": bulk_booking.id,
                    "client": str(bulk_booking.client),
                    "status": bulk_booking.status,
                    "total_bookings": bulk_booking.total_bookings,
                    "successful_bookings": bulk_booking.successful_bookings,
                    "failed_bookings": bulk_booking.failed_bookings,
                    "created_at": bulk_booking.created_at,
                    "bookings": BookingSerializer(
                        bulk_booking.bookings.all(), many=True
                    ).data,
                }
            )
        except BulkBooking.DoesNotExist:
            return Response(
                {"detail": "Bulk booking no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )


class SedeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing sedes (sites) in the multisite system.
    """

    queryset = Sede.objects.all()
    serializer_class = SedeSerializer
    permission_classes = [
        permissions.AllowAny
    ]  # Changed to AllowAny for frontend access
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    @action(detail=False, methods=["get"], url_path="active")
    def active_sedes(self, request):
        """Get only active sedes."""
        active_sedes = Sede.objects.filter(status=True)
        serializer = self.get_serializer(active_sedes, many=True)
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_dashboard_data(request):
    """Endpoint optimizado para datos del dashboard - solo datos agregados"""
    try:
        # from django.db.models.functions import TruncDate, TruncMonth

        sede_ids = request.GET.getlist("sede_ids[]")
        sede_headers = request.headers.get("X-Sedes-Selected", "")
        sede_id_header = request.headers.get("X-Sede-ID", "")

        # Si hay sede_ids en headers, usarlos
        if sede_headers:
            sede_ids = sede_headers.split(",")
        elif sede_id_header:
            # Nuevo header X-Sede-ID para sede individual
            sede_ids = [sede_id_header]

        # Si no hay sede_ids, usar todas las sedes del usuario
        if not sede_ids:
            sede_ids = [str(sede.id) for sede in Sede.objects.filter(status=True)]

        # Convertir a enteros
        try:
            sede_ids = [int(sede_id) for sede_id in sede_ids if sede_id.strip()]
        except ValueError:
            return Response({"error": "IDs de sede inválidos"}, status=400)

        today = timezone.now().date()
        current_month = today.month
        current_year = today.year

        # Métricas básicas
        today_bookings = Booking.objects.filter(
            sede_id__in=sede_ids, class_date=today
        ).count()

        # Ingresos de hoy
        today_revenue = (
            Payment.objects.filter(
                sede_id__in=sede_ids, date_paid__date=today
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        # Clientes activos (con membresía activa)
        active_clients = (
            Client.objects.filter(
                sede_id__in=sede_ids, current_membership__isnull=False, status="A"
            )
            .distinct()
            .count()
        )

        # Calcular total de clientes activos para porcentajes
        total_active_clients = active_clients

        # Nuevos clientes este mes
        new_clients = Client.objects.filter(
            sede_id__in=sede_ids,
            created_at__year=current_year,
            created_at__month=current_month,
        ).count()

        # Ingresos del mes actual
        monthly_revenue = (
            Payment.objects.filter(
                sede_id__in=sede_ids,
                date_paid__year=current_year,
                date_paid__month=current_month,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        # Ingresos totales históricos
        total_revenue = (
            Payment.objects.filter(sede_id__in=sede_ids).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )

        # Reservas por día (últimos 15 días)
        daily_bookings = []
        for i in range(14, -1, -1):
            date = today - timedelta(days=i)
            count = Booking.objects.filter(
                sede_id__in=sede_ids, class_date=date
            ).count()
            daily_bookings.append({"date": date.strftime("%d/%m"), "count": count})

        # Estadísticas de asistencia
        attendance_stats = (
            Booking.objects.filter(sede_id__in=sede_ids)
            .values("attendance_status")
            .annotate(count=Count("id"))
        )

        attendance_dict = {
            item["attendance_status"]: item["count"] for item in attendance_stats
        }

        # Ingresos diarios (últimos 30 días)
        daily_revenue = []
        for i in range(29, -1, -1):
            date = today - timedelta(days=i)
            revenue = (
                Payment.objects.filter(
                    sede_id__in=sede_ids, date_paid__date=date
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )
            daily_revenue.append(
                {"date": date.strftime("%d/%m"), "amount": float(revenue)}
            )

        # Métodos de pago
        payment_methods = (
            Payment.objects.filter(sede_id__in=sede_ids)
            .values("payment_method")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Pagos recientes (solo los últimos 10)
        recent_payments = (
            Payment.objects.filter(sede_id__in=sede_ids)
            .select_related("client", "membership")
            .order_by("-date_paid")[:10]
        )

        recent_payments_data = []
        for payment in recent_payments:
            recent_payments_data.append(
                {
                    "client_name": f"{payment.client.first_name or ''} {payment.client.last_name or ''}".strip(),
                    "membership_name": (
                        payment.membership.name if payment.membership else "N/A"
                    ),
                    "amount": float(payment.amount),
                    "date_paid": payment.date_paid.strftime("%d/%m/%Y"),
                    "payment_method": payment.payment_method or "Efectivo",
                    "valid_until": (
                        payment.valid_until.strftime("%d/%m/%Y")
                        if payment.valid_until
                        else "N/A"
                    ),
                }
            )

        # Ingresos mensuales con crecimiento
        monthly_revenue_data = []
        for i in range(12, 0, -1):
            month_date = today - timedelta(days=30 * i)
            month = month_date.month
            year = month_date.year

            revenue = (
                Payment.objects.filter(
                    sede_id__in=sede_ids, date_paid__year=year, date_paid__month=month
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )

            payment_count = Payment.objects.filter(
                sede_id__in=sede_ids, date_paid__year=year, date_paid__month=month
            ).count()

            # Calcular crecimiento
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1

            prev_revenue = (
                Payment.objects.filter(
                    sede_id__in=sede_ids,
                    date_paid__year=prev_year,
                    date_paid__month=prev_month,
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )

            growth = 0
            if prev_revenue > 0:
                growth = ((revenue - prev_revenue) / prev_revenue) * 100

            monthly_revenue_data.append(
                {
                    "year": year,
                    "month": month,
                    "month_name": calendar.month_name[month],
                    "total_amount": float(revenue),
                    "payment_count": payment_count,
                    "average_payment": (
                        float(revenue / payment_count) if payment_count > 0 else 0
                    ),
                    "growth": growth,
                }
            )

        return Response(
            {
                # Métricas básicas
                "todayBookings": today_bookings,
                "todayRevenue": float(today_revenue),
                "activeClients": active_clients,
                "newClients": new_clients,
                "monthlyRevenue": float(monthly_revenue),  # noqa: F601
                "totalRevenue": float(total_revenue),
                # Datos de reservas
                "dailyBookings": daily_bookings,
                "attendanceStats": {
                    "attended": attendance_dict.get("attended", 0),
                    "no_show": attendance_dict.get("no_show", 0),
                    "cancelled": attendance_dict.get("cancelled", 0),
                },
                "timeSlotStats": [
                    {
                        "time_slot": "05:00-06:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="05:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "06:00-07:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="06:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "07:00-08:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="07:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "08:00-09:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="08:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "09:00-10:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="09:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "10:00-11:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="10:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "11:00-12:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="11:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "12:00-13:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="12:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "16:00-17:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="16:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "17:00-18:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="17:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "18:00-19:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="18:00",
                            status="active",
                        ).count(),
                    },
                    {
                        "time_slot": "19:00-20:00",
                        "count": Booking.objects.filter(
                            sede_id__in=sede_ids,
                            schedule__time_slot="19:00",
                            status="active",
                        ).count(),
                    },
                ],
                # Datos de pagos
                "dailyRevenue": daily_revenue,
                "paymentMethods": [
                    {
                        "method": item["payment_method"] or "Efectivo",
                        "count": item["count"],
                    }
                    for item in payment_methods
                ],
                "recentPayments": recent_payments_data,
                "monthlyRevenue": monthly_revenue_data,  # noqa: F601
                # Datos de clientes (mock por ahora)
                "ageGroups": [
                    {"range": "18-25", "count": int(active_clients * 0.2)},
                    {"range": "26-35", "count": int(active_clients * 0.4)},
                    {"range": "36-45", "count": int(active_clients * 0.3)},
                    {"range": "46+", "count": int(active_clients * 0.1)},
                ],
                "clientStatus": {
                    "active": active_clients,
                    "inactive": int(active_clients * 0.1),
                    "new": new_clients,
                    "at_risk": int(active_clients * 0.05),
                },
                "topClients": [
                    {
                        "name": f"{client.first_name} {client.last_name}",
                        "email": client.email or "N/A",
                        "membership_name": (
                            client.current_membership.name
                            if client.current_membership
                            else "Sin membresía"
                        ),
                        "classes_taken": Booking.objects.filter(
                            client=client,
                            sede_id__in=sede_ids,
                            attendance_status="attended",
                        ).count(),
                        "last_visit": (
                            Booking.objects.filter(
                                client=client,
                                sede_id__in=sede_ids,
                                attendance_status="attended",
                            )
                            .order_by("-class_date")
                            .first()
                            .class_date.strftime("%d/%m/%Y")
                            if Booking.objects.filter(
                                client=client,
                                sede_id__in=sede_ids,
                                attendance_status="attended",
                            ).exists()
                            else "N/A"
                        ),
                        "status": "active" if client.status == "A" else "inactive",
                        "total_value": Payment.objects.filter(
                            client=client, sede_id__in=sede_ids
                        ).aggregate(total=Sum("amount"))["total"]
                        or 0,
                    }
                    for client in Client.objects.filter(sede_id__in=sede_ids).order_by(
                        "-created_at"
                    )[:10]
                ],
                "clientsAtRisk": [
                    {
                        "name": f"{client.first_name} {client.last_name}",
                        "email": client.email or "N/A",
                        "membership_name": (
                            client.current_membership.name
                            if client.current_membership
                            else "Sin membresía"
                        ),
                        "last_visit": (
                            Booking.objects.filter(
                                client=client,
                                sede_id__in=sede_ids,
                                attendance_status="attended",
                            )
                            .order_by("-class_date")
                            .first()
                            .class_date.strftime("%d/%m/%Y")
                            if Booking.objects.filter(
                                client=client,
                                sede_id__in=sede_ids,
                                attendance_status="attended",
                            ).exists()
                            else "N/A"
                        ),
                        "days_since_visit": (
                            (
                                today
                                - Booking.objects.filter(
                                    client=client,
                                    sede_id__in=sede_ids,
                                    attendance_status="attended",
                                )
                                .order_by("-class_date")
                                .first()
                                .class_date
                            ).days
                            if Booking.objects.filter(
                                client=client,
                                sede_id__in=sede_ids,
                                attendance_status="attended",
                            ).exists()
                            else 999
                        ),
                        "remaining_classes": (
                            client.current_membership.classes_per_month
                            if client.current_membership
                            and client.current_membership.classes_per_month
                            else "Ilimitado"
                        ),
                    }
                    for client in Client.objects.filter(sede_id__in=sede_ids).order_by(
                        "-created_at"
                    )[:10]
                    if Booking.objects.filter(
                        client=client,
                        sede_id__in=sede_ids,
                        attendance_status="attended",
                    ).exists()
                    and (
                        today
                        - Booking.objects.filter(
                            client=client,
                            sede_id__in=sede_ids,
                            attendance_status="attended",
                        )
                        .order_by("-class_date")
                        .first()
                        .class_date
                    ).days
                    > 14
                ],
                # Datos de membresías (mock por ahora)
                "membershipStats": [
                    {"name": "Mensual", "count": int(active_clients * 0.4)},
                    {"name": "Trimestral", "count": int(active_clients * 0.3)},
                    {"name": "Anual", "count": int(active_clients * 0.2)},
                    {"name": "Clase Suelta", "count": int(active_clients * 0.1)},
                ],
                "membershipDetails": [
                    {
                        "name": membership.name,
                        "active_clients": Client.objects.filter(
                            sede_id__in=sede_ids,
                            current_membership=membership,
                            status="A",
                        ).count(),
                        "classes_per_month": membership.classes_per_month
                        or "Ilimitado",
                        "price": float(membership.price),
                        "percentage": (
                            Client.objects.filter(
                                sede_id__in=sede_ids,
                                current_membership=membership,
                                status="A",
                            ).count()
                            / max(total_active_clients, 1)
                        )
                        * 100,
                        "monthly_revenue": Payment.objects.filter(
                            sede_id__in=sede_ids,
                            membership=membership,
                            date_paid__year=current_year,
                            date_paid__month=current_month,
                            valid_until__gte=today,
                        ).aggregate(total=Sum("amount"))["total"]
                        or 0,
                    }
                    for membership in Membership.objects.filter(
                        Q(scope="GLOBAL") | Q(sede_id__in=sede_ids)
                    ).distinct()
                ],
                "renewalStats": [
                    {
                        "month": calendar.month_name[month],
                        "count": Payment.objects.filter(
                            sede_id__in=sede_ids,
                            date_paid__year=current_year,
                            date_paid__month=month,
                        ).count(),
                    }
                    for month in range(1, 13)
                ],
            }
        )

    except Exception as e:
        return Response({"error": f"Error interno del servidor: {str(e)}"}, status=500)


class ClassTypeViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar tipos de clase
    """

    queryset = ClassType.objects.all()
    serializer_class = ClassTypeSerializer
    permission_classes = [IsAuthenticated, SedeAccessPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    ordering_fields = ["name"]
    ordering = ["name"]


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated, IsSedeOwnerOrReadOnly]
    
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["sede", "is_active"]
    ordering_fields = ["start_time", "end_time", "created_at"]
    ordering = ["sede", "start_time"]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('sede_id')
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        return queryset
    
    @action(detail=False, methods=['get'], url_path='by-sede/(?P<sede_id>[^/.]+)')
    def by_sede(self, request, sede_id=None):
        """Obtener todos los TimeSlots activos de una sede específica"""
        try:
            time_slots = TimeSlot.objects.filter(
                sede_id=sede_id,
                is_active=True
            ).order_by('start_time')
            
            serializer = self.get_serializer(time_slots, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"error": f"Error al obtener time slots: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


