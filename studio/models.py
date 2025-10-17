# studio/models.py
from datetime import timedelta, date

from accounts.models import Client, CustomUser
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from .managers import (
    BookingManager,
    ClientManager,
    MembershipManager,
    PromotionManager,
    ScheduleManager,
)

User = get_user_model()


class Sede(models.Model):
    """Global Sede model for multisite support"""

    name = models.CharField(max_length=100, help_text="Nombre de la sede")
    slug = models.SlugField(
        max_length=50, unique=True, help_text="Identificador único para URLs"
    )
    status = models.BooleanField(default=True, help_text="Sede activa/inactiva")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Sede"
        verbose_name_plural = "Sedes"

    def __str__(self):
        return self.name


class ClassType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    """Modelo para configurar horarios específicos por sede"""
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        help_text="Sede a la que pertenece este horario"
    )
    start_time = models.TimeField(help_text="Hora de inicio (ej: 16:30)")
    end_time = models.TimeField(help_text="Hora de fin (ej: 17:30)")
    is_active = models.BooleanField(default=True, help_text="Horario activo/inactivo")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_time']
        unique_together = ['sede', 'start_time', 'end_time']
        verbose_name = "Horario"
        verbose_name_plural = "Horarios"
    
    def __str__(self):
        return f"{self.sede.name}: {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
    
    @property
    def time_slot_display(self):
        """Formato para mostrar el horario"""
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
    
    @property
    def time_slot_value(self):
        """Valor para usar en el campo time_slot del Schedule"""
        return self.start_time.strftime('%H:%M')


class Schedule(models.Model):
    DAY_CHOICES = [
        ("MON", "Lunes"),
        ("TUE", "Martes"),
        ("WED", "Miércoles"),
        ("THU", "Jueves"),
        ("FRI", "Viernes"),
        ("SAT", "Sábado"),
        ("SUN", "Domingo"),
    ]
    
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    time_slot = models.CharField(max_length=5, help_text="Hora de inicio (ej: 16:30)")
    # Relación opcional con un tipo de clase (por ejemplo, "Pilates Mat", "Pilates Reformer", etc.)
    class_type = models.ForeignKey(
        ClassType, on_delete=models.CASCADE, blank=True, null=True
    )
    # Campo para distinguir si la clase es individual (capacidad forzada a 1)
    is_individual = models.BooleanField(
        default=False, help_text="Si se marca, la clase es individual (capacidad 1)."
    )
    # Capacidad predeterminada para clases grupales.
    capacity = models.PositiveIntegerField(default=9)
    coach = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"groups__name": "coach"},
        related_name="assigned_classes",
    )
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede a la que pertenece este horario",
    )

    # Manager personalizado
    objects = ScheduleManager()

    def save(self, *args, **kwargs):
        # Si es una clase individual, forzamos la capacidad a 1.
        if self.is_individual:
            self.capacity = 1
        
        # Validar que no haya solapamiento de horarios para la misma sede y día
        self.validate_no_overlap()
        
        super().save(*args, **kwargs)
    
    def validate_no_overlap(self):
        """Valida que no haya solapamiento de horarios para la misma sede y día"""
        if not self.sede or not self.day or not self.time_slot:
            return
        
        # Buscar TimeSlot correspondiente
        try:
            time_slot_obj = TimeSlot.objects.get(
                sede=self.sede,
                start_time=self.time_slot,
                is_active=True
            )
            start_time = time_slot_obj.start_time
            end_time = time_slot_obj.end_time
        except TimeSlot.DoesNotExist:
            # Si no existe TimeSlot, usar duración de 1 hora como fallback
            from datetime import datetime, timedelta
            start_time = datetime.strptime(self.time_slot, "%H:%M").time()
            end_time = (datetime.combine(datetime.today(), start_time) + timedelta(hours=1)).time()
        
        # Buscar schedules que se solapen
        overlapping_schedules = Schedule.objects.filter(
            sede=self.sede,
            day=self.day
        ).exclude(id=self.id)  # Excluir el schedule actual si es una actualización
        
        for schedule in overlapping_schedules:
            try:
                schedule_time_slot = TimeSlot.objects.get(
                    sede=schedule.sede,
                    start_time=schedule.time_slot,
                    is_active=True
                )
                schedule_start = schedule_time_slot.start_time
                schedule_end = schedule_time_slot.end_time
            except TimeSlot.DoesNotExist:
                from datetime import datetime, timedelta
                schedule_start = datetime.strptime(schedule.time_slot, "%H:%M").time()
                schedule_end = (datetime.combine(datetime.today(), schedule_start) + timedelta(hours=1)).time()
            
            # Verificar solapamiento
            if (start_time < schedule_end and end_time > schedule_start):
                raise ValidationError(
                    f"El horario se solapa con otro schedule existente: "
                    f"{schedule.get_day_display()} {schedule.time_slot} "
                    f"({schedule.class_type.name if schedule.class_type else 'Sin tipo'})"
                )

    def __str__(self):
        tipo = "Individual" if self.is_individual else "Grupal"
        return f"{self.get_day_display()} {self.time_slot} ({tipo})"


