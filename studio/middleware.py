import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from studio.models import Sede

logger = logging.getLogger(__name__)


class SedeFilterMiddleware(MiddlewareMixin):
    """
    Middleware to handle sede filtering and logging for multisite support.
    """
    
    def process_request(self, request):
        """Process incoming request to extract and validate sede information."""
        # Extract sede information from headers or query parameters
        sede_ids_header = request.META.get('HTTP_X_SEDES_SELECTED', '')
        sede_id_param = request.GET.get('sede_id')
        sede_ids_param = request.GET.get('sede_ids')
        
        # Parse sede IDs
        sede_ids = []
        
        if sede_ids_header:
            try:
                sede_ids = [int(id.strip()) for id in sede_ids_header.split(',') if id.strip()]
            except ValueError:
                logger.warning(f"Invalid sede IDs in header: {sede_ids_header}")
        
        if sede_id_param:
            try:
                sede_ids.append(int(sede_id_param))
            except ValueError:
                logger.warning(f"Invalid sede_id parameter: {sede_id_param}")
        
        if sede_ids_param:
            try:
                sede_ids.extend([int(id.strip()) for id in sede_ids_param.split(',') if id.strip()])
            except ValueError:
                logger.warning(f"Invalid sede_ids parameter: {sede_ids_param}")
        
        # Remove duplicates and validate sede IDs
        sede_ids = list(set(sede_ids))
        valid_sede_ids = []
        
        if sede_ids:
            valid_sedes = Sede.objects.filter(id__in=sede_ids, status=True)
            valid_sede_ids = list(valid_sedes.values_list('id', flat=True))
            
            if len(valid_sede_ids) != len(sede_ids):
                invalid_ids = set(sede_ids) - set(valid_sede_ids)
                logger.warning(f"Invalid or inactive sede IDs: {invalid_ids}")
        
        # Store sede information in request for use in views
        request.sede_ids = valid_sede_ids
        request.sede_filter_applied = len(valid_sede_ids) > 0
        
        # Log sede selection for observability
        if valid_sede_ids:
            logger.info(f"Request {request.method} {request.path} - Selected sedes: {valid_sede_ids}")
            print(f"🔍 MIDDLEWARE: {request.method} {request.path} - Selected sedes: {valid_sede_ids}")
        else:
            print(f"🔍 MIDDLEWARE: {request.method} {request.path} - No sede filtering applied")
        
        return None
    
    def process_response(self, request, response):
        """Process outgoing response to add sede information to headers."""
        if hasattr(request, 'sede_ids') and request.sede_ids:
            response['X-Sedes-Selected'] = ','.join(map(str, request.sede_ids))
        
        return response


class SedeValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate sede access permissions for authenticated users.
    """
    
    def process_request(self, request):
        """Validate that user has access to requested sedes."""
        if not request.user.is_authenticated:
            return None
        
        if not hasattr(request, 'sede_ids') or not request.sede_ids:
            return None
        
        # For now, allow all authenticated users to access any sede
        # In the future, this can be enhanced with user-sede permissions
        # user_sedes = request.user.sedes.all() if hasattr(request.user, 'sedes') else []
        # if not all(sede_id in user_sedes for sede_id in request.sede_ids):
        #     return JsonResponse({
        #         'error': 'Access denied to requested sedes'
        #     }, status=403)
        
        return None
