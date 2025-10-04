# accounts/models.py
# import re
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    # No es necesario definir is_staff, ya que viene de AbstractUser.
    # Personalizamos los campos groups y user_permissions para evitar conflictos.
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",
        blank=True,
        help_text="Los grupos a los que pertenece este usuario.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",
        blank=True,
        help_text="Permisos específicos para este usuario.",
        verbose_name="user permissions",
    )

    is_enabled = models.BooleanField(
        default=True,
        help_text="Indica si el usuario está habilitado para acceder al sistema.",
    )

    # Sede asignada al usuario (para secretarias y coaches)
    sede = models.ForeignKey(
        "studio.Sede",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Sede asignada al usuario (solo para secretarias y coaches)",
    )

    def save(self, *args, **kwargs):
        # Si is_enabled es False, forzamos is_active a False para desactivar el acceso.
        if not self.is_enabled:
            self.is_active = False
        else:
            # Opcional: Si se reactiva el usuario, aseguramos que is_active sea True.
            self.is_active = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Password reset for {self.user.username}"


class Client(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_profile",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)

    # Phone validation for Guatemala numbers (8 digits)
    phone_regex = RegexValidator(
        regex=r"^(\+?502[0-9]{8}|[0-9]{8})$",
        message="El número de teléfono debe tener 8 dígitos para Guatemala (ej: 50212345678 o 12345678)",
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[phone_regex],
        help_text="Número de teléfono de Guatemala (8 dígitos)",
    )

    address = models.CharField(max_length=255, blank=True, null=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    dpi = models.CharField(
        max_length=15,
        unique=False,
        null=True,
        blank=True,
        help_text="DPI único para validar uso de clase gratuita",
    )
    SEX_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("O", "Otro"),
    ]
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    source = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="¿Cómo nos conociste? Ej: Instagram, Recomendación, Facebook...",
    )
    STATUS_CHOICES = [
        ("A", "Activo"),
        ("I", "Inactivo"),
    ]
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default="I",
        help_text="A = Activo, I = Inactivo",
    )
    current_membership = models.ForeignKey(
        "studio.Membership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Membresía asignada manualmente al cliente",
    )
    trial_used = models.BooleanField(default=False)
    
    # Campo para trazabilidad de términos y condiciones aceptados
    terms_accepted = models.BooleanField(
        default=False,
        help_text="Indica si el cliente ha aceptado los términos y condiciones"
    )
    terms_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora cuando el cliente aceptó los términos y condiciones"
    )
    
    # Campos de seguimiento para envío de correos y login
    email_sent = models.BooleanField(
        default=False,
        help_text="Indica si se ha enviado el correo con credenciales"
    )
    first_login = models.BooleanField(
        default=False,
        help_text="Indica si el usuario ha iniciado sesión por primera vez"
    )
    
    # Multisite support
    sede = models.ForeignKey(
        "studio.Sede",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede principal del cliente",
    )

    # Manager personalizado
    objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dpi"],
                name="unique_dpi_not_null",
                condition=~models.Q(dpi__isnull=True),
            )
        ]

    def clean(self):
        """Custom validation for phone number"""
        super().clean()
        if self.phone:
            # Remove all non-digit characters
            digits_only = "".join(filter(str.isdigit, self.phone))

            # Validate Guatemala phone number format
            if len(digits_only) == 8:
                # Local number, add country code
                self.phone = f"+502{digits_only}"
            elif len(digits_only) == 11 and digits_only.startswith("502"):
                # Already has country code
                self.phone = f"+{digits_only}"
            elif len(digits_only) == 10 and digits_only.startswith("502"):
                # Missing +, add it
                self.phone = f"+{digits_only}"
            elif len(digits_only) > 0 and len(digits_only) != 8:
                # For existing clients, be more flexible with phone validation
                # Just ensure it has a reasonable format
                if len(digits_only) >= 7 and len(digits_only) <= 15:
                    # Keep the original format but ensure it starts with +
                    if not self.phone.startswith("+"):
                        self.phone = f"+{digits_only}"
                else:
                    raise ValidationError(
                        {
                            "phone": "El número de teléfono debe tener entre 7 y 15 dígitos."
                        }
                    )

    def save(self, *args, **kwargs):
        # Skip phone validation for existing clients to avoid breaking existing data
        skip_validation = kwargs.pop("skip_phone_validation", False)
        if not skip_validation:
            self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_membership(self):
        """Retorna la membresía activa del cliente considerando todos los pagos válidos"""
        from studio.models import Payment
        
        # Buscar todos los pagos válidos (que no hayan expirado)
        today = timezone.now().date()
        valid_payments = Payment.objects.filter(
            client=self,
            valid_from__lte=today,  # La vigencia ya empezó
            valid_until__gte=today  # Y aún no ha expirado
        ).order_by('valid_until')
        
        if not valid_payments.exists():
            return None
        
        # Si hay pagos válidos, tomar el más reciente para obtener la membresía
        # pero la vigencia real se calcula considerando todos los pagos
        latest_valid_payment = valid_payments.last()
        return latest_valid_payment.membership
    
    @property
    def membership_valid_until(self):
        """Retorna la fecha de vencimiento real considerando todos los pagos válidos"""
        from studio.models import Payment
        
        today = timezone.now().date()
        valid_payments = Payment.objects.filter(
            client=self,
            valid_from__lte=today,  # La vigencia ya empezó
            valid_until__gte=today  # Y aún no ha expirado
        ).order_by('valid_until')
        
        if not valid_payments.exists():
            return None
        
        # Retornar la fecha de vencimiento más lejana
        return valid_payments.last().valid_until
    
    def get_monthly_payment_status(self, months_ahead=6):
        """Retorna el estado de pagos para los próximos meses"""
        from studio.models import Payment
        from datetime import date, timedelta
        
        today = timezone.now().date()
        current_month = today.replace(day=1)
        
        monthly_status = []
        
        for i in range(months_ahead):
            month_date = current_month + timedelta(days=32 * i)
            month_date = month_date.replace(day=1)
            
            # Calcular el rango del mes (del 1 al último día)
            month_start = month_date
            if month_date.month == 12:
                next_month = month_date.replace(year=month_date.year + 1, month=1)
            else:
                next_month = month_date.replace(month=month_date.month + 1)
            month_end = next_month - timedelta(days=1)
            
            # Buscar pagos que cubran específicamente este mes
            # Un pago cubre un mes si su período de vigencia incluye todo el mes
            has_payment = Payment.objects.filter(
                client=self,
                valid_from__lte=month_start,      # La vigencia empieza antes o al inicio del mes
                valid_until__gte=max(month_end, today)  # Y su vigencia llega hasta el final del mes o después, y aún no ha expirado
            ).exists()
            
            # Determinar el estado
            if month_date < current_month:
                status = "past"
            elif has_payment:
                status = "paid"
            else:
                status = "pending"
            
            monthly_status.append({
                "month": month_date.strftime("%B"),
                "year": month_date.year,
                "month_num": month_date.month,
                "status": status,
                "is_current": month_date.month == current_month.month and month_date.year == current_month.year,
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "coverage_period": f"{month_start.strftime('%d/%m/%Y')} - {month_end.strftime('%d/%m/%Y')}"
            })
        
        return monthly_status

    def get_payment_receipts(self, months_ahead=6):
        """Retorna los recibos/pagos específicos por mes, como un sistema de pólizas"""
        from studio.models import Payment
        from datetime import date, timedelta
        
        today = timezone.now().date()
        current_month = today.replace(day=1)
        
        receipts = []
        
        for i in range(months_ahead):
            month_date = current_month + timedelta(days=32 * i)
            month_date = month_date.replace(day=1)
            
            # Calcular el rango del mes
            month_start = month_date
            if month_date.month == 12:
                next_month = month_date.replace(year=month_date.year + 1, month=1)
            else:
                next_month = month_date.replace(month=month_date.month + 1)
            month_end = next_month - timedelta(days=1)
            
            # Buscar el recibo específico para este mes
            receipt = Payment.objects.filter(
                client=self,
                valid_from__lte=month_start,      # La vigencia empieza antes o al inicio del mes
                valid_until__gte=max(month_end, today)  # Y su vigencia llega hasta el final del mes o después, y aún no ha expirado
            ).order_by('-valid_until').first()
            
            if receipt:
                receipts.append({
                    "month": month_date.strftime("%B"),
                    "year": month_date.year,
                    "month_num": month_date.month,
                    "receipt_id": receipt.id,
                    "amount": str(receipt.amount),
                    "payment_method": receipt.payment_method,
                    "date_paid": receipt.date_paid.date(),
                    "valid_from": month_start,
                    "valid_until": month_end,
                    "coverage_period": f"{month_start.strftime('%d/%m/%Y')} - {month_end.strftime('%d/%m/%Y')}",
                    "status": "active" if receipt.valid_until >= today else "expired"
                })
            else:
                receipts.append({
                    "month": month_date.strftime("%B"),
                    "year": month_date.year,
                    "month_num": month_date.month,
                    "receipt_id": None,
                    "amount": None,
                    "payment_method": None,
                    "date_paid": None,
                    "valid_from": month_start,
                    "valid_until": month_end,
                    "coverage_period": f"{month_start.strftime('%d/%m/%Y')} - {month_end.strftime('%d/%m/%Y')}",
                    "status": "pending"
                })
        
        return receipts

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class TermsAcceptanceLog(models.Model):
    """
    Bitácora de aceptación de términos y condiciones
    Proporciona trazabilidad completa para auditorías legales
    """
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='terms_acceptance_logs',
        help_text="Cliente que aceptó los términos"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuario autenticado que realizó la aceptación"
    )
    
    # Información de trazabilidad
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Dirección IP del cliente"
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        help_text="User-Agent del navegador/dispositivo"
    )
    
    # Información del cliente al momento de aceptación (snapshot)
    client_first_name = models.CharField(
        max_length=100,
        default="",
        help_text="Nombre del cliente al momento de aceptación"
    )
    client_last_name = models.CharField(
        max_length=100,
        default="",
        help_text="Apellido del cliente al momento de aceptación"
    )
    client_dpi = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="DPI del cliente al momento de aceptación"
    )
    client_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email del cliente al momento de aceptación"
    )
    client_phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Teléfono del cliente al momento de aceptación"
    )
    client_status = models.CharField(
        max_length=1,
        default="I",
        help_text="Estado del cliente al momento de aceptación"
    )
    client_created_at = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha de creación del cliente al momento de aceptación"
    )
    
    # Información del usuario al momento de aceptación (snapshot)
    user_username = models.CharField(
        max_length=150,
        default="",
        help_text="Username del usuario al momento de aceptación"
    )
    user_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email del usuario al momento de aceptación"
    )
    user_is_active = models.BooleanField(
        default=True,
        help_text="Estado activo del usuario al momento de aceptación"
    )
    user_date_joined = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha de registro del usuario al momento de aceptación"
    )
    
    # Timestamps
    accepted_at = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha y hora exacta de aceptación"
    )
    
    # Información adicional de contexto
    session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID de sesión del navegador"
    )
    referrer_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL desde donde se aceptaron los términos"
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-accepted_at']
        verbose_name = "Log de Aceptación de Términos"
        verbose_name_plural = "Logs de Aceptación de Términos"
        indexes = [
            models.Index(fields=['client', '-accepted_at']),
            models.Index(fields=['ip_address', '-accepted_at']),
            models.Index(fields=['accepted_at']),
        ]
    
    def __str__(self):
        return f"Términos aceptados por {self.client.full_name} el {self.accepted_at.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def client_name(self):
        return self.client.full_name
    
    @property
    def user_name(self):
        return self.user.username if self.user else "N/A"
    
    @property
    def browser_info(self):
        """Extrae información del navegador del User-Agent"""
        if not self.user_agent:
            return "Desconocido"
        
        # Extraer información básica del User-Agent
        ua = self.user_agent.lower()
        if 'chrome' in ua:
            return "Chrome"
        elif 'firefox' in ua:
            return "Firefox"
        elif 'safari' in ua:
            return "Safari"
        elif 'edge' in ua:
            return "Edge"
        elif 'opera' in ua:
            return "Opera"
        else:
            return "Otro"
    
    @property
    def device_type(self):
        """Detecta el tipo de dispositivo del User-Agent"""
        if not self.user_agent:
            return "Desconocido"
        
        ua = self.user_agent.lower()
        if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
            return "Móvil"
        elif 'tablet' in ua or 'ipad' in ua:
            return "Tablet"
        else:
            return "Desktop"
