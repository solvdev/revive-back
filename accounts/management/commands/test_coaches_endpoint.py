# accounts/management/commands/test_coaches_endpoint.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from accounts.models import CustomUser
from accounts.views import CustomUserViewSet
from django.test import RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Probar el endpoint de coaches directamente'

    def handle(self, *args, **options):
        # Crear un request factory
        factory = RequestFactory()
        
        # Obtener un usuario admin
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No hay usuario superuser disponible'))
            return
        
        # Crear un request simulado
        request = factory.get('/api/accounts/users/coaches/')
        request.user = admin_user
        
        # Simular sede_ids (todos los coaches están en sede Xela)
        request.sede_ids = [1]  # Asumiendo que Xela es sede ID 1
        
        # Crear instancia del viewset
        viewset = CustomUserViewSet()
        viewset.request = request
        
        try:
            # Llamar al método list_coaches
            response = viewset.list_coaches(request)
            
            self.stdout.write(self.style.SUCCESS('=== RESULTADO DEL ENDPOINT ==='))
            self.stdout.write(f'Status Code: {response.status_code}')
            self.stdout.write(f'Data: {response.data}')
            
            if response.data:
                self.stdout.write(f'Coaches encontrados: {len(response.data)}')
                for coach in response.data:
                    self.stdout.write(f'- {coach.get("username", "N/A")} ({coach.get("first_name", "")} {coach.get("last_name", "")})')
            else:
                self.stdout.write(self.style.WARNING('No se encontraron coaches'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al probar endpoint: {str(e)}'))
        
        # También verificar directamente desde la base de datos
        self.stdout.write(self.style.SUCCESS('\n=== VERIFICACIÓN DIRECTA ==='))
        coach_group = Group.objects.filter(name='coach').first()
        if coach_group:
            coaches = CustomUser.objects.filter(groups=coach_group)
            self.stdout.write(f'Coaches en BD: {coaches.count()}')
            for coach in coaches:
                self.stdout.write(f'- {coach.username} ({coach.first_name} {coach.last_name}) - Sede: {coach.sede}')
