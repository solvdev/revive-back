# studio/management/commands/assign_default_sede.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from studio.models import Sede

User = get_user_model()


class Command(BaseCommand):
    help = 'Asigna una sede por defecto a usuarios que no tienen sede asignada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='ID de la sede por defecto a asignar',
        )
        parser.add_argument(
            '--sede-name',
            type=str,
            help='Nombre de la sede por defecto a asignar',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué usuarios serían afectados sin hacer cambios',
        )

    def handle(self, *args, **options):
        # Obtener la sede por defecto
        sede = None
        
        if options['sede_id']:
            try:
                sede = Sede.objects.get(id=options['sede_id'])
            except Sede.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Sede con ID {options["sede_id"]} no encontrada')
                )
                return
        elif options['sede_name']:
            try:
                sede = Sede.objects.get(name=options['sede_name'])
            except Sede.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Sede "{options["sede_name"]}" no encontrada')
                )
                return
        else:
            # Usar la primera sede disponible
            sede = Sede.objects.first()
            if not sede:
                self.stdout.write(
                    self.style.ERROR('No hay sedes disponibles en el sistema')
                )
                return

        # Encontrar usuarios sin sede
        users_without_sede = User.objects.filter(sede__isnull=True)
        
        if not users_without_sede.exists():
            self.stdout.write(
                self.style.SUCCESS('Todos los usuarios ya tienen sede asignada')
            )
            return

        self.stdout.write(
            f'Encontrados {users_without_sede.count()} usuarios sin sede asignada'
        )
        self.stdout.write(f'Sede por defecto: {sede.name} (ID: {sede.id})')
        
        if options['dry_run']:
            self.stdout.write('\nUsuarios que serían afectados:')
            for user in users_without_sede:
                self.stdout.write(f'  - {user.username} ({user.email or "Sin email"})')
            self.stdout.write('\nEjecuta sin --dry-run para aplicar los cambios')
            return

        # Asignar sede a usuarios
        updated_count = users_without_sede.update(sede=sede)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Se asignó la sede "{sede.name}" a {updated_count} usuarios'
            )
        )
        
        # Mostrar usuarios actualizados
        self.stdout.write('\nUsuarios actualizados:')
        for user in users_without_sede:
            self.stdout.write(f'  - {user.username} ({user.email or "Sin email"})')
