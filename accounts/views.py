# accounts/views.py
from rest_framework import viewsets, permissions
from rest_framework.pagination import PageNumberPagination
from .models import CustomUser, Client
from rest_framework.response import Response
from .serializers import CustomUserSerializer, ClientSerializer, CombinedProfileSerializer, ClientMinimalSerializer
from rest_framework import filters
from rest_framework.decorators import action
from datetime import date
from studio.models import Payment, PlanIntent
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.contrib.auth.models import Group as AuthGroup
from rest_framework import status
from .serializers import UserRegistrationSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from .models import PasswordResetToken
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import timedelta
from django.core.cache import cache
from studio.mixins import SedeFilterMixin
import re

class CustomUserViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    # Solo administradores podrán acceder a estos endpoints
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'], url_path='coaches', permission_classes=[permissions.IsAuthenticated])
    def list_coaches(self, request):
        coach_group = AuthGroup.objects.filter(name="coach").first()
        if not coach_group:
            return Response([], status=200)

        # Get coaches queryset
        coaches_queryset = CustomUser.objects.filter(groups=coach_group)
        
        # Apply sede filtering manually
        if hasattr(request, 'sede_ids') and request.sede_ids:
            coaches_queryset = coaches_queryset.filter(sede_id__in=request.sede_ids)
        
        serializer = self.get_serializer(coaches_queryset, many=True)
        return Response(serializer.data)


# class ClientPagination(PageNumberPagination):
#     page_size = 10
#     page_size_query_param = 'page_size'
#     max_page_size = 100


