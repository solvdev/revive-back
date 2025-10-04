# accounts/management/commands/check_user_permissions.py
from django.core.management.base import BaseCommand
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Verificar permisos de usuarios'

    def handle(self, *args, **options):
        # Mostrar todos los usuarios y sus permisos
        self.stdout.write(self.style.SUCCESS('=== USUARIOS Y PERMISOS ==='))
        
        users = CustomUser.objects.all()
        for user in users:
            groups = [g.name for g in user.groups.all()]
            self.stdout.write(f'Usuario: {user.username}')
            self.stdout.write(f'  - is_superuser: {user.is_superuser}')
            self.stdout.write(f'  - is_staff: {user.is_staff}')
            self.stdout.write(f'  - is_active: {user.is_active}')
            self.stdout.write(f'  - grupos: {groups}')
            self.stdout.write(f'  - sede: {user.sede}')
            self.stdout.write('')
