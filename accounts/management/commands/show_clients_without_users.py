from django.core.management.base import BaseCommand
from accounts.models import Client


class Command(BaseCommand):
    help = 'Show clients without user accounts'

    def handle(self, *args, **options):
        clients_without_users = Client.objects.filter(user__isnull=True)
        
        self.stdout.write(f"Clientes sin usuario: {clients_without_users.count()}")
        self.stdout.write("-" * 80)
        
        for client in clients_without_users[:20]:  # Mostrar solo los primeros 20
            sede_name = client.sede.name if client.sede else "Sin sede"
            self.stdout.write(f"- {client.full_name} ({client.email}) - Sede: {sede_name}")
        
        if clients_without_users.count() > 20:
            self.stdout.write(f"... y {clients_without_users.count() - 20} más")
