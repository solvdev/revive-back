from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Client
from studio.models import Sede
from studio.management.mails.mails import send_user_generated_email
import secrets
import string

User = get_user_model()


class Command(BaseCommand):
    help = 'Create user account for existing Fabiola Urizar client and send welcome email'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting user creation for existing Fabiola Urizar client..."))

        # Buscar el cliente existente de Fabiola Urizar (Client ID: 9808)
        try:
            client = Client.objects.get(id=9808)
            self.stdout.write(f"Found existing client: {client.full_name} (ID: {client.id})")
            self.stdout.write(f"Email: {client.email}")
            self.stdout.write(f"Sede: {client.sede.name if client.sede else 'Sin sede'}")
            self.stdout.write(f"Status: {client.status}")
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR("Client with ID 9808 (Fabiola Urizar) not found"))
            return

        # Verificar si ya tiene cuenta de usuario
        if client.user:
            self.stdout.write(self.style.WARNING(f"Client already has user account: {client.user.username}"))
            return

        # Verificar que tenga sede asignada
        if not client.sede:
            self.stdout.write(self.style.ERROR("Client does not have a sede assigned"))
            return

        # Generar username único
        base_username = f"{client.first_name.lower()}.{client.last_name.lower()}"
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
                email=client.email,
                password=temp_password,
                first_name=client.first_name,
                last_name=client.last_name,
                is_active=True,
                is_enabled=True,
                sede=client.sede  # Asignar la misma sede del cliente
            )

            # Asignar grupo de cliente
            from django.contrib.auth.models import Group
            try:
                client_group = Group.objects.get(name="client")
                user.groups.add(client_group)
                self.stdout.write(f"User {username} assigned to client group")
            except Group.DoesNotExist:
                self.stdout.write(self.style.WARNING("Client group not found, skipping group assignment"))

            # Asociar el usuario con el cliente existente
            client.user = user
            client.save(skip_phone_validation=True)
            self.stdout.write(f"User {username} associated with existing client {client.full_name}")

            # Enviar email de bienvenida
            try:
                send_user_generated_email(user, client, temp_password)
                self.stdout.write(self.style.SUCCESS(f"✅ Welcome email sent to {client.email}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error sending email: {str(e)}"))

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🎉 User account created successfully for existing client!\n"
                    f"Client: {client.full_name} (ID: {client.id})\n"
                    f"Username: {username}\n"
                    f"Email: {client.email}\n"
                    f"Temporary Password: {temp_password}\n"
                    f"Sede: {client.sede.name}\n"
                    f"User ID: {user.id}"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error creating user: {str(e)}"))
