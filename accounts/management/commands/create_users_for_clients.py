from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Client
from studio.management.mails.mails import send_user_generated_email
import secrets
import string

User = get_user_model()


class Command(BaseCommand):
    help = 'Create user accounts for clients who do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            default=2,
            help='Sede ID to filter clients (default: 2 - Punto Roosevelt)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of clients to process in each batch (default: 50)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not create users, just show what would be done',
        )
        parser.add_argument(
            '--send-emails',
            action='store_true',
            help='Send welcome emails to newly created users',
        )

    def handle(self, *args, **options):
        sede_id = options['sede_id']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        send_emails = options['send_emails']
        
        # Verificar que la sede existe
        try:
            from studio.models import Sede
            sede = Sede.objects.get(id=sede_id, status=True)
            self.stdout.write(f"Using sede: {sede.name} (ID: {sede.id})")
        except Sede.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Sede with ID {sede_id} not found or inactive"))
            return
        
        # Obtener clientes sin usuario de la sede específica
        clients_without_users = Client.objects.filter(user__isnull=True, sede_id=sede_id)
        total_clients = clients_without_users.count()
        
        self.stdout.write(f"Found {total_clients} clients without user accounts")
        
        if total_clients == 0:
            self.stdout.write(self.style.SUCCESS("All clients already have user accounts!"))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No users will be created"))
            self.stdout.write("\nFirst 10 clients that would get user accounts:")
            for client in clients_without_users[:10]:
                sede_name = client.sede.name if client.sede else "Sin sede"
                self.stdout.write(f"- {client.full_name} ({client.email}) - Sede: {sede_name}")
            return
        
        # Procesar por lotes
        created_count = 0
        error_count = 0
        
        for i in range(0, total_clients, batch_size):
            batch_clients = clients_without_users[i:i + batch_size]
            self.stdout.write(f"\nProcessing batch {i//batch_size + 1} ({len(batch_clients)} clients)...")
            
            for client in batch_clients:
                try:
                    # Verificar que el cliente tenga sede
                    if not client.sede:
                        self.stdout.write(
                            self.style.WARNING(f"⚠️  Skipping {client.full_name} - No sede assigned")
                        )
                        continue
                    
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
                    
                    # Crear usuario
                    user = User.objects.create_user(
                        username=username,
                        email=client.email,
                        password=temp_password,
                        first_name=client.first_name,
                        last_name=client.last_name,
                        is_active=True,
                        is_enabled=True,
                        sede=client.sede
                    )
                    
                    # Asignar grupo de cliente
                    from django.contrib.auth.models import Group
                    try:
                        client_group = Group.objects.get(name="client")
                        user.groups.add(client_group)
                    except Group.DoesNotExist:
                        pass
                    
                    # Asociar usuario con cliente
                    client.user = user
                    client.save(skip_phone_validation=True)
                    
                    # Enviar email si se solicita
                    if send_emails:
                        try:
                            send_user_generated_email(user, client, temp_password)
                            self.stdout.write(f"✅ {client.full_name} - Email sent")
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(f"⚠️  {client.full_name} - User created but email failed: {e}")
                            )
                    else:
                        self.stdout.write(f"✅ {client.full_name} - User created (no email)")
                    
                    created_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error creating user for {client.full_name}: {e}")
                    )
                    error_count += 1
        
        # Resumen final
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Process completed!"))
        self.stdout.write(f"✅ Users created: {created_count}")
        if error_count > 0:
            self.stdout.write(f"❌ Errors: {error_count}")
        
        remaining = Client.objects.filter(user__isnull=True).count()
        if remaining > 0:
            self.stdout.write(f"⚠️  {remaining} clients still without user accounts")
        else:
            self.stdout.write(self.style.SUCCESS("🎉 All clients now have user accounts!"))
