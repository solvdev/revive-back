# accounts/management/commands/test_email.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils.html import strip_tags


class Command(BaseCommand):
    help = 'Enviar correo de prueba con imagen de Revive Pilates'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email de destino')

    def handle(self, *args, **options):
        email = options['email']
        
        subject = "Prueba de Correo - Revive Pilates"
        
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
                <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
                <h1 style="color: #2c3e50; margin-top: 20px;">¡Hola desde Revive Pilates!</h1>
            </div>

            <div style="padding: 30px;">
                <p>Este es un correo de prueba para verificar que:</p>
                
                <ul>
                    <li>La imagen se carga correctamente desde S3</li>
                    <li>El remitente es correcto (no-reply@revivepilatesgt.com)</li>
                    <li>El formato HTML funciona bien</li>
                    <li>Mailjet está configurado correctamente</li>
                </ul>

                <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #27ae60; margin-top: 0;">Todo funcionando perfectamente!</h3>
                    <p>El sistema de correos de Revive Pilates está listo para enviar notificaciones a los clientes.</p>
                </div>

                <div style="text-align: center; margin: 30px 0;">
                    <p style="color: #6c757d; font-size: 14px;">
                        <strong>Revive Pilates</strong><br>
                        Sistema de Gestión de Clases
                    </p>
                </div>

                <p>Saludos,<br>
                <strong>Equipo Revive Pilates</strong></p>
            </div>

            <div style="text-align: center; padding: 20px; background-color: #f8f9fa; color: #6c757d; font-size: 12px;">
                <p>Este es un correo de prueba del sistema de Revive Pilates.</p>
            </div>
        </div>
        """

        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject,
                plain_message,
                "no-reply@revivepilatesgt.com",
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Correo de prueba enviado exitosamente a {email}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error enviando correo: {str(e)}')
            )
