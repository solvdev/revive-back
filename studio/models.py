# studio/models.py
from django.db import models
from accounts.models import Client, CustomUser
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()

class Sede(models.Model):
    """Global Sede model for multisite support"""
    name = models.CharField(max_length=100, help_text="Nombre de la sede")
    slug = models.SlugField(max_length=50, unique=True, help_text="Identificador único para URLs")
    status = models.BooleanField(default=True, help_text="Sede activa/inactiva")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Sede"
        verbose_name_plural = "Sedes"
    
    def __str__(self):
        return self.name

class ClassType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class Schedule(models.Model):
    DAY_CHOICES = [
        ('MON', 'Lunes'),
        ('TUE', 'Martes'),
        ('WED', 'Miércoles'),
        ('THU', 'Jueves'),
        ('FRI', 'Viernes'),
        ('SAT', 'Sábado'),
        ('SUN', 'Domingo'),
    ]
    # Definimos los bloques horarios AM, cada uno de una hora.
    TIME_SLOTS = [
        ('05:00', '05:00 - 06:00'),
        ('06:00', '06:00 - 07:00'),
        ('07:00', '07:00 - 08:00'),
        ('08:00', '08:00 - 09:00'),
        ('09:00', '09:00 - 10:00'),
        ('10:00', '10:00 - 11:00'),
        ('11:00', '11:00 - 12:00'),
        ('12:00', '12:00 - 13:00'),
        ('16:00', '16:00 - 17:00'),
        ('17:00', '17:00 - 18:00'),
        ('18:00', '18:00 - 19:00'),
        ('19:00', '19:00 - 20:00'),
    ]
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    time_slot = models.CharField(max_length=5, choices=TIME_SLOTS, default='05:00')
    # Relación opcional con un tipo de clase (por ejemplo, "Pilates Mat", "Pilates Reformer", etc.)
    class_type = models.ForeignKey(ClassType, on_delete=models.CASCADE, blank=True, null=True)
    # Campo para distinguir si la clase es individual (capacidad forzada a 1)
    is_individual = models.BooleanField(
        default=False,
        help_text="Si se marca, la clase es individual (capacidad 1)."
    )
    # Capacidad predeterminada para clases grupales.
    capacity = models.PositiveIntegerField(default=9)
    coach = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'groups__name': 'coach'},
        related_name='assigned_classes'
    )
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede a la que pertenece este horario"
    )

    def save(self, *args, **kwargs):
        # Si es una clase individual, forzamos la capacidad a 1.
        if self.is_individual:
            self.capacity = 1
        super().save(*args, **kwargs)

    def __str__(self):
        tipo = "Individual" if self.is_individual else "Grupal"
        return f"{self.get_day_display()} {self.get_time_slot_display()} ({tipo})"

