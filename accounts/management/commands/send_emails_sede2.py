"""
Comando de Django para enviar correos a usuarios de sede 2 sin emojis
Ejecutar con: python manage.py send_emails_sede2
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets
import string

from accounts.models import Client, PasswordResetToken
from studio.models import Sede
from studio.management.mails.mails import send_user_generated_email


class Command(BaseCommand):
    help = 'Envia correos con credenciales a usuarios de sede 2 que no han recibido correo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra que usuarios recibirian correos sin enviarlos realmente',
        )

    def generate_temp_password(self):
        """Genera una contraseña temporal segura"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(characters) for _ in range(12))

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        
        self.stdout.write('Buscando clientes de sede 2 sin correo enviado, sin login y sin reset de contraseña...')
        
        try:
            sede = Sede.objects.get(id=2, status=True)
            self.stdout.write(f"Filtrando por sede: {sede.name}")
        except Sede.DoesNotExist:
            raise CommandError('Sede con ID 2 no encontrada o inactiva')
        
        # Construir queryset base - TODOS los clientes de sede 2 sin correo enviado
        queryset = Client.objects.filter(
            user__isnull=False,  # Que tengan usuario asociado
            email_sent=False,    # Que no hayan recibido correo
            first_login=False,   # Que no hayan iniciado sesión por primera vez
            user__last_login__isnull=True,  # Que nunca hayan iniciado sesión
            email__isnull=False,  # Que tengan email
            email__gt='',  # Email no vacío
            sede=sede  # Sede 2
        ).exclude(
            user__passwordresettoken__is_used=True  # Excluir usuarios que ya usaron reset de contraseña
        ).select_related('user', 'sede')
        
        # Obtener usuarios candidatos
        candidates = queryset.all()
        total_candidates = candidates.count()
        
        if total_candidates == 0:
            self.stdout.write('No hay usuarios nuevos pendientes de correo en sede 2')
            return
        
        self.stdout.write(f"Usuarios encontrados: {total_candidates}")
        
        if dry_run:
            self.stdout.write('\nMODO DRY-RUN - No se enviaran correos realmente')
            self.show_candidates(candidates)
            return
        
        # Confirmar antes de enviar
        confirm = input(f'\nEnviar correos a {total_candidates} usuarios? (y/N): ')
        if confirm.lower() != 'y':
            self.stdout.write('Operacion cancelada')
            return
        
        # Procesar envío
        self.send_emails_to_candidates(candidates)

    def show_candidates(self, candidates):
        """Muestra los candidatos sin enviar correos"""
        self.stdout.write('\nUsuarios que recibirian correos:')
        
        for client in candidates[:10]:  # Mostrar solo los primeros 10
            user = client.user
            sede_name = client.sede.name if client.sede else 'Sin sede'
            days_since_created = (timezone.now() - user.date_joined).days
            
            self.stdout.write(
                f'  - {client.first_name} {client.last_name}'
                f' ({client.email}) - {sede_name}'
                f' - Creado hace {days_since_created} dias'
            )
        
        if candidates.count() > 10:
            self.stdout.write(f'  ... y {candidates.count() - 10} mas')

    def send_emails_to_candidates(self, candidates):
        """Envía correos a los candidatos"""
        self.stdout.write('\nEnviando correos...')
        
        emails_sent = 0
        emails_failed = 0
        
        for client in candidates:
            try:
                user = client.user
                sede_name = client.sede.name if client.sede else 'Sin sede'
                
                self.stdout.write(f'Enviando a: {client.first_name} {client.last_name} ({sede_name})')
                
                # Generar nueva contraseña temporal
                temp_password = self.generate_temp_password()
                
                # Establecer la contraseña temporal
                user.set_password(temp_password)
                user.save()
                
                # Enviar correo usando la función del sistema
                send_user_generated_email(user, client, temp_password)
                
                # Marcar como enviado
                client.email_sent = True
                client.save(update_fields=['email_sent'])
                
                emails_sent += 1
                self.stdout.write(f'  Enviado exitosamente')
                
            except Exception as e:
                emails_failed += 1
                self.stdout.write(f'  Error: {e}')
                continue
        
        # Estadísticas finales
        self.stdout.write('\nEstadisticas:')
        self.stdout.write(f'  - Correos enviados: {emails_sent}')
        self.stdout.write(f'  - Correos fallidos: {emails_failed}')
        self.stdout.write(f'  - Total procesados: {emails_sent + emails_failed}')
        
        if emails_sent > 0:
            self.stdout.write(f'\nProceso completado! Se enviaron {emails_sent} correos')
