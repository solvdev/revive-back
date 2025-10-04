from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import models
from accounts.models import Client

User = get_user_model()


class Command(BaseCommand):
    help = 'Search for clients by name or email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--search',
            type=str,
            help='Search term (name or email)',
            required=True
        )

    def handle(self, *args, **options):
        search_term = options['search'].lower()
        
        # Buscar clientes por nombre, apellido o email
        clients = Client.objects.filter(
            models.Q(first_name__icontains=search_term) |
            models.Q(last_name__icontains=search_term) |
            models.Q(email__icontains=search_term)
        )
        
        if clients.exists():
            self.stdout.write(f"Found {clients.count()} client(s) matching '{search_term}':")
            self.stdout.write("-" * 80)
            
            for client in clients:
                sede_name = client.sede.name if client.sede else "Sin sede"
                user_exists = client.user is not None
                
                self.stdout.write(f"Client ID: {client.id}")
                self.stdout.write(f"Name: {client.first_name} {client.last_name}")
                self.stdout.write(f"Email: {client.email}")
                self.stdout.write(f"DPI: {client.dpi}")
                self.stdout.write(f"Sede: {sede_name}")
                self.stdout.write(f"Status: {client.status}")
                self.stdout.write(f"Has User Account: {'Yes' if user_exists else 'No'}")
                if user_exists:
                    self.stdout.write(f"Username: {client.user.username}")
                self.stdout.write(f"Created: {client.created_at}")
                self.stdout.write("-" * 80)
        else:
            self.stdout.write(f"No clients found matching '{search_term}'")
