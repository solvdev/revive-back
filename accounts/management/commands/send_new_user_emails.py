"""
Comando de Django para enviar correos automáticamente a usuarios nuevos
Ejecutar con: python manage.py send_new_user_emails
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets
import string

from accounts.models import Client
from studio.models import Sede
from studio.management.mails.mails import send_user_generated_email


class Command(BaseCommand):
    help = 'Envía correos con credenciales a usuarios nuevos que nunca han recibido correo ni iniciado sesión'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='ID de la sede específica (opcional, si no se especifica envía a todas las sedes)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué usuarios recibirían correos sin enviarlos realmente',
        )
        parser.add_argument(
            '--days-old',
            type=int,
            default=1,
            help='Solo usuarios creados hace X días o más (default: 1)',
        )

    def generate_temp_password(self):
        """Genera una contraseña temporal segura"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(characters) for _ in range(12))

    def handle(self, *args, **options):
        sede_id = options.get('sede_id')
        dry_run = options.get('dry_run')
        days_old = options.get('days_old')
        
        self.stdout.write(
            self.style.SUCCESS(f'🔍 Buscando usuarios nuevos (creados hace {days_old}+ días)...')
        )
        
        # Calcular fecha límite
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Construir queryset base
        queryset = Client.objects.filter(
            user__isnull=False,  # Que tengan usuario asociado
            email_sent=False,    # Que no hayan recibido correo
            user__last_login__isnull=True,  # Que nunca hayan iniciado sesión
            user__date_joined__lte=cutoff_date,  # Que hayan sido creados hace X días o más
            email__isnull=False,  # Que tengan email
            email__gt=''  # Email no vacío
        ).select_related('user', 'sede')
        
        # Filtrar por sede si se especifica
        if sede_id:
            try:
                sede = Sede.objects.get(id=sede_id, status=True)
                queryset = queryset.filter(sede=sede)
                self.stdout.write(f"🏢 Filtrando por sede: {sede.name}")
            except Sede.DoesNotExist:
                raise CommandError(f'Sede con ID {sede_id} no encontrada o inactiva')
        
        # Obtener usuarios candidatos
        candidates = queryset.all()
        total_candidates = candidates.count()
        
        if total_candidates == 0:
            self.stdout.write(
                self.style.WARNING('✅ No hay usuarios nuevos pendientes de correo')
            )
            return
        
        self.stdout.write(f"📊 Usuarios encontrados: {total_candidates}")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n👀 MODO DRY-RUN - No se enviarán correos realmente')
            )
            self.show_candidates(candidates)
            return
        
        # Confirmar antes de enviar
        confirm = input(f'\n¿Enviar correos a {total_candidates} usuarios? (y/N): ')
        if confirm.lower() != 'y':
            self.stdout.write(self.style.WARNING('❌ Operación cancelada'))
            return
        
        # Procesar envío
        self.send_emails_to_candidates(candidates)

    def show_candidates(self, candidates):
        """Muestra los candidatos sin enviar correos"""
        self.stdout.write('\n📋 Usuarios que recibirían correos:')
        
        for client in candidates[:10]:  # Mostrar solo los primeros 10
            user = client.user
            sede_name = client.sede.name if client.sede else 'Sin sede'
            days_since_created = (timezone.now() - user.date_joined).days
            
            self.stdout.write(
                f'  • {client.first_name} {client.last_name}'
                f' ({client.email}) - {sede_name}'
                f' - Creado hace {days_since_created} días'
            )
        
        if candidates.count() > 10:
            self.stdout.write(f'  ... y {candidates.count() - 10} más')

    def send_emails_to_candidates(self, candidates):
        """Envía correos a los candidatos"""
        self.stdout.write('\n📧 Enviando correos...')
        
        emails_sent = 0
        emails_failed = 0
        
        for client in candidates:
            try:
                user = client.user
                sede_name = client.sede.name if client.sede else 'Sin sede'
                
                self.stdout.write(f'📤 {client.first_name} {client.last_name} ({sede_name})')
                
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
                self.stdout.write(f'  ✅ Enviado')
                
            except Exception as e:
                emails_failed += 1
                self.stdout.write(f'  ❌ Error: {e}')
                continue
        
        # Estadísticas finales
        self.stdout.write('\n📊 Estadísticas:')
        self.stdout.write(f'  • Correos enviados: {emails_sent}')
        self.stdout.write(f'  • Correos fallidos: {emails_failed}')
        self.stdout.write(f'  • Total procesados: {emails_sent + emails_failed}')
        
        if emails_sent > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n✅ Proceso completado! Se enviaron {emails_sent} correos')
            )
