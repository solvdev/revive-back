from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Client
from studio.models import Sede

User = get_user_model()


class Command(BaseCommand):
    help = 'Create client records for users that don\'t have associated clients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='Sede ID to assign to new clients',
            required=True
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes',
        )
        parser.add_argument(
            '--status',
            type=str,
            default='I',
            choices=['A', 'I'],
            help='Status for new clients (A=Active, I=Inactive). Default: I',
        )

    def handle(self, *args, **options):
        sede_id = options['sede_id']
        dry_run = options['dry_run']
        status = options['status']

        try:
            sede = Sede.objects.get(id=sede_id, status=True)
            self.stdout.write(f"Using sede: {sede.name} (ID: {sede.id})")
        except Sede.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Sede with ID {sede_id} not found or inactive")
            )
            return

        # Find users without client profiles (excluding staff users)
        users_without_clients = User.objects.filter(
            client_profile__isnull=True,
            is_staff=False  # Exclude staff users
        )
        
        self.stdout.write(f"Found {users_without_clients.count()} non-staff users without client profiles")
        
        if users_without_clients.count() == 0:
            self.stdout.write(self.style.SUCCESS("All users already have client profiles!"))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            self.stdout.write("\nUsers that would get client profiles:")
            self.stdout.write("-" * 80)
            
            for user in users_without_clients:
                self.stdout.write(f"User: {user.username}")
                self.stdout.write(f"  - Name: {user.first_name} {user.last_name}")
                self.stdout.write(f"  - Email: {user.email}")
                self.stdout.write(f"  - Sede: {sede.name}")
                self.stdout.write(f"  - Status: {status}")
                self.stdout.write(f"  - Created: {user.date_joined}")
                self.stdout.write("-" * 80)
        else:
            created_count = 0
            
            for user in users_without_clients:
                try:
                    # Create client profile
                    client = Client.objects.create(
                        user=user,
                        first_name=user.first_name or '',
                        last_name=user.last_name or '',
                        email=user.email,
                        sede=sede,
                        status=status,
                        source="Migración automática - Usuario sin cliente"
                    )
                    
                    created_count += 1
                    self.stdout.write(f"✅ Created client for user: {user.username}")
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error creating client for user {user.username}: {str(e)}")
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully created {created_count} client profiles"
                )
            )
            
            # Show summary
            remaining_users = User.objects.filter(client_profile__isnull=True).count()
            if remaining_users > 0:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {remaining_users} users still without client profiles")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("🎉 All users now have client profiles!")
                )
