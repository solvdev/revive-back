# accounts/models.py
from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.conf import settings
from django.core.validators import RegexValidator
import uuid
import re


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
        'studio.Sede',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Sede asignada al usuario (solo para secretarias y coaches)"
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
        ordering = ['-created_at']
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Password reset for {self.user.username}"


class Client(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="client_profile"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    
    # Phone validation for Guatemala numbers (8 digits)
    phone_regex = RegexValidator(
        regex=r'^(\+?502[0-9]{8}|[0-9]{8})$',
        message="El número de teléfono debe tener 8 dígitos para Guatemala (ej: 50212345678 o 12345678)"
    )
    phone = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        validators=[phone_regex],
        help_text="Número de teléfono de Guatemala (8 dígitos)"
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
        'studio.Membership',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Membresía asignada manualmente al cliente"
    )
    trial_used = models.BooleanField(default=False)
    # Multisite support
    sede = models.ForeignKey(
        'studio.Sede',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Sede principal del cliente"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dpi"],
                name="unique_dpi_not_null",
                condition=~models.Q(dpi__isnull=True)
            )
        ]

    def clean(self):
        """Custom validation for phone number"""
        super().clean()
        if self.phone:
            # Remove all non-digit characters
            digits_only = ''.join(filter(str.isdigit, self.phone))
            
            # Validate Guatemala phone number format
            if len(digits_only) == 8:
                # Local number, add country code
                self.phone = f"+502{digits_only}"
            elif len(digits_only) == 11 and digits_only.startswith('502'):
                # Already has country code
                self.phone = f"+{digits_only}"
            elif len(digits_only) == 10 and digits_only.startswith('502'):
                # Missing +, add it
                self.phone = f"+{digits_only}"
            elif len(digits_only) > 0 and len(digits_only) != 8:
                # For existing clients, be more flexible with phone validation
                # Just ensure it has a reasonable format
                if len(digits_only) >= 7 and len(digits_only) <= 15:
                    # Keep the original format but ensure it starts with +
                    if not self.phone.startswith('+'):
                        self.phone = f"+{digits_only}"
                else:
                    raise ValidationError({
                        'phone': 'El número de teléfono debe tener entre 7 y 15 dígitos.'
                    })

    def save(self, *args, **kwargs):
        # Skip phone validation for existing clients to avoid breaking existing data
        skip_validation = kwargs.pop('skip_phone_validation', False)
        if not skip_validation:
            self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_membership(self):

        from studio.models import Payment

        latest_payment = (
            Payment.objects.filter(client=self).order_by("-date_paid").first()
        )
        if latest_payment and latest_payment.valid_until >= timezone.now().date():
            return latest_payment.membership
        return None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
