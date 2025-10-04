# studio/permissions.py
from rest_framework import permissions
from django.utils.translation import gettext_lazy as _


class SedeAccessPermission(permissions.BasePermission):
    """
    Permiso personalizado para validar acceso a sedes específicas.
    Los usuarios solo pueden acceder a recursos de su sede asignada.
    """

    message = _("No tienes permisos para acceder a este recurso de esta sede.")

    def has_permission(self, request, view):
        # Si no está autenticado, no tiene permisos
        if not request.user.is_authenticated:
            return False

        # Si no hay filtro de sede aplicado, permitir acceso (para administradores globales)
        if not hasattr(request, 'sede_ids') or not request.sede_ids:
            return True

        # Verificar que el usuario tenga una sede asignada
        user_sede = getattr(request.user, 'sede', None)
        
        # Si el usuario no tiene sede asignada, es un admin global - permitir acceso
        if not user_sede:
            # Verificar si es admin global
            from django.contrib.auth.models import Group
            admin_group = Group.objects.get(name='admin')
            if admin_group in request.user.groups.all():
                return True
            return False

        # Verificar que la sede del usuario esté en las sedes solicitadas
        return user_sede.id in request.sede_ids

    def has_object_permission(self, request, view, obj):
        # Si no está autenticado, no tiene permisos
        if not request.user.is_authenticated:
            return False

        # Si el objeto no tiene sede, permitir acceso
        if not hasattr(obj, 'sede') or not obj.sede:
            return True

        # Verificar que el usuario tenga una sede asignada
        user_sede = getattr(request.user, 'sede', None)
        
        # Si el usuario no tiene sede asignada, es un admin global - permitir acceso
        if not user_sede:
            # Verificar si es admin global
            from django.contrib.auth.models import Group
            admin_group = Group.objects.get(name='admin')
            if admin_group in request.user.groups.all():
                return True
            return False

        # Verificar que la sede del objeto coincida con la sede del usuario
        return obj.sede.id == user_sede.id


class SedeWritePermission(permissions.BasePermission):
    """
    Permiso para operaciones de escritura que requieren validación de sede.
    """

    message = _("No tienes permisos para realizar esta operación en esta sede.")

    def has_permission(self, request, view):
        # Si no está autenticado, no tiene permisos
        if not request.user.is_authenticated:
            return False

        # Para operaciones de lectura, usar el permiso básico
        if request.method in permissions.SAFE_METHODS:
            return SedeAccessPermission().has_permission(request, view)

        # Para operaciones de escritura, verificar sede
        user_sede = getattr(request.user, 'sede', None)
        if not user_sede:
            return False

        # Si hay filtro de sede, verificar que coincida
        if hasattr(request, 'sede_ids') and request.sede_ids:
            return user_sede.id in request.sede_ids

        return True

    def has_object_permission(self, request, view, obj):
        # Si no está autenticado, no tiene permisos
        if not request.user.is_authenticated:
            return False

        # Para operaciones de lectura, usar el permiso básico
        if request.method in permissions.SAFE_METHODS:
            return SedeAccessPermission().has_object_permission(request, view, obj)

        # Para operaciones de escritura, verificar sede del objeto
        if not hasattr(obj, 'sede') or not obj.sede:
            return True

        user_sede = getattr(request.user, 'sede', None)
        if not user_sede:
            return False

        return obj.sede.id == user_sede.id


class IsSedeOwnerOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite lectura a todos los usuarios autenticados,
    pero solo escritura a usuarios de la sede correspondiente.
    """

    message = _("Solo puedes modificar recursos de tu sede asignada.")

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Lectura permitida para todos los usuarios autenticados
        if request.method in permissions.SAFE_METHODS:
            return True

        # Special case for booking cancellation
        if hasattr(obj, 'client'):
            # If this is a booking and the user is a client, allow cancellation of own bookings
            if hasattr(request.user, 'client_profile') and obj.client and obj.client.user == request.user:
                return True
            
            # If this is a booking and the user is admin/secretaria, allow cancellation
            if (request.user.is_superuser or 
                request.user.groups.filter(name__in=["admin", "secretaria"]).exists()):
                return True

        # Escritura solo para usuarios de la sede correspondiente
        if not hasattr(obj, 'sede') or not obj.sede:
            return True

        user_sede = getattr(request.user, 'sede', None)
        if not user_sede:
            return False

        return obj.sede.id == user_sede.id
