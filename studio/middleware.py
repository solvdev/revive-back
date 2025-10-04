import logging

# from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from studio.models import Sede

logger = logging.getLogger(__name__)


class SedeFilterMiddleware(MiddlewareMixin):
    """
    Middleware to handle sede filtering and logging for multisite support.
    """

    def process_request(self, request):
        """Process incoming request to extract and validate sede information."""
        # Extract sede information from headers or query parameters
        sede_ids_header = request.META.get("HTTP_X_SEDES_SELECTED", "")
        sede_id_header = request.META.get("HTTP_X_SEDE_ID", "")
        sede_id_param = request.GET.get("sede_id")
        sede_ids_param = request.GET.get("sede_ids")

        # Parse sede IDs
        sede_ids = []

        if sede_ids_header:
            try:
                sede_ids = [
                    int(id.strip()) for id in sede_ids_header.split(",") if id.strip()
                ]
            except ValueError:
                logger.warning(f"Invalid sede IDs in header: {sede_ids_header}")

        if sede_id_header:
            try:
                sede_ids.append(int(sede_id_header))
            except ValueError:
                logger.warning(f"Invalid sede ID in header: {sede_id_header}")

        if sede_id_param:
            try:
                sede_ids.append(int(sede_id_param))
            except ValueError:
                logger.warning(f"Invalid sede_id parameter: {sede_id_param}")

        if sede_ids_param:
            try:
                sede_ids.extend(
                    [int(id.strip()) for id in sede_ids_param.split(",") if id.strip()]
                )
            except ValueError:
                logger.warning(f"Invalid sede_ids parameter: {sede_ids_param}")

        # Remove duplicates and validate sede IDs
        sede_ids = list(set(sede_ids))
        valid_sede_ids = []

        if sede_ids:
            valid_sedes = Sede.objects.filter(id__in=sede_ids, status=True)
            valid_sede_ids = list(valid_sedes.values_list("id", flat=True))

            if len(valid_sede_ids) != len(sede_ids):
                invalid_ids = set(sede_ids) - set(valid_sede_ids)
                logger.warning(f"Invalid or inactive sede IDs: {invalid_ids}")

        # Store sede information in request for use in views
        request.sede_ids = valid_sede_ids
        request.sede_filter_applied = len(valid_sede_ids) > 0

        # Log sede selection for observability
        if valid_sede_ids:
            logger.info(
                f"Request {request.method} {request.path} - Selected sedes: {valid_sede_ids}"
            )
            print(
                f"🔍 MIDDLEWARE: {request.method} {request.path} - Selected sedes: {valid_sede_ids}"
            )
        else:
            print(
                f"🔍 MIDDLEWARE: {request.method} {request.path} - No sede filtering applied"
            )

        return None

    def process_response(self, request, response):
        """Process outgoing response to add sede information to headers."""
        if hasattr(request, "sede_ids") and request.sede_ids:
            response["X-Sedes-Selected"] = ",".join(map(str, request.sede_ids))

        return response


class SedeValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate sede access permissions for authenticated users.
    """

    def process_request(self, request):
        """Validate that user has access to requested sedes."""
        if not request.user.is_authenticated:
            return None

        if not hasattr(request, "sede_ids") or not request.sede_ids:
            return None

        # Los superusuarios pueden acceder a cualquier sede
        if request.user.is_superuser:
            logger.info(f"Superuser {request.user.username} accessing sedes: {request.sede_ids}")
            print(f"✅ VALIDATION: Superuser {request.user.username} accessing sedes: {request.sede_ids}")
            return None

        # Obtener la sede del usuario autenticado
        user_sede = getattr(request.user, 'sede', None)
        
        # Si el usuario no tiene sede asignada, no puede acceder a ninguna sede específica
        if not user_sede:
            logger.warning(f"User {request.user.username} has no sede assigned, denying access to sedes: {request.sede_ids}")
            from django.http import JsonResponse
            return JsonResponse({
                'success': False,
                'message': 'No tienes una sede asignada. Contacta al administrador.',
                'error_code': 'NO_SEDE_ASSIGNED'
            }, status=403)

        # Verificar que el usuario solo pueda acceder a su sede asignada
        if user_sede.id not in request.sede_ids:
            logger.warning(f"User {request.user.username} (sede: {user_sede.id}) trying to access unauthorized sedes: {request.sede_ids}")
            from django.http import JsonResponse
            return JsonResponse({
                'success': False,
                'message': f'No tienes permisos para acceder a esta sede. Tu sede asignada es: {user_sede.name}',
                'error_code': 'SEDE_ACCESS_DENIED'
            }, status=403)

        # Filtrar solo la sede del usuario
        request.sede_ids = [user_sede.id]
        request.user_sede = user_sede

        logger.info(f"User {request.user.username} accessing sede: {user_sede.name} (ID: {user_sede.id})")
        print(f"✅ VALIDATION: User {request.user.username} accessing sede: {user_sede.name} (ID: {user_sede.id})")

        return None
