# accounts/management/commands/reset_staff_passwords.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Cambia la contraseña de todos los usuarios staff a Revive2025!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='Revive2025!',
            help='Nueva contraseña para todos los usuarios staff (default: Revive2025!)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué usuarios serían afectados sin hacer cambios reales'
        )

    def handle(self, *args, **options):
        password = options['password']
        dry_run = options['dry_run']
        
        # Obtener todos los usuarios staff
        staff_users = User.objects.filter(is_staff=True)
        
        if not staff_users.exists():
            self.stdout.write(
                self.style.WARNING('No se encontraron usuarios staff en el sistema.')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'Se encontraron {staff_users.count()} usuarios staff:')
        )
        
        # Mostrar información de los usuarios
        for user in staff_users:
            self.stdout.write(f'  - {user.username} ({user.email}) - Activo: {user.is_active}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nMODO DRY-RUN: No se realizarán cambios reales.')
            )
            self.stdout.write(f'Se cambiaría la contraseña a: {password}')
            return
        
        # Proceder directamente sin confirmación
        self.stdout.write(f'\nProcediendo a cambiar la contraseña de {staff_users.count()} usuarios staff a "{password}"...')
        
        # Cambiar las contraseñas
        updated_count = 0
        with transaction.atomic():
            for user in staff_users:
                try:
                    user.set_password(password)
                    user.save()
                    updated_count += 1
                    self.stdout.write(f'[OK] Contraseña actualizada para {user.username}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'[ERROR] Error actualizando {user.username}: {str(e)}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n¡Completado! Se actualizaron {updated_count} usuarios staff.')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Nueva contraseña: {password}')
        )