class Membership(models.Model):
    SCOPE_CHOICES = [
        ("GLOBAL", "Global"),
        ("SEDE", "Sede específica"),
    ]

    name = models.CharField(
        max_length=100
    )  # Ej: "1 clase individual", "2 clases/semana", etc.
    price = models.DecimalField(max_digits=6, decimal_places=2)
    # Si es nulo o 0 se considera que no hay límite semanal.
    classes_per_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Número total de clases permitidas por mes. Si es nulo o 0, se considera ilimitado.",
    )
    # Multisite support
    scope = models.CharField(
        max_length=10,
        choices=SCOPE_CHOICES,
        default="GLOBAL",
        help_text="Alcance de la membresía: GLOBAL (todas las sedes) o SEDE (sede específica)",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede específica para membresías con scope=SEDE",
    )

    # Manager personalizado
    objects = MembershipManager()

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.scope == "SEDE" and not self.sede:
            raise ValidationError(
                "Las membresías de sede específica deben tener una sede asignada."
            )
        if self.scope == "GLOBAL" and self.sede:
            raise ValidationError(
                "Las membresías globales no deben tener sede asignada."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope_text = (
            f" ({self.sede.name})" if self.scope == "SEDE" and self.sede else ""
        )
        return f"{self.name}{scope_text}"


class Promotion(models.Model):
    SCOPE_CHOICES = [
        ("GLOBAL", "Global"),
        ("SEDE", "Sede específica"),
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
        default="GLOBAL",
        help_text="Alcance de la promoción: GLOBAL (todas las sedes) o SEDE (sede específica)",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede específica para promociones con scope=SEDE",
    )

    # Manager personalizado
    objects = PromotionManager()

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.scope == "SEDE" and not self.sede:
            raise ValidationError(
                "Las promociones de sede específica deben tener una sede asignada."
            )
        if self.scope == "GLOBAL" and self.sede:
            raise ValidationError(
                "Las promociones globales no deben tener sede asignada."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope_text = (
            f" ({self.sede.name})" if self.scope == "SEDE" and self.sede else ""
        )
        return f"{self.name}{scope_text}"


class PromotionInstance(models.Model):
    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, related_name="instances"
    )
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
    promotion = models.ForeignKey(
        Promotion, on_delete=models.SET_NULL, null=True, blank=True
    )
    promotion_instance = models.ForeignKey(
        "PromotionInstance", on_delete=models.SET_NULL, null=True, blank=True
    )
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    date_paid = models.DateTimeField(default=timezone.now)
    
    # Campos para sistema de recibos/pólizas
    valid_from = models.DateField(
        blank=True, 
        null=True,
        help_text="Fecha de inicio de vigencia del recibo"
    )
    valid_until = models.DateField(
        blank=True, 
        null=True,
        help_text="Fecha de fin de vigencia del recibo"
    )
    receipt_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text="Número único del recibo"
    )
    month_year = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text="Mes y año del recibo (formato: YYYY-MM)"
    )
    
    # Campos para pagos anticipados
    is_advance_payment = models.BooleanField(
        default=False,
        help_text="Indica si es un pago anticipado para un mes futuro"
    )
    target_month = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text="Mes objetivo para pago anticipado (formato: YYYY-MM)"
    )
    effective_from = models.DateField(
        blank=True,
        null=True,
        help_text="Fecha efectiva de inicio de la membresía"
    )
    effective_until = models.DateField(
        blank=True,
        null=True,
        help_text="Fecha efectiva de fin de la membresía"
    )
    
    extra_classes = models.PositiveIntegerField(
        default=0,
        help_text="Clases adicionales otorgadas (compensaciones u otros motivos).",
    )
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede donde se realizó el pago",
    )

    # Auditoría
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_created",
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_modified",
    )

    def save(self, *args, **kwargs):
        # Solo manejar promociones
        if self.promotion:
            self.amount = self.promotion.price
        
        # Generar número de recibo si no existe
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        
        # Calcular fechas efectivas basado en tipo de pago
        if self.is_advance_payment and self.target_month:
            # Pago anticipado: usar target_month
            year, month = map(int, self.target_month.split('-'))
            self.effective_from = date(year, month, 1)
            self.effective_until = date(year, month, 1) + timedelta(days=30)
            self.month_year = self.target_month
        else:
            # Pago inmediato: usar fecha de pago
            if not self.effective_from and self.date_paid:
                self.effective_from = self.date_paid.date()
            if not self.effective_until and self.effective_from:
                # Para paquetes (no clases individuales): 30 días de vigencia
                # Para clases individuales: mantener lógica específica si es necesario
                if self.membership and not self.membership.name.lower().__contains__("individual"):
                    self.effective_until = self.effective_from + timedelta(days=30)
                else:
                    # Clases individuales: también 30 días por defecto
                    self.effective_until = self.effective_from + timedelta(days=30)
            if not self.month_year and self.effective_from:
                self.month_year = self.effective_from.strftime('%Y-%m')
        
        # Mantener compatibilidad con campos legacy
        if not self.valid_from:
            self.valid_from = self.effective_from
        if not self.valid_until:
            self.valid_until = self.effective_until
        
        super().save(*args, **kwargs)
    
    def generate_receipt_number(self):
        """Genera un número de recibo único"""
        from datetime import datetime
        import random
        
        # Formato: REC-YYYY-MM-NNNN
        year_month = datetime.now().strftime('%Y%m')
        random_num = random.randint(1000, 9999)
        receipt_num = f"REC-{year_month}-{random_num}"
        
        # Verificar que no exista
        while Payment.objects.filter(receipt_number=receipt_num).exists():
            random_num = random.randint(1000, 9999)
            receipt_num = f"REC-{year_month}-{random_num}"
        
        return receipt_num

    def __str__(self):
        return f"Pago de {self.client} - {self.membership.name} - {self.date_paid.strftime('%Y-%m-%d')}"


