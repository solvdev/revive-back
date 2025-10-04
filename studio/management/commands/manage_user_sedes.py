"""
Comando para gestionar las sedes de usuarios
Ejecutar con: python manage.py manage_user_sedes
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from studio.models import Sede
from studio.models_user_sede import UserSede

User = get_user_model()


class Command(BaseCommand):
    help = 'Gestiona las sedes asignadas a usuarios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list-users',
            action='store_true',
            help='Lista todos los usuarios y sus sedes',
        )
        parser.add_argument(
            '--add-sede',
            type=str,
            help='Agregar sede a un usuario (formato: username:sede_id)',
        )
        parser.add_argument(
            '--remove-sede',
            type=str,
            help='Remover sede de un usuario (formato: username:sede_id)',
        )
        parser.add_argument(
            '--set-primary',
            type=str,
            help='Establecer sede principal (formato: username:sede_id)',
        )
        parser.add_argument(
            '--list-sedes',
            action='store_true',
            help='Lista todas las sedes disponibles',
        )

    def handle(self, *args, **options):
        if options['list_users']:
            self.list_users()
        elif options['add_sede']:
            self.add_sede(options['add_sede'])
        elif options['remove_sede']:
            self.remove_sede(options['remove_sede'])
        elif options['set_primary']:
            self.set_primary(options['set_primary'])
        elif options['list_sedes']:
            self.list_sedes()
        else:
            self.stdout.write('Usa --help para ver las opciones disponibles')

    def list_users(self):
        """Lista todos los usuarios y sus sedes"""
        self.stdout.write('Usuarios y sus sedes:')
        self.stdout.write('=' * 50)
        
        users = User.objects.filter(user_sedes__isnull=False).distinct().order_by('username')
        
        for user in users:
            user_sedes = UserSede.objects.filter(user=user).select_related('sede')
            sede_list = []
            
            for user_sede in user_sedes:
                primary_indicator = " (Principal)" if user_sede.is_primary else ""
                manage_indicator = " [Gestión]" if user_sede.can_manage else ""
                sede_list.append(f"{user_sede.sede.name}{primary_indicator}{manage_indicator}")
            
            self.stdout.write(f'{user.username} ({user.get_full_name()}):')
            for sede in sede_list:
                self.stdout.write(f'  - {sede}')
            self.stdout.write('')

    def add_sede(self, user_sede_str):
        """Agrega una sede a un usuario"""
        try:
            username, sede_id = user_sede_str.split(':')
            user = User.objects.get(username=username)
            sede = Sede.objects.get(id=sede_id, status=True)
            
            # Verificar si ya existe
            if UserSede.objects.filter(user=user, sede=sede).exists():
                self.stdout.write(f'El usuario {username} ya tiene acceso a {sede.name}')
                return
            
            # Crear la relación
            UserSede.objects.create(
                user=user,
                sede=sede,
                is_primary=False,
                can_manage=True
            )
            
            self.stdout.write(f'Agregado: {username} ahora puede acceder a {sede.name}')
            
        except ValueError:
            raise CommandError('Formato incorrecto. Usa: username:sede_id')
        except User.DoesNotExist:
            raise CommandError(f'Usuario {username} no encontrado')
        except Sede.DoesNotExist:
            raise CommandError(f'Sede con ID {sede_id} no encontrada')

    def remove_sede(self, user_sede_str):
        """Remueve una sede de un usuario"""
        try:
            username, sede_id = user_sede_str.split(':')
            user = User.objects.get(username=username)
            sede = Sede.objects.get(id=sede_id)
            
            user_sede = UserSede.objects.get(user=user, sede=sede)
            user_sede.delete()
            
            self.stdout.write(f'Removido: {username} ya no puede acceder a {sede.name}')
            
        except ValueError:
            raise CommandError('Formato incorrecto. Usa: username:sede_id')
        except User.DoesNotExist:
            raise CommandError(f'Usuario {username} no encontrado')
        except Sede.DoesNotExist:
            raise CommandError(f'Sede con ID {sede_id} no encontrada')
        except UserSede.DoesNotExist:
            raise CommandError(f'El usuario {username} no tiene acceso a {sede.name}')

    def set_primary(self, user_sede_str):
        """Establece una sede como principal para un usuario"""
        try:
            username, sede_id = user_sede_str.split(':')
            user = User.objects.get(username=username)
            sede = Sede.objects.get(id=sede_id)
            
            # Remover primary de otras sedes
            UserSede.objects.filter(user=user, is_primary=True).update(is_primary=False)
            
            # Establecer nueva sede principal
            user_sede, created = UserSede.objects.get_or_create(
                user=user,
                sede=sede,
                defaults={'is_primary': True, 'can_manage': True}
            )
            
            if not created:
                user_sede.is_primary = True
                user_sede.save()
            
            self.stdout.write(f'Sede principal establecida: {username} -> {sede.name}')
            
        except ValueError:
            raise CommandError('Formato incorrecto. Usa: username:sede_id')
        except User.DoesNotExist:
            raise CommandError(f'Usuario {username} no encontrado')
        except Sede.DoesNotExist:
            raise CommandError(f'Sede con ID {sede_id} no encontrada')

    def list_sedes(self):
        """Lista todas las sedes disponibles"""
        self.stdout.write('Sedes disponibles:')
        self.stdout.write('=' * 30)
        
        sedes = Sede.objects.filter(status=True).order_by('name')
        
        for sede in sedes:
            self.stdout.write(f'{sede.id}: {sede.name} ({sede.slug})')
