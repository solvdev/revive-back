from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Client
from studio.models import Sede

User = get_user_model()


class Command(BaseCommand):
    help = 'Fix users and clients that don\'t have sede assigned'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='Sede ID to assign to users without sede',
            required=True
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        sede_id = options['sede_id']
        dry_run = options['dry_run']

        try:
            sede = Sede.objects.get(id=sede_id, status=True)
            self.stdout.write(f"Using sede: {sede.name} (ID: {sede.id})")
        except Sede.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Sede with ID {sede_id} not found or inactive")
            )
            return

        # Find users without sede
        users_without_sede = User.objects.filter(sede__isnull=True)
        self.stdout.write(f"Found {users_without_sede.count()} users without sede")

        # Find clients without sede
        clients_without_sede = Client.objects.filter(sede__isnull=True)
        self.stdout.write(f"Found {clients_without_sede.count()} clients without sede")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            
            for user in users_without_sede:
                self.stdout.write(f"Would assign sede {sede.name} to user: {user.username}")
            
            for client in clients_without_sede:
                self.stdout.write(f"Would assign sede {sede.name} to client: {client.full_name}")
        else:
            # Update users
            updated_users = users_without_sede.update(sede=sede)
            self.stdout.write(f"Updated {updated_users} users with sede {sede.name}")

            # Update clients
            updated_clients = clients_without_sede.update(sede=sede)
            self.stdout.write(f"Updated {updated_clients} clients with sede {sede.name}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully assigned sede {sede.name} to {updated_users} users and {updated_clients} clients"
                )
            )