class ClientViewSet(SedeFilterMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by('id')  # ← orden opcional
    serializer_class = ClientSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['email', 'first_name', 'last_name', 'phone', 'dpi']  # ← puedes buscar por más campos
    # pagination_class = ClientPagination

    def list(self, request, *args, **kwargs):
        """Override list to use minimal serializer for better performance"""
        # Use minimal serializer for list view to avoid N+1 queries
        queryset = self.filter_queryset(self.get_queryset())
        serializer = ClientMinimalSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='simple-list')
    def simple_list(self, request):
        """Get only id, first_name, last_name for dropdowns - much faster"""
        clients = Client.objects.filter(status="A").only('id', 'first_name', 'last_name').order_by('first_name', 'last_name')
        
        # Apply sede filtering if sede_ids are provided
        if hasattr(request, 'sede_ids') and request.sede_ids:
            clients = clients.filter(sede_id__in=request.sede_ids)
        
        data = [{'id': client.id, 'first_name': client.first_name, 'last_name': client.last_name} for client in clients]
        return Response(data)




    @action(detail=False, methods=['get'], url_path='minimal-list')
    def minimal_list(self, request):
        """Lista minimalista usando serializer sin consultas adicionales"""
        import time
        
        print("=== MINIMAL LIST DEBUG START ===")
        start_time = time.time()
        
        try:
            print("Step 1: Starting query...")
            query_start = time.time()
            
            # Usar el serializer minimalista
            clients = Client.objects.filter(status="A").order_by('first_name', 'last_name')
            
            # Apply sede filtering if sede_ids are provided
            if hasattr(request, 'sede_ids') and request.sede_ids:
                clients = clients.filter(sede_id__in=request.sede_ids)
            
            # Apply slice after filtering
            clients = clients[:1000]
            
            query_end = time.time()
            query_time = (query_end - query_start) * 1000
            print(f"Step 1: Query executed in {query_time:.2f}ms, got {clients.count()} clients")
            
            print("Step 2: Starting serialization...")
            serializer_start = time.time()
            
            serializer = ClientMinimalSerializer(clients, many=True)
            
            serializer_end = time.time()
            serializer_time = (serializer_end - serializer_start) * 1000
            print(f"Step 2: Serialization completed in {serializer_time:.2f}ms")
            
            print("Step 3: Processing data...")
            processing_start = time.time()
            
            # Agregar campo 'name' concatenado
            data = []
            for item in serializer.data:
                data.append({
                    'id': item['id'],
                    'name': f"{item['first_name']} {item['last_name']}"
                })
            
            processing_end = time.time()
            processing_time = (processing_end - processing_start) * 1000
            print(f"Step 3: Data processing completed in {processing_time:.2f}ms")
            
            end_time = time.time()
            total_time = (end_time - start_time) * 1000
            print(f"TOTAL TIME: {total_time:.2f}ms")
            print(f"Breakdown: Query={query_time:.2f}ms, Serializer={serializer_time:.2f}ms, Processing={processing_time:.2f}ms")
            print(f"Returned {len(data)} clients")
            
            print("=== MINIMAL LIST DEBUG END ===")
            return Response(data)
            
        except Exception as e:
            print(f"ERROR in minimal_list: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return Response({"error": str(e)}, status=500)


    @action(detail=True, methods=['get'], url_path='dashboard')
    def client_dashboard(self, request, pk=None):
        """Get comprehensive client dashboard data in one request"""
        from django.db.models import Count, Q, Sum
        from datetime import datetime, timedelta
        from studio.models import Booking, Payment, Membership
        
        client = self.get_object()
        
        # Validate that client belongs to selected sede
        if hasattr(request, 'sede_ids') and request.sede_ids:
            if client.sede_id not in request.sede_ids:
                return Response({
                    'error': 'Cliente no pertenece a la sede seleccionada'
                }, status=403)
        
        # Get current date info
        now = datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Get active payment
        active_payment = Payment.objects.filter(
            client=client, 
            valid_until__gte=now.date()
        ).select_related('membership').order_by('-date_paid').first()
        
        # Get booking statistics
        total_bookings = Booking.objects.filter(client=client).count()
        attended_bookings = Booking.objects.filter(client=client, attendance_status='attended').count()
        no_show_bookings = Booking.objects.filter(client=client, attendance_status='no_show').count()
        cancelled_bookings = Booking.objects.filter(client=client, attendance_status='cancelled').count()
        
        # Current month statistics
        current_month_bookings = Booking.objects.filter(
            client=client,
            class_date__range=[current_month_start.date(), current_month_end]
        )
        
        current_month_attended = current_month_bookings.filter(attendance_status='attended').count()
        current_month_no_show = current_month_bookings.filter(attendance_status='no_show').count()
        
        # Recent bookings (last 10)
        recent_bookings = Booking.objects.filter(client=client).select_related(
            'schedule', 'schedule__class_type', 'membership'
        ).order_by('-class_date')[:10]
        
        recent_bookings_data = []
        for booking in recent_bookings:
            schedule_info = "—"
            if booking.schedule:
                day_name = booking.class_date.strftime("%A")
                day_name_es = {
                    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
                    "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"
                }.get(day_name, day_name)
                schedule_info = f"{day_name_es} {booking.schedule.time_slot}"
            
            recent_bookings_data.append({
                'id': booking.id,
                'class_date': booking.class_date.strftime('%Y-%m-%d'),
                'attendance_status': booking.attendance_status,
                'schedule': schedule_info,
                'cancellation_reason': booking.cancellation_reason,
            })
        
        # Payment history (last 5)
        payment_history = Payment.objects.filter(client=client).select_related('membership').order_by('-date_paid')[:5]
        payment_data = []
        for payment in payment_history:
            payment_data.append({
                'id': payment.id,
                'amount': float(payment.amount),
                'date_paid': payment.date_paid.strftime('%Y-%m-%d'),
                'valid_until': payment.valid_until.strftime('%Y-%m-%d'),
                'membership_name': payment.membership.name if payment.membership else 'N/A',
                'is_active': payment.valid_until >= now.date()
            })
        
        # Calculate remaining classes
        expected_classes = active_payment.membership.classes_per_month if active_payment and active_payment.membership else 0
        remaining_classes = expected_classes - current_month_attended if expected_classes else 0
        
        # Determine client status
        if current_month_attended == 0 and current_month_no_show == 0:
            status = "Nuevo"
            status_color = "info"
        elif remaining_classes <= 2 and remaining_classes > 0:
            status = "Renovación"
            status_color = "warning"
        elif remaining_classes == 0:
            status = "Inactivo"
            status_color = "secondary"
        else:
            status = "Activo"
            status_color = "success"
        
        dashboard_data = {
            'client': {
                'id': client.id,
                'first_name': client.first_name,
                'last_name': client.last_name,
                'email': client.email,
                'phone': client.phone,
                'status': status,
                'status_color': status_color,
                'created_at': client.created_at.strftime('%Y-%m-%d') if client.created_at else None,
            },
            'current_membership': {
                'name': active_payment.membership.name if active_payment and active_payment.membership else 'Sin membresía activa',
                'classes_per_month': expected_classes,
                'valid_until': active_payment.valid_until.strftime('%Y-%m-%d') if active_payment else None,
                'is_active': active_payment is not None
            },
            'statistics': {
                'total_bookings': total_bookings,
                'attended_bookings': attended_bookings,
                'no_show_bookings': no_show_bookings,
                'cancelled_bookings': cancelled_bookings,
                'attendance_rate': round((attended_bookings / total_bookings * 100) if total_bookings > 0 else 0, 1),
                'current_month_attended': current_month_attended,
                'current_month_no_show': current_month_no_show,
                'remaining_classes': remaining_classes,
            },
            'recent_bookings': recent_bookings_data,
            'payment_history': payment_data,
        }
        
        return Response(dashboard_data)

    @action(detail=True, methods=['get'], url_path='clases-por-mes')
    def client_clases_por_mes(self, request, pk=None):
        """Get monthly class control data for a specific client"""
        from django.db.models import Q
        from datetime import datetime, timedelta
        
        client = self.get_object()
        
        year = int(request.query_params.get('year', datetime.now().year))
        month = int(request.query_params.get('month', datetime.now().month))
        
        first_day = datetime(year, month, 1).date()
        if month == 12:
            last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        # Check if client was created after the requested period
        client_created_date = client.created_at.date() if client.created_at else datetime.now().date()
        if client_created_date > last_day:
            return Response({
                'client_id': client.id,
                'client_name': f"{client.first_name} {client.last_name}",
                'membership': 'Cliente no existía en este período',
                'expected_classes': 0,
                'valid_classes': 0,
                'no_show_classes': 0,
                'date_no_show': [],
                'penalty': 0,
            })
        
        # If client was created during the period, adjust the start date
        if client_created_date > first_day:
            first_day = client_created_date
        
        # Get the most recent active payment for the period
        # Only consider payments that were active during the requested period
        active_payment = client.payment_set.filter(
            valid_until__gte=first_day,
            date_paid__lte=last_day  # Payment must have been made before or during the period
        ).select_related('membership').order_by('-date_paid').first()
        
        if not active_payment:
            return Response({
                'client_id': client.id,
                'client_name': f"{client.first_name} {client.last_name}",
                'membership': 'Sin membresía activa en este período',
                'expected_classes': 0,
                'valid_classes': 0,
                'no_show_classes': 0,
                'date_no_show': [],
                'penalty': 0,
            })
        
        # Count valid classes (attended + cancelled) - only for the adjusted period
        valid_classes = client.booking_set.filter(
            class_date__range=[first_day, last_day],
            attendance_status__in=['attended', 'cancelled']
        ).count()
        
        # Count no-show classes without justification - only for the adjusted period
        no_show_classes = client.booking_set.filter(
            class_date__range=[first_day, last_day],
            attendance_status='no_show',
        ).filter(
            Q(cancellation_reason__isnull=True) | Q(cancellation_reason__exact='')
        ).count()
        
        # Get no-show dates - only for the adjusted period
        no_show_dates = list(client.booking_set.filter(
            class_date__range=[first_day, last_day],
            attendance_status='no_show',
        ).filter(
            Q(cancellation_reason__isnull=True) | Q(cancellation_reason__exact='')
        ).values_list('class_date', flat=True).distinct())
        
        # Calculate penalty only for no-shows in the adjusted period
        penalizacion = no_show_classes * 35
        
        return Response({
            'client_id': client.id,
            'client_name': f"{client.first_name} {client.last_name}",
            'membership': active_payment.membership.name,
            'expected_classes': active_payment.membership.classes_per_month or 0,
            'valid_classes': valid_classes,
            'no_show_classes': no_show_classes,
            'date_no_show': no_show_dates,
            'penalty': penalizacion,
            'debug_info': {
                'client_created_date': client_created_date.strftime('%Y-%m-%d'),
                'period_start': first_day.strftime('%Y-%m-%d'),
                'period_end': last_day.strftime('%Y-%m-%d'),
                'payment_date': active_payment.date_paid.strftime('%Y-%m-%d'),
                'payment_valid_until': active_payment.valid_until.strftime('%Y-%m-%d'),
            }
        })

    @action(detail=True, methods=['get'], url_path='estado')
    def estado_cliente(self, request, pk=None):
        client = self.get_object()

        # Verificar membresía activa
        latest_payment = Payment.objects.filter(client=client).order_by('-date_paid').first()
        plan_activo = latest_payment and latest_payment.valid_until >= date.today()

        # Verificar si tiene intención de plan pendiente (no confirmada)
        plan_intent = PlanIntent.objects.filter(client=client, is_confirmed=False).order_by('-selected_at').first()

        if not client.trial_used and not plan_intent:
            estado = 'nuevo'
        elif not client.trial_used and plan_intent:
            estado = 'conClaseGratisPendienteYPlanSeleccionado'
        elif client.trial_used and not plan_activo and plan_intent:
            estado = 'conClaseGratisUsadaYPlanSeleccionado'
        elif client.trial_used and not plan_activo and not plan_intent:
            estado = 'conClaseGratisUsada'
        elif plan_activo:
            estado = 'conPlanActivo'
        else:
            estado = 'desconocido'

        puede_agendar = not client.trial_used or plan_activo

        return Response({
            "estado": estado,
            "puede_agendar": puede_agendar,
            "trial_used": client.trial_used,
            "plan_activo": bool(plan_activo),
            "plan_seleccionado": bool(plan_intent),
            "mensaje": self._mensaje_por_estado(estado),
            "plan_intent": {
                "membership_id": plan_intent.membership.id,
                "membership_name": plan_intent.membership.name,
                "price": plan_intent.membership.price
            } if plan_intent else None
        })

    def _mensaje_por_estado(self, estado):
        mensajes = {
            'nuevo': "Bienvenido, agenda tu clase de prueba gratuita.",
            'conClaseGratisPendienteYPlanSeleccionado': "Puedes usar tu clase gratuita o activar el plan que seleccionaste.",
            'conClaseGratisUsada': "Ya usaste tu clase gratuita. Suscríbete para seguir entrenando con nosotros.",
            'conClaseGratisUsadaYPlanSeleccionado': "Ya usaste tu clase gratuita. Tienes un plan pendiente, actívalo para continuar entrenando con nosotros.",
            'conPlanActivo': "Tu plan está activo. Puedes agendar tus clases.",
            'desconocido': "No pudimos determinar tu estado, por favor contáctanos."
        }
        return mensajes.get(estado, '')
    
    @action(detail=False, methods=['get'], url_path='dpi')
    def client_por_dpi(self, request):
        dpi = request.query_params.get('dpi')
        if not dpi:
            return Response({"detail": "Se requiere el parámetro 'dpi'."}, status=400)
        
        client = Client.objects.filter(dpi=dpi).first()
        if client:
            # Reutilizamos la función de estado para obtener el estado del cliente
            latest_payment = Payment.objects.filter(client=client).order_by('-date_paid').first()
            plan_activo = latest_payment and latest_payment.valid_until >= date.today()
            plan_intent = PlanIntent.objects.filter(client=client, is_confirmed=False).order_by('-selected_at').first()
            if not client.trial_used and not plan_intent:
                estado = 'nuevo'
            elif not client.trial_used and plan_intent:
                estado = 'conClaseGratisPendienteYPlanSeleccionado'
            elif client.trial_used and not plan_activo and plan_intent:
                estado = 'conClaseGratisUsadaYPlanSeleccionado'
            elif client.trial_used and not plan_activo and not plan_intent:
                estado = 'conClaseGratisUsada'
            elif plan_activo:
                estado = 'conPlanActivo'
            else:
                estado = 'desconocido'

            puede_agendar = not client.trial_used or plan_activo
            mensaje = {
                'nuevo': "Bienvenido, agenda tu clase de prueba gratuita.",
                'conClaseGratisPendienteYPlanSeleccionado': "Puedes usar tu clase gratuita o activar el plan que seleccionaste.",
                'conClaseGratisUsada': "Ya usaste tu clase gratuita. Suscríbete para seguir entrenando con nosotros.",
                'conClaseGratisUsadaYPlanSeleccionado': "Ya usaste tu clase gratuita. Tienes un plan pendiente, actívalo para continuar entrenando con nosotros.",
                'conPlanActivo': "Tu plan está activo. Puedes agendar tus clases.",
                'desconocido': "No pudimos determinar tu estado, por favor contáctanos."
            }.get(estado, '')

            return Response({
                "client": ClientSerializer(client).data,
                "estado": estado,
                "puede_agendar": puede_agendar,
                "trial_used": client.trial_used,
                "plan_activo": bool(plan_activo),
                "plan_seleccionado": bool(plan_intent),
                "mensaje": mensaje,
                "plan_intent": {
                    "membership_id": plan_intent.membership.id,
                    "membership_name": plan_intent.membership.name,
                    "price": plan_intent.membership.price
                } if plan_intent else None
            })
        else:
            return Response({"detail": "No se encontró un cliente con ese DPI."}, status=404)
        
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        original_status = instance.status
        original_membership = instance.active_membership

        response = super().update(request, *args, **kwargs)

        updated_instance = self.get_object()
        updated_status = updated_instance.status
        updated_membership = updated_instance.active_membership

        if (
            (original_status == 'A' and updated_status == 'I') or
            (original_membership and not updated_membership)
        ):
            try:
                from studio.management.mails.mails import send_membership_cancellation_email
                send_membership_cancellation_email(updated_instance)
            except Exception as e:
                print(f"[ERROR] Falló envío de correo de cancelación: {str(e)}")

        return response
    
    @action(detail=False, methods=['get'], url_path='count')
    def count_clients(self, request):
        today = timezone.now().date()
        
        # Base querysets
        total_qs = Client.objects.all()
        active_qs = Client.objects.filter(status='A')
        inactive_qs = Client.objects.filter(status='I')
        new_this_month_qs = Client.objects.filter(
            created_at__year=today.year,
            created_at__month=today.month
        )
        
        # Apply sede filtering if sede_ids are provided
        if hasattr(request, 'sede_ids') and request.sede_ids:
            total_qs = total_qs.filter(sede_id__in=request.sede_ids)
            active_qs = active_qs.filter(sede_id__in=request.sede_ids)
            inactive_qs = inactive_qs.filter(sede_id__in=request.sede_ids)
            new_this_month_qs = new_this_month_qs.filter(sede_id__in=request.sede_ids)
        
        total = total_qs.count()
        active = active_qs.count()
        inactive = inactive_qs.count()
        new_this_month = new_this_month_qs.count()

        return Response({
            "total": total,
            "active": active,
            "inactive": inactive,
            "new_this_month": new_this_month
    })

#metodos para clientes

# NUEVO: obtener el Client del usuario autenticado
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    return Response(CustomUserSerializer(request.user).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_client(request):
    client = Client.objects.select_related('current_membership', 'user').filter(user=request.user).first()
    if not client:
        return Response({"detail": "Este usuario no tiene un cliente asociado."}, status=404)
    return Response(ClientSerializer(client).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_profile(request):
    client = (
        Client.objects
        .select_related('current_membership', 'user')
        .filter(user=request.user)
        .first()
    )
    data = CombinedProfileSerializer({"user": request.user, "client": client}).data
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_auth_session(request):
    """Return user session information including available sites."""
    from studio.models import Sede
    
    # Get user information
    user_data = CustomUserSerializer(request.user).data
    
    # Get available sedes (for now, all active sedes)
    # In the future, this can be filtered based on user permissions
    available_sedes = Sede.objects.filter(status=True).values('id', 'name', 'slug')
    
    # Get client information if exists
    client = Client.objects.select_related('sede').filter(user=request.user).first()
    client_sede = None
    
    # Priorizar la sede del usuario sobre la del cliente
    if request.user.sede:
        client_sede = {
            'id': request.user.sede.id,
            'name': request.user.sede.name,
            'slug': request.user.sede.slug
        }
    elif client and client.sede:
        client_sede = {
            'id': client.sede.id,
            'name': client.sede.name,
            'slug': client.sede.slug
        }
    
    return Response({
        'user': user_data,
        'available_sedes': list(available_sedes),
        'client_sede': client_sede,
        'sede_filter_applied': getattr(request, 'sede_filter_applied', False),
        'selected_sede_ids': getattr(request, 'sede_ids', [])
    })


# User Registration
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Assign client role to new user
        try:
            client_group, created = AuthGroup.objects.get_or_create(name="client")
            user.groups.add(client_group)
            print(f"User {user.username} assigned to client group")
        except Exception as e:
            print(f"Error assigning client role: {e}")
        
        # Send welcome email
        try:
            from studio.management.mails.mails import send_welcome_email
            # Get the client record that was created in the serializer
            client = Client.objects.get(user=user)
            send_welcome_email(user, client)
            print(f"Welcome email sent to {user.email}")
        except Exception as e:
            print(f"Error sending welcome email: {e}")
        
        return Response({
            "message": "Usuario registrado exitosamente. Por favor inicia sesión.",
            "user": CustomUserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Password Reset Request
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        user = CustomUser.objects.get(email=email)
        
        # Create or get existing token
        token, created = PasswordResetToken.objects.get_or_create(
            user=user,
            defaults={
                'expires_at': timezone.now() + timedelta(hours=24)
            }
        )
        
        if not created:
            # Update existing token
            token.expires_at = timezone.now() + timedelta(hours=24)
            token.is_used = False
            token.save()
        
        # Send email with reset link
        from django.conf import settings
        try:
            from vile_pilates.env import FRONTEND_URL
            frontend_url = FRONTEND_URL
        except ImportError:
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        reset_url = f"{frontend_url}/auth/reset-password/{token.token}"
        
        # Simple email template
        subject = "Recuperación de Contraseña - Vilé Pilates"
        html_message = f"""
        <h2>Recuperación de Contraseña</h2>
        <p>Hola {user.first_name},</p>
        <p>Has solicitado recuperar tu contraseña. Haz clic en el siguiente enlace para continuar:</p>
        <p><a href="{reset_url}">Cambiar Contraseña</a></p>
        <p>Este enlace expirará en 24 horas.</p>
        <p>Si no solicitaste este cambio, puedes ignorar este mensaje.</p>
        <br>
        <p>Saludos,<br>Equipo Vilé Pilates</p>
        """
        
        plain_message = strip_tags(html_message)
        
        try:
            # Send email using configured settings
            send_mail(
                subject,
                plain_message,
                'no-reply@vilepilates.com',
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
            return Response({
                "message": "Se ha enviado un enlace de recuperación a tu email."
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return Response({
                "error": "Error al enviar el email. Por favor intenta nuevamente."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Password Reset Confirm
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def confirm_password_reset(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']
        
        # Update user password
        user = reset_token.user
        user.set_password(new_password)
        user.save()
        
        # Mark token as used
        reset_token.is_used = True
        reset_token.save()
        
        return Response({
            "message": "Contraseña actualizada exitosamente. Puedes iniciar sesión con tu nueva contraseña."
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




# Generate User for Existing Client
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def generate_user_for_client(request):
    """Generar usuario para un cliente existente usando solo email"""
    email = request.data.get('email', '').strip().lower()
    
    if not email:
        return Response({
            "error": "Email es requerido"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Buscar cliente por email
    try:
        client = Client.objects.get(email__iexact=email)
    except Client.DoesNotExist:
        return Response({
            "error": "No se encontró un cliente con ese email. Verifica que sea el email correcto o contacta con nosotros."
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Verificar si ya tiene usuario
    if client.user:
        return Response({
            "error": "Este cliente ya tiene una cuenta de usuario asociada. Intenta iniciar sesión con tu email."
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generar username único basado en email
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    
    while CustomUser.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    
    # Generar contraseña temporal
    import secrets
    import string
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    temp_password = ''.join(secrets.choice(characters) for _ in range(12))
    
    # Crear usuario
    user = CustomUser.objects.create_user(
        username=username,
        email=email,
        password=temp_password,
        first_name=client.first_name,
        last_name=client.last_name,
        is_active=True,
        is_enabled=True
    )
    
    # Asignar grupo de cliente
    try:
        client_group = AuthGroup.objects.get(name="client")
        user.groups.add(client_group)
    except AuthGroup.DoesNotExist:
        pass
    
    # Asignar sede si el cliente tiene una
    if client.sede:
        user.sede = client.sede
        user.save()
    
    # Asociar cliente con usuario
    client.user = user
    client.save(skip_phone_validation=True, update_fields=['user'])  # Force update of user field
    
    # Verificar que se guardó correctamente
    client.refresh_from_db()
    if not client.user:
        # Si no se guardó, intentar de nuevo sin update_fields
        client.user = user
        client.save(skip_phone_validation=True)
    
    # Enviar email de notificación
    try:
        from studio.management.mails.mails import send_user_generated_email
        send_user_generated_email(user, client, temp_password)
    except Exception as e:
        print(f"Error enviando email: {e}")
    
    return Response({
        "message": "Usuario generado exitosamente",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }, status=status.HTTP_201_CREATED)


# Set Password for Generated User
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def set_password_for_generated_user(request):
    """Establecer contraseña para un usuario recién generado"""
    email = request.data.get('email', '').strip().lower()
    new_password = request.data.get('new_password', '').strip()
    
    print(f"🔍 DEBUG set_password_for_generated_user:")
    print(f"   Email: {email}")
    print(f"   New password length: {len(new_password)}")
    print(f"   Request data: {request.data}")
    
    if not email:
        return Response({
            "error": "Email es requerido"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not new_password:
        return Response({
            "error": "Nueva contraseña es requerida"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if len(new_password) < 8:
        return Response({
            "error": "La contraseña debe tener al menos 8 caracteres"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validar fortaleza de contraseña
    if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', new_password):
        return Response({
            "error": "La contraseña debe contener al menos una mayúscula, una minúscula y un número"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Buscar usuario por email
    try:
        user = CustomUser.objects.get(email__iexact=email)
        print(f"   User found: {user.username}")
        print(f"   User current password hash: {user.password[:20]}...")
    except CustomUser.DoesNotExist:
        return Response({
            "error": "Usuario no encontrado"
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Establecer nueva contraseña
    print(f"   Setting new password...")
    user.set_password(new_password)
    user.save()
    print(f"   Password updated successfully")
    print(f"   New password hash: {user.password[:20]}...")
    print(f"   ✅ NO EMAIL SHOULD BE SENT FROM THIS FUNCTION")
    
    return Response({
        "message": "Contraseña establecida exitosamente. Ya puedes iniciar sesión con tu email y nueva contraseña."
    }, status=status.HTTP_200_OK)