class Membership(models.Model):
    SCOPE_CHOICES = [
        ('GLOBAL', 'Global'),
        ('SEDE', 'Sede específica'),
    ]
    
    name = models.CharField(max_length=100)  # Ej: "1 clase individual", "2 clases/semana", etc.
    price = models.DecimalField(max_digits=6, decimal_places=2)
    # Si es nulo o 0 se considera que no hay límite semanal.
    classes_per_month = models.PositiveIntegerField(
    null=True, blank=True,
    help_text="Número total de clases permitidas por mes. Si es nulo o 0, se considera ilimitado."
    )
    # Multisite support
    scope = models.CharField(
        max_length=10,
        choices=SCOPE_CHOICES,
        default='GLOBAL',
        help_text="Alcance de la membresía: GLOBAL (todas las sedes) o SEDE (sede específica)"
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede específica para membresías con scope=SEDE"
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.scope == 'SEDE' and not self.sede:
            raise ValidationError("Las membresías de sede específica deben tener una sede asignada.")
        if self.scope == 'GLOBAL' and self.sede:
            raise ValidationError("Las membresías globales no deben tener sede asignada.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope_text = f" ({self.sede.name})" if self.scope == 'SEDE' and self.sede else ""
        return f"{self.name}{scope_text}"
    
class Promotion(models.Model):
    SCOPE_CHOICES = [
        ('GLOBAL', 'Global'),
        ('SEDE', 'Sede específica'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    clases_por_cliente = models.PositiveIntegerField(default=4)
    # Multisite support
    scope = models.CharField(
        max_length=10,
        choices=SCOPE_CHOICES,
        default='GLOBAL',
        help_text="Alcance de la promoción: GLOBAL (todas las sedes) o SEDE (sede específica)"
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede específica para promociones con scope=SEDE"
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.scope == 'SEDE' and not self.sede:
            raise ValidationError("Las promociones de sede específica deben tener una sede asignada.")
        if self.scope == 'GLOBAL' and self.sede:
            raise ValidationError("Las promociones globales no deben tener sede asignada.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope_text = f" ({self.sede.name})" if self.scope == 'SEDE' and self.sede else ""
        return f"{self.name}{scope_text}"


class PromotionInstance(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='instances')
    clients = models.ManyToManyField(Client)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self):
        today = timezone.now().date()
        return self.promotion.start_date <= today <= self.promotion.end_date

    def __str__(self):
        return f"Compra #{self.id} - {self.promotion.name}"


class Payment(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, null=True, blank=True)
    promotion_instance = models.ForeignKey('PromotionInstance', on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    date_paid = models.DateTimeField(default=timezone.now)
    valid_until = models.DateField(blank=True, null=True)
    extra_classes = models.PositiveIntegerField(
        default=0,
        help_text="Clases adicionales otorgadas (compensaciones u otros motivos)."
    )
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede donde se realizó el pago"
    )

    # Auditoría
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_created')
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_modified')

    def save(self, *args, **kwargs):
        if not self.valid_until:
            self.valid_until = (self.date_paid + timedelta(days=30)).date()
        if self.promotion:
            self.amount = self.promotion.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pago de {self.client} - {self.membership.name} - {self.date_paid.strftime('%Y-%m-%d')}"
    
class Venta(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ventas')
    product_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    price_per_unit = models.DecimalField(max_digits=8, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    date_sold = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede donde se realizó la venta"
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_created')
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_modified')

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} x{self.quantity} - {self.client}"

class BulkBooking(models.Model):
    """Model to handle multiple bookings at once for better user experience"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('partial', 'Parcialmente completado'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='bulk_bookings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_bookings = models.PositiveIntegerField(default=0)
    successful_bookings = models.PositiveIntegerField(default=0)
    failed_bookings = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede para la cual se realizan las reservas masivas"
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Bulk Booking #{self.id} - {self.client} ({self.status})"
    
    def update_status(self):
        """Update status based on booking results"""
        if self.failed_bookings == 0:
            self.status = 'completed'
        elif self.successful_bookings == 0:
            self.status = 'failed'
        else:
            self.status = 'partial'
        self.save(update_fields=['status'])

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente de pago'),
        ('active', 'Activo'),
        ('cancelled', 'Cancelado'),
    ]
    ATTENDANCE_CHOICES = [
        ('pending', 'Pendiente'),
        ('attended', 'Asistió'),
        ('no_show', 'No se presentó'),
    ]
    CANCELLATION_TYPE_CHOICES = [
        ('client', 'Cancelado por cliente'),
        ('instructor', 'Cancelado por instructor'),
        ('admin', 'Cancelado por administración'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    membership = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Plan seleccionado al momento de la reserva (opcional, no implica pago automático)."
    )
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    # Fecha en la que se realizará la clase (esto permite separar la fecha de la plantilla y la fecha de reserva)
    class_date = models.DateField(help_text="Fecha en que se realizará la clase", default=timezone.now)
    # Fecha en la que se realizó la reserva
    date_booked = models.DateTimeField(auto_now_add=True)

    payment = models.ForeignKey(
        'Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Pago relacionado con esta clase"
    )
    
    # Relación con bulk booking (opcional)
    bulk_booking = models.ForeignKey(
        BulkBooking, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bookings'
    )
    
    # Estado general de la reserva
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    # Estado de la asistencia
    attendance_status = models.CharField(max_length=10, choices=ATTENDANCE_CHOICES, default='pending')
    
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede donde se realizará la clase"
    )
    
    # Información sobre la cancelación (en caso de ser necesaria)
    cancellation_type = models.CharField(
        max_length=10,
        choices=CANCELLATION_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Indica quién canceló la reserva."
    )
    cancellation_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Motivo de cancelación (especialmente para cancelaciones por instructor o admin)."
    )

    class Meta:
        unique_together = ('client', 'schedule', 'class_date')

    def __str__(self):
        if self.status == 'cancelled':
            details = f" ({self.get_cancellation_type_display()}"
            if self.cancellation_reason:
                details += f": {self.cancellation_reason}"
            details += ")"
            return f"{self.client} - {self.schedule} on {self.class_date}{details}"
        return f"{self.client} - {self.schedule} on {self.class_date} ({self.get_attendance_status_display()})"

class PlanIntent(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    membership = models.ForeignKey('Membership', on_delete=models.CASCADE)
    selected_at = models.DateTimeField(default=timezone.now)
    is_confirmed = models.BooleanField(default=False)
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede para la cual se seleccionó el plan"
    )

    class Meta:
        unique_together = ['client', 'membership']

    def __str__(self):
        return f"Intento de {self.membership.name} por {self.client}"

class MonthlyRevenue(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    total_amount = models.DecimalField(max_digits=25, decimal_places=2, default=0)
    payment_count = models.PositiveIntegerField(default=0)
    venta_count = models.IntegerField(default=0)
    venta_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # nuevo
    last_updated = models.DateTimeField(auto_now=True)
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede para la cual se calcula el revenue (null = global)"
    )

    class Meta:
        unique_together = ['year', 'month', 'sede']
        ordering = ['-year', '-month']

    def __str__(self):
        sede_text = f" - {self.sede.name}" if self.sede else " - Global"
        return f"{self.month}/{self.year}{sede_text} - Q{self.total_amount}"

