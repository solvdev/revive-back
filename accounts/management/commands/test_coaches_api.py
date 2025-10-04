# accounts/management/commands/test_coaches_api.py
from django.core.management.base import BaseCommand
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Probar el endpoint de coaches con autenticación real'

    def handle(self, *args, **options):
        # Crear un cliente de prueba
        client = Client()
        
        # Obtener un usuario admin
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No hay usuario superuser disponible'))
            return
        
        # Autenticar al usuario
        client.force_login(admin_user)
        
        # Probar el endpoint de coaches
        url = '/api/accounts/users/coaches/'
        
        # Probar sin headers de sede
        self.stdout.write(self.style.SUCCESS('=== PROBANDO SIN HEADERS DE SEDE ==='))
        response = client.get(url)
        self.stdout.write(f'Status: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            self.stdout.write(f'Coaches encontrados: {len(data)}')
            for coach in data:
                self.stdout.write(f'- {coach.get("username", "N/A")} ({coach.get("first_name", "")} {coach.get("last_name", "")})')
        else:
            self.stdout.write(f'Error: {response.content.decode()}')
        
        # Probar con headers de sede
        self.stdout.write(self.style.SUCCESS('\n=== PROBANDO CON HEADERS DE SEDE ==='))
        response = client.get(url, HTTP_X_SEDES_SELECTED='1')
        self.stdout.write(f'Status: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            self.stdout.write(f'Coaches encontrados: {len(data)}')
            for coach in data:
                self.stdout.write(f'- {coach.get("username", "N/A")} ({coach.get("first_name", "")} {coach.get("last_name", "")})')
        else:
            self.stdout.write(f'Error: {response.content.decode()}')
        
        # Probar con parámetros de sede
        self.stdout.write(self.style.SUCCESS('\n=== PROBANDO CON PARÁMETROS DE SEDE ==='))
        response = client.get(url, {'sede_ids': '1'})
        self.stdout.write(f'Status: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            self.stdout.write(f'Coaches encontrados: {len(data)}')
            for coach in data:
                self.stdout.write(f'- {coach.get("username", "N/A")} ({coach.get("first_name", "")} {coach.get("last_name", "")})')
        else:
            self.stdout.write(f'Error: {response.content.decode()}')
