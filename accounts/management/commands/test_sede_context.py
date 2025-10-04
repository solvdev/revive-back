from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Test SedeContext functionality'

    def handle(self, *args, **options):
        # Buscar usuarios con sede
        users_with_sede = User.objects.filter(sede__isnull=False)
        
        self.stdout.write(f"Usuarios con sede: {users_with_sede.count()}")
        
        for user in users_with_sede[:5]:  # Mostrar solo los primeros 5
            self.stdout.write(f"- {user.username}: {user.sede.name} (ID: {user.sede.id})")
        
        # Buscar usuarios sin sede
        users_without_sede = User.objects.filter(sede__isnull=True)
        self.stdout.write(f"\nUsuarios sin sede: {users_without_sede.count()}")
        
        for user in users_without_sede[:3]:  # Mostrar solo los primeros 3
            self.stdout.write(f"- {user.username}: Sin sede")
