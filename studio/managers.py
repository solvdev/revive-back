# studio/managers.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class SedeFilteredQuerySet(models.QuerySet):
    """
    QuerySet personalizado que filtra automáticamente por sede.
    """

    def for_sede(self, sede_id):
        """Filtrar por sede específica."""
        return self.filter(sede_id=sede_id)

    def for_user_sede(self, user):
        """Filtrar por la sede del usuario."""
        if hasattr(user, 'sede') and user.sede:
            return self.filter(sede_id=user.sede.id)
        return self.none()

    def with_sede_info(self):
        """Incluir información de la sede en la consulta."""
        return self.select_related('sede')

    def active_only(self):
        """Filtrar solo registros activos (status != 'deleted')."""
        if hasattr(self.model, 'status'):
            return self.exclude(status='deleted')
        return self


class SedeFilteredManager(models.Manager):
    """
    Manager personalizado que aplica filtros de sede automáticamente.
    """

    def get_queryset(self):
        """Retorna el QuerySet base con filtros de sede."""
        return SedeFilteredQuerySet(self.model, using=self._db)

    def for_sede(self, sede_id):
        """Filtrar por sede específica."""
        return self.get_queryset().for_sede(sede_id)

    def for_user_sede(self, user):
        """Filtrar por la sede del usuario."""
        return self.get_queryset().for_user_sede(user)

    def with_sede_info(self):
        """Incluir información de la sede en la consulta."""
        return self.get_queryset().with_sede_info()

    def active_only(self):
        """Filtrar solo registros activos."""
        return self.get_queryset().active_only()


class BookingManager(SedeFilteredManager):
    """
    Manager específico para Bookings con funcionalidades adicionales.
    """

    def for_client_sede(self, client):
        """Obtener bookings de un cliente filtrados por su sede."""
        if hasattr(client, 'sede') and client.sede:
            return self.filter(client=client, sede_id=client.sede.id)
        return self.filter(client=client)

    def for_schedule_sede(self, schedule):
        """Obtener bookings de un horario filtrados por su sede."""
        if hasattr(schedule, 'sede') and schedule.sede:
            return self.filter(schedule=schedule, sede_id=schedule.sede.id)
        return self.filter(schedule=schedule)

    def upcoming_for_sede(self, sede_id):
        """Obtener bookings próximos para una sede específica."""
        from django.utils import timezone
        return self.filter(
            sede_id=sede_id,
            class_date__gte=timezone.now().date(),
            status='active'
        ).order_by('class_date', 'schedule__time_slot')

    def by_date_range(self, sede_id, start_date, end_date):
        """Obtener bookings en un rango de fechas para una sede."""
        return self.filter(
            sede_id=sede_id,
            class_date__range=[start_date, end_date]
        ).order_by('class_date', 'schedule__time_slot')


class ClientManager(SedeFilteredManager):
    """
    Manager específico para Clients con funcionalidades adicionales.
    """

    def for_sede(self, sede_id):
        """Obtener clientes de una sede específica."""
        return self.filter(sede_id=sede_id)

    def active_for_sede(self, sede_id):
        """Obtener clientes activos de una sede específica."""
        return self.filter(sede_id=sede_id, status='A')

    def with_active_membership_for_sede(self, sede_id):
        """Obtener clientes con membresía activa en una sede específica."""
        from django.utils import timezone
        today = timezone.now().date()
        
        return self.filter(
            sede_id=sede_id,
            status='A',
            payments__valid_until__gte=today,
            payments__date_paid__lte=today
        ).distinct()


class MembershipManager(SedeFilteredManager):
    """
    Manager específico para Memberships con funcionalidades adicionales.
    """

    def available_for_sede(self, sede_id):
        """Obtener membresías disponibles para una sede específica."""
        return self.filter(
            models.Q(scope='GLOBAL') | 
            models.Q(scope='SEDE', sede_id=sede_id)
        )

    def global_memberships(self):
        """Obtener solo membresías globales."""
        return self.filter(scope='GLOBAL')

    def sede_specific_memberships(self, sede_id):
        """Obtener membresías específicas de una sede."""
        return self.filter(scope='SEDE', sede_id=sede_id)


class PromotionManager(SedeFilteredManager):
    """
    Manager específico para Promotions con funcionalidades adicionales.
    """

    def available_for_sede(self, sede_id):
        """Obtener promociones disponibles para una sede específica."""
        return self.filter(
            models.Q(scope='GLOBAL') | 
            models.Q(scope='SEDE', sede_id=sede_id)
        )

    def active_for_sede(self, sede_id):
        """Obtener promociones activas para una sede específica."""
        from django.utils import timezone
        today = timezone.now().date()
        
        return self.filter(
            models.Q(scope='GLOBAL') | 
            models.Q(scope='SEDE', sede_id=sede_id),
            start_date__lte=today,
            end_date__gte=today
        )


class ScheduleManager(SedeFilteredManager):
    """
    Manager específico para Schedules con funcionalidades adicionales.
    """

    def for_sede(self, sede_id):
        """Obtener horarios de una sede específica."""
        return self.filter(sede_id=sede_id)

    def for_coach_sede(self, coach):
        """Obtener horarios de un coach filtrados por su sede."""
        if hasattr(coach, 'sede') and coach.sede:
            return self.filter(coach=coach, sede_id=coach.sede.id)
        return self.filter(coach=coach)

    def available_slots_for_sede(self, sede_id, day, time_slot):
        """Obtener slots disponibles para una sede, día y hora específicos."""
        return self.filter(
            sede_id=sede_id,
            day=day,
            time_slot=time_slot
        )