class Venta(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="ventas")
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
        help_text="Sede donde se realizó la venta",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas_created",
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas_modified",
    )

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} x{self.quantity} - {self.client}"


class BulkBooking(models.Model):
    """Model to handle multiple bookings at once for better user experience"""

    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("processing", "Procesando"),
        ("completed", "Completado"),
        ("failed", "Fallido"),
        ("partial", "Parcialmente completado"),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="bulk_bookings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
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
        help_text="Sede para la cual se realizan las reservas masivas",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Bulk Booking #{self.id} - {self.client} ({self.status})"

    def update_status(self):
        """Update status based on booking results"""
        if self.failed_bookings == 0:
            self.status = "completed"
        elif self.successful_bookings == 0:
            self.status = "failed"
        else:
            self.status = "partial"
        self.save(update_fields=["status"])


class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pendiente de pago"),
        ("active", "Activo"),
        ("cancelled", "Cancelado"),
    ]
    ATTENDANCE_CHOICES = [
        ("pending", "Pendiente"),
        ("attended", "Asistió"),
        ("no_show", "No se presentó"),
    ]
    CANCELLATION_TYPE_CHOICES = [
        ("client", "Cancelado por cliente"),
        ("instructor", "Cancelado por instructor"),
        ("admin", "Cancelado por administración"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    membership = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Plan seleccionado al momento de la reserva (opcional, no implica pago automático).",
    )
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    # Fecha en la que se realizará la clase (esto permite separar la fecha de la plantilla y la fecha de reserva)
    class_date = models.DateField(
        help_text="Fecha en que se realizará la clase", default=timezone.now
    )
    # Fecha en la que se realizó la reserva
    date_booked = models.DateTimeField(auto_now_add=True)

    payment = models.ForeignKey(
        "Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Pago relacionado con esta clase",
    )

    # Relación con bulk booking (opcional)
    bulk_booking = models.ForeignKey(
        BulkBooking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )

    # Estado general de la reserva
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    # Estado de la asistencia
    attendance_status = models.CharField(
        max_length=10, choices=ATTENDANCE_CHOICES, default="pending"
    )

    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede donde se realizará la clase",
    )

    # Información sobre la cancelación (en caso de ser necesaria)
    cancellation_type = models.CharField(
        max_length=10,
        choices=CANCELLATION_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Indica quién canceló la reserva.",
    )
    cancellation_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Motivo de cancelación (especialmente para cancelaciones por instructor o admin).",
    )

    # Manager personalizado
    objects = BookingManager()

    class Meta:
        unique_together = ("client", "schedule", "class_date")

    def __str__(self):
        if self.status == "cancelled":
            details = f" ({self.get_cancellation_type_display()}"
            if self.cancellation_reason:
                details += f": {self.cancellation_reason}"
            details += ")"
            return f"{self.client} - {self.schedule} on {self.class_date}{details}"
        return f"{self.client} - {self.schedule} on {self.class_date} ({self.get_attendance_status_display()})"


class PlanIntent(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    membership = models.ForeignKey("Membership", on_delete=models.CASCADE)
    selected_at = models.DateTimeField(default=timezone.now)
    is_confirmed = models.BooleanField(default=False)
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede para la cual se seleccionó el plan",
    )

    class Meta:
        unique_together = ["client", "membership"]

    def __str__(self):
        return f"Intento de {self.membership.name} por {self.client}"


class MonthlyRevenue(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    total_amount = models.DecimalField(max_digits=25, decimal_places=2, default=0)
    payment_count = models.PositiveIntegerField(default=0)
    venta_count = models.IntegerField(default=0)
    venta_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # nuevo
    last_updated = models.DateTimeField(auto_now=True)
    # Multisite support
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede para la cual se calcula el revenue (null = global)",
    )

    class Meta:
        unique_together = ["year", "month", "sede"]
        ordering = ["-year", "-month"]

    def __str__(self):
        sede_text = f" - {self.sede.name}" if self.sede else " - Global"
        return f"{self.month}/{self.year}{sede_text} - Q{self.total_amount}"
