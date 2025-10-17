# studio/middleware_user_sede.py
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from studio.models_user_sede import UserSede


class UserSedeValidationMiddleware(MiddlewareMixin):
    """
    Middleware que valida el acceso de usuarios a sedes específicas
    usando el nuevo sistema de múltiples sedes
    """
    
    def process_request(self, request):
        # Solo aplicar a usuarios autenticados
        if not request.user.is_authenticated:
            return None
        
        # Administradores siempre pueden acceder
        if request.user.is_superuser or request.user.is_staff:
            return None
        
        # Obtener sede_id del header o parámetros
        sede_id = request.META.get('HTTP_X_SEDE_ID')
        if not sede_id:
            # Intentar obtener de los parámetros de la URL
            sede_id = request.GET.get('sede_id')
        
        if not sede_id:
            return None
        
        try:
            sede_id = int(sede_id)
        except (ValueError, TypeError):
            return None
        
        # Verificar si el usuario puede acceder a esta sede
        if not UserSede.can_user_access_sede(request.user, sede_id):
            # Obtener sedes accesibles para el mensaje de error
            accessible_sedes = UserSede.get_accessible_sedes(request.user)
            sede_names = [sede.name for sede in accessible_sedes]
            
            return JsonResponse({
                'error': 'No tienes permisos para acceder a esta sede',
                'accessible_sedes': sede_names,
                'requested_sede_id': sede_id
            }, status=403)
        
        return None

