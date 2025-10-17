# studio/models_user_sede.py
from django.db import models
from django.contrib.auth import get_user_model
from .models import Sede

User = get_user_model()


class UserSede(models.Model):
    """
    Modelo intermedio para manejar usuarios en múltiples sedes
    Permite que coaches y administradores puedan estar en varias sedes
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='user_sedes'
    )
    sede = models.ForeignKey(
        Sede, 
        on_delete=models.CASCADE,
        related_name='sede_users'
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Sede principal del usuario (para compatibilidad con el campo sede actual)"
    )
    can_manage = models.BooleanField(
        default=False,
        help_text="Si el usuario puede gestionar recursos en esta sede"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'sede']
        ordering = ['-is_primary', 'sede__name']
        verbose_name = "Usuario-Sede"
        verbose_name_plural = "Usuarios-Sedes"
    
    def __str__(self):
        primary_indicator = " (Principal)" if self.is_primary else ""
        return f"{self.user.username} - {self.sede.name}{primary_indicator}"
    
    @classmethod
    def get_user_sedes(cls, user):
        """Obtener todas las sedes de un usuario"""
        return cls.objects.filter(user=user).select_related('sede')
    
    @classmethod
    def get_user_primary_sede(cls, user):
        """Obtener la sede principal de un usuario"""
        try:
            return cls.objects.get(user=user, is_primary=True).sede
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def can_user_access_sede(cls, user, sede):
        """Verificar si un usuario puede acceder a una sede específica"""
        # Administradores siempre pueden acceder
        if user.is_superuser or user.is_staff:
            return True
        
        # Verificar si el usuario tiene acceso a esta sede
        return cls.objects.filter(user=user, sede=sede).exists()
    
    @classmethod
    def get_accessible_sedes(cls, user):
        """Obtener todas las sedes a las que un usuario puede acceder"""
        # Administradores pueden acceder a todas las sedes
        if user.is_superuser or user.is_staff:
            return Sede.objects.filter(status=True)
        
        # Para otros usuarios, solo sus sedes asignadas
        return Sede.objects.filter(
            status=True,
            sede_users__user=user
        ).distinct()

