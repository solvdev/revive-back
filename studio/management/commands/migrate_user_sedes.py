"""
Comando para migrar usuarios existentes al nuevo sistema de múltiples sedes
Ejecutar con: python manage.py migrate_user_sedes
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from studio.models import Sede
from studio.models_user_sede import UserSede

User = get_user_model()


class Command(BaseCommand):
    help = 'Migra usuarios existentes al nuevo sistema de múltiples sedes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué se haría sin crear los registros',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        
        if dry_run:
            self.stdout.write('MODO DRY-RUN - No se crearán registros')
        
        self.stdout.write('Migrando usuarios al sistema de múltiples sedes...')
        
        # Obtener todos los usuarios que tienen sede asignada
        users_with_sede = User.objects.filter(sede__isnull=False)
        total_users = users_with_sede.count()
        
        self.stdout.write(f'Usuarios encontrados con sede: {total_users}')
        
        created_count = 0
        
        for user in users_with_sede:
            sede = user.sede
            
            # Verificar si ya existe la relación
            if UserSede.objects.filter(user=user, sede=sede).exists():
                self.stdout.write(f'  Ya existe: {user.username} - {sede.name}')
                continue
            
            if not dry_run:
                # Crear la relación UserSede
                UserSede.objects.create(
                    user=user,
                    sede=sede,
                    is_primary=True,  # Marcar como sede principal
                    can_manage=True   # Permitir gestión
                )
            
            created_count += 1
            self.stdout.write(f'  {"Creando" if not dry_run else "Crearía"}: {user.username} - {sede.name} (Principal)')
        
        # Manejar administradores (superusuarios y staff)
        admins = User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True)
        admin_count = admins.count()
        
        self.stdout.write(f'\nAdministradores encontrados: {admin_count}')
        
        # Obtener todas las sedes activas
        active_sedes = Sede.objects.filter(status=True)
        
        for admin in admins:
            self.stdout.write(f'  Administrador: {admin.username}')
            
            for sede in active_sedes:
                # Verificar si ya existe la relación
                if UserSede.objects.filter(user=admin, sede=sede).exists():
                    continue
                
                if not dry_run:
                    # Crear relación para todas las sedes
                    UserSede.objects.create(
                        user=admin,
                        sede=sede,
                        is_primary=False,  # No es sede principal para admins
                        can_manage=True    # Pueden gestionar
                    )
                
                created_count += 1
                self.stdout.write(f'    {"Creando" if not dry_run else "Crearía"}: acceso a {sede.name}')
        
        self.stdout.write(f'\nTotal de relaciones {"creadas" if not dry_run else "que se crearían"}: {created_count}')
        
        if not dry_run:
            self.stdout.write('\nMigración completada exitosamente!')
        else:
            self.stdout.write('\nEjecuta sin --dry-run para aplicar los cambios')
