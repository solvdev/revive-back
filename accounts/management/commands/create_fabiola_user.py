from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Client
from studio.models import Sede
from studio.management.mails.mails import send_user_generated_email
import secrets
import string

User = get_user_model()


class Command(BaseCommand):
    help = 'Create user and client for Fabiola Urizar and send welcome email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            default=1,
            help='Sede ID to assign to the client (default: 1 - San Lucas)',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='fabiola.urizar@gmail.com',
            help='Email for Fabiola Urizar (default: fabiola.urizar@gmail.com)',
        )

    def handle(self, *args, **options):
        sede_id = options['sede_id']
        email = options['email']
        
        # Datos de Fabiola Urizar
        first_name = "Fabiola"
        last_name = "Urizar"
        
        try:
            sede = Sede.objects.get(id=sede_id, status=True)
            self.stdout.write(f"Using sede: {sede.name} (ID: {sede.id})")
        except Sede.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Sede with ID {sede_id} not found or inactive")
            )
            return

        # Verificar si ya existe un usuario con este email
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.ERROR(f"User with email {email} already exists")
            )
            return

        # Generar username único basado en el nombre
        base_username = f"{first_name.lower()}.{last_name.lower()}"
        username = base_username
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Generar contraseña temporal
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = "".join(secrets.choice(characters) for _ in range(12))

        try:
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_enabled=True,
            )

            # Asignar grupo de cliente
            from django.contrib.auth.models import Group
            try:
                client_group = Group.objects.get(name="client")
                user.groups.add(client_group)
            except Group.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING("Client group not found, skipping group assignment")
                )

            # Asignar sede al usuario
            user.sede = sede
            user.save()

            # Crear perfil de cliente
            client = Client.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                email=email,
                sede=sede,
                status="I",  # Inactivo por defecto
                source="Creación manual - Fabiola Urizar"
            )

            # Enviar email de bienvenida
            try:
                send_user_generated_email(user, client, temp_password)
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Welcome email sent to {email}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error sending email: {str(e)}")
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🎉 User created successfully!\n"
                    f"Username: {username}\n"
                    f"Email: {email}\n"
                    f"Temporary Password: {temp_password}\n"
                    f"Sede: {sede.name}\n"
                    f"Client ID: {client.id}"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error creating user: {str(e)}")
            )
