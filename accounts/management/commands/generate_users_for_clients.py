import secrets
import string

from accounts.models import Client
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

# from django.template.loader import render_to_string
from django.utils.html import strip_tags

# from studio.models import Sede

User = get_user_model()


class Command(BaseCommand):
    help = "Genera usuarios para clientes existentes que no tienen usuario asociado"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se haría sin ejecutar cambios",
        )
        parser.add_argument(
            "--send-emails",
            action="store_true",
            help="Enviar emails de notificación a los usuarios generados",
        )
        parser.add_argument(
            "--sede-id",
            type=int,
            help="Solo procesar clientes de una sede específica",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        send_emails = options["send_emails"]
        sede_id = options.get("sede_id")

        # Obtener clientes sin usuario
        clients_query = Client.objects.filter(user__isnull=True)

        if sede_id:
            clients_query = clients_query.filter(sede_id=sede_id)

        clients = clients_query.select_related("sede")

        self.stdout.write(f"Encontrados {clients.count()} clientes sin usuario")

        if dry_run:
            self.stdout.write("=== MODO DRY RUN - No se realizarán cambios ===")

        # Obtener o crear grupo de clientes
        client_group, created = Group.objects.get_or_create(name="client")
        if created:
            self.stdout.write("Grupo 'client' creado")

        generated_users = []
        errors = []

        for client in clients:
            try:
                if dry_run:
                    self.stdout.write(
                        f"DRY RUN: Generaría usuario para {client.first_name} {client.last_name} ({client.email})"
                    )
                    continue

                # Generar username único basado en email o nombre
                base_username = self.generate_username(client)
                username = self.ensure_unique_username(base_username)

                # Generar contraseña temporal
                temp_password = self.generate_temp_password()

                # Crear usuario
                user = User.objects.create_user(
                    username=username,
                    email=client.email or f"{username}@temp.revivepilatesgt.com",
                    password=temp_password,
                    first_name=client.first_name,
                    last_name=client.last_name,
                    is_active=True,
                    is_enabled=True,
                )

                # Asignar grupo de cliente
                user.groups.add(client_group)

                # Asignar sede si el cliente tiene una
                if client.sede:
                    user.sede = client.sede
                    user.save()

                # Asociar cliente con usuario
                client.user = user
                client.save()

                generated_users.append(
                    {"user": user, "client": client, "temp_password": temp_password}
                )

                self.stdout.write(
                    f"✓ Usuario creado para {client.first_name} {client.last_name} - Username: {username}"
                )

            except Exception as e:
                error_msg = f"Error creando usuario para {client.first_name} {client.last_name}: {str(e)}"
                errors.append(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))

        # Enviar emails si se solicita
        if send_emails and generated_users and not dry_run:
            self.send_notification_emails(generated_users)

        # Resumen final
        self.stdout.write("\n=== RESUMEN ===")
        self.stdout.write(f"Usuarios generados: {len(generated_users)}")
        self.stdout.write(f"Errores: {len(errors)}")

        if errors:
            self.stdout.write("\n=== ERRORES ===")
            for error in errors:
                self.stdout.write(self.style.ERROR(error))

    def generate_username(self, client):
        """Genera un username basado en el email o nombre del cliente"""
        if client.email:
            # Usar parte antes del @ del email
            email_part = client.email.split("@")[0]
            # Limpiar caracteres especiales
            username = "".join(c for c in email_part if c.isalnum() or c in "._-")
            return username[:30]  # Limitar longitud
        else:
            # Usar nombre y apellido
            first_name = "".join(c for c in client.first_name if c.isalnum())
            last_name = "".join(c for c in client.last_name if c.isalnum())
            return f"{first_name.lower()}{last_name.lower()}"[:30]

    def ensure_unique_username(self, base_username):
        """Asegura que el username sea único agregando números si es necesario"""
        username = base_username
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        return username

    def generate_temp_password(self):
        """Genera una contraseña temporal segura"""
        # Generar contraseña de 12 caracteres con mayúsculas, minúsculas, números y símbolos
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(characters) for _ in range(12))
        return password

    def send_notification_emails(self, generated_users):
        """Envía emails de notificación a los usuarios generados"""
        try:
            from revive_pilates.env import FRONTEND_URL

            frontend_url = FRONTEND_URL
        except ImportError:
            frontend_url = getattr(
                settings, "FRONTEND_URL", "https://app.revivepilatesgt.com"
            )

        login_url = f"{frontend_url}/auth/login"

        for user_data in generated_users:
            user = user_data["user"]
            client = user_data["client"]
            temp_password = user_data["temp_password"]

            try:
                subject = "¡Bienvenido a Revive Pilates - Tu cuenta está lista!"

                html_message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
                        <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
                        <h1 style="color: #2c3e50; margin-top: 20px;">¡Bienvenido a Revive Pilates!</h1>
                    </div>

                    <div style="padding: 30px;">
                        <p>Hola {client.first_name},</p>

                        <p>¡Excelente noticia! Hemos creado tu cuenta en nuestro sistema de reservas online.
                        Ahora puedes gestionar tus clases de manera fácil y rápida.</p>

                        <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="color: #27ae60; margin-top: 0;">📱 Tus credenciales de acceso:</h3>
                            <p><strong>Email:</strong> {user.email}</p>
                            <p><strong>Contraseña temporal:</strong> <code style="background-color: #f1f1f1; padding: 4px 8px; border-radius: 4px;">{temp_password}</code></p>
                        </div>

                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{login_url}"
                               style="background-color: #27ae60; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">
                                🚀 Iniciar Sesión Ahora
                            </a>
                        </div>

                        <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <h4 style="color: #856404; margin-top: 0;">🔒 Importante - Seguridad:</h4>
                            <ul style="color: #856404;">
                                <li>Cambia tu contraseña temporal después del primer inicio de sesión</li>
                                <li>Tu contraseña temporal es válida por 7 días</li>
                                <li>Si no cambias la contraseña, se desactivará tu cuenta</li>
                            </ul>
                        </div>

                        <h3>🎯 ¿Qué puedes hacer ahora?</h3>
                        <ul>
                            <li>📅 <strong>Reservar clases:</strong> Ve las clases disponibles y reserva tu lugar</li>
                            <li>📊 <strong>Ver tu historial:</strong> Revisa tus clases pasadas y futuras</li>
                            <li>💳 <strong>Gestionar membresías:</strong> Administra tus planes y pagos</li>
                            <li>📱 <strong>Perfil personal:</strong> Actualiza tu información de contacto</li>
                        </ul>

                        <p>Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.</p>

                        <p>¡Esperamos verte pronto en clase!</p>

                        <p>Saludos,<br>
                        <strong>Equipo Revive Pilates</strong></p>
                    </div>

                    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; color: #6c757d; font-size: 12px;">
                        <p>Este email fue enviado automáticamente. Por favor no respondas a este mensaje.</p>
                        <p>Si no solicitaste esta cuenta, contacta con nosotros inmediatamente.</p>
                    </div>
                </div>
                """

                plain_message = strip_tags(html_message)

                send_mail(
                    subject,
                    plain_message,
                    "no-reply@revivepilatesgt.com",
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                self.stdout.write(f"✓ Email enviado a {user.email}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error enviando email a {user.email}: {str(e)}")
                )
