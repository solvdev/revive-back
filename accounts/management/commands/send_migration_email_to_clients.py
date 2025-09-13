# accounts/management/commands/send_migration_email_to_clients.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from accounts.models import Client
from studio.models import Sede
import time

class Command(BaseCommand):
    help = 'Enviar email masivo a clientes existentes con instrucciones para crear sus cuentas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular envío sin enviar emails reales',
        )
        parser.add_argument(
            '--sede-id',
            type=int,
            help='Enviar solo a clientes de una sede específica',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limitar número de emails a enviar (0 = sin límite)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay entre emails en segundos (default: 1.0)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        sede_id = options['sede_id']
        limit = options['limit']
        delay = options['delay']

        # Obtener clientes
        clients_query = Client.objects.filter(user__isnull=True)  # Solo clientes sin usuario
        
        if sede_id:
            clients_query = clients_query.filter(sede_id=sede_id)
        
        if limit > 0:
            clients_query = clients_query[:limit]
        
        clients = list(clients_query)
        
        self.stdout.write(f"📧 Enviando emails a {len(clients)} clientes...")
        
        if dry_run:
            self.stdout.write("🔍 MODO DRY-RUN - No se enviarán emails reales")
        
        # Obtener URL del frontend
        frontend_url = 'https://booking.vilepilates.com'
        
        migration_url = f"{frontend_url}/auth/migrate-existing-user"
        
        sent_count = 0
        error_count = 0
        
        for i, client in enumerate(clients, 1):
            try:
                self.stdout.write(f"📤 [{i}/{len(clients)}] Enviando a {client.email}...")
                
                if not dry_run:
                    self.send_migration_email(client, migration_url)
                    sent_count += 1
                    
                    # Delay entre emails para evitar spam
                    if delay > 0 and i < len(clients):
                        time.sleep(delay)
                else:
                    self.stdout.write(f"   📧 [DRY-RUN] Email para {client.email}")
                    sent_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error enviando a {client.email}: {str(e)}")
                )
                error_count += 1
        
        # Resumen
        self.stdout.write("\n" + "="*50)
        self.stdout.write("📊 RESUMEN DEL ENVÍO:")
        self.stdout.write(f"✅ Emails enviados: {sent_count}")
        self.stdout.write(f"❌ Errores: {error_count}")
        self.stdout.write(f"📧 Total procesados: {len(clients)}")
        
        if dry_run:
            self.stdout.write("\n🔍 Este fue un DRY-RUN. Para enviar emails reales, ejecuta sin --dry-run")

    def send_migration_email(self, client, migration_url):
        """Enviar email de migración a un cliente"""
        subject = "¡Actualiza tu cuenta en Vilé Pilates - Nuevo Sistema de Reservas!"
        
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
                <img src="{migration_url.replace('/auth/migrate-existing-user', '')}/vile-logo.png" alt="Vilé Pilates" style="max-width: 200px;">
                <h1 style="color: #2c3e50; margin-top: 20px;">¡Hola {client.first_name}!</h1>
            </div>
            
            <div style="padding: 30px;">
                <p>Esperamos que estés disfrutando de tus clases en Vilé Pilates. Tenemos una excelente noticia para ti:</p>
                
                <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h2 style="color: #27ae60; margin-top: 0;">🎉 ¡Nuevo Sistema de Reservas Online!</h2>
                    <p>Hemos lanzado una nueva plataforma digital que te permitirá:</p>
                    <ul style="color: #27ae60;">
                        <li>📅 <strong>Reservar tus clases</strong> desde cualquier lugar</li>
                        <li>📊 <strong>Ver tu historial</strong> de clases pasadas y futuras</li>
                        <li>💳 <strong>Gestionar tus membresías</strong> y pagos</li>
                        <li>📱 <strong>Acceso 24/7</strong> desde tu teléfono o computadora</li>
                        <li>🔔 <strong>Notificaciones</strong> de tus clases y recordatorios</li>
                    </ul>
                </div>
                
                <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #856404; margin-top: 0;">🔑 ¿Cómo activar tu cuenta?</h3>
                    <p style="color: #856404; margin-bottom: 15px;">Como ya eres cliente de Vilé Pilates, crear tu cuenta es súper fácil:</p>
                    <ol style="color: #856404;">
                        <li><strong>Haz clic en el botón de abajo</strong> o ve a: <a href="{migration_url}" style="color: #856404;">{migration_url}</a></li>
                        <li><strong>Ingresa tu email</strong> (el mismo que usas con nosotros)</li>
                        <li><strong>Establece tu contraseña</strong> personalizada</li>
                        <li><strong>¡Listo!</strong> Ya puedes usar el nuevo sistema</li>
                    </ol>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{migration_url}" 
                       style="background-color: #27ae60; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 16px;">
                        🚀 Crear Mi Cuenta Ahora
                    </a>
                </div>
                
                <div style="background-color: #d1ecf1; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #0c5460; margin-top: 0;">💡 ¿Por qué necesitas una cuenta?</h3>
                    <ul style="color: #0c5460;">
                        <li><strong>Mejor experiencia:</strong> Reserva clases en segundos</li>
                        <li><strong>Control total:</strong> Gestiona tu horario de clases</li>
                        <li><strong>Sin esperas:</strong> No más llamadas para reservar</li>
                        <li><strong>Historial completo:</strong> Ve todas tus clases y progreso</li>
                        <li><strong>Notificaciones:</strong> Recibe recordatorios de tus clases</li>
                    </ul>
                </div>
                
                <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #721c24; margin-top: 0;">⚠️ Importante</h3>
                    <p style="color: #721c24; margin-bottom: 0;">
                        <strong>Tu cuenta actual seguirá funcionando normalmente.</strong> 
                        Este nuevo sistema es adicional y te dará más control sobre tus reservas.
                    </p>
                </div>
                
                <p>Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos:</p>
                <ul>
                    <li>📞 <strong>Teléfono:</strong> [Tu número de teléfono]</li>
                    <li>📧 <strong>Email:</strong> [Tu email de contacto]</li>
                    <li>📍 <strong>Ubicación:</strong> [Tu dirección]</li>
                </ul>
                
                <p>¡Esperamos verte pronto en clase!</p>
                
                <p>Saludos,<br>
                <strong>Equipo Vilé Pilates</strong></p>
            </div>
            
            <div style="text-align: center; padding: 20px; background-color: #f8f9fa; color: #6c757d; font-size: 12px;">
                <p>Este email fue enviado a clientes existentes de Vilé Pilates.</p>
                <p>Si no deseas recibir estos emails, puedes contactarnos para darte de baja.</p>
            </div>
        </div>
        """
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            'no-reply@vilepilates.com',
            [client.email],
            html_message=html_message,
            fail_silently=False,
        )
