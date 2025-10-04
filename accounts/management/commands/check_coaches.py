# accounts/management/commands/check_coaches.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Verificar grupos y coaches en el sistema'

    def handle(self, *args, **options):
        # Mostrar todos los grupos disponibles
        self.stdout.write(self.style.SUCCESS('=== GRUPOS DISPONIBLES ==='))
        groups = Group.objects.all()
        if groups.exists():
            for group in groups:
                self.stdout.write(f'- {group.name}')
        else:
            self.stdout.write(self.style.WARNING('No hay grupos en el sistema'))
        
        # Verificar grupo coach
        self.stdout.write(self.style.SUCCESS('\n=== VERIFICACIÓN GRUPO COACH ==='))
        coach_group = Group.objects.filter(name='coach').first()
        
        if coach_group:
            self.stdout.write(f'[OK] Grupo "coach" existe (ID: {coach_group.id})')
            
            # Buscar usuarios con grupo coach
            coaches = CustomUser.objects.filter(groups=coach_group)
            self.stdout.write(f'[OK] Coaches encontrados: {coaches.count()}')
            
            if coaches.exists():
                self.stdout.write(self.style.SUCCESS('\n=== COACHES ==='))
                for coach in coaches:
                    self.stdout.write(f'- {coach.username} ({coach.first_name} {coach.last_name}) - Activo: {coach.is_active} - Sede: {coach.sede}')
            else:
                self.stdout.write(self.style.WARNING('No hay usuarios asignados al grupo coach'))
        else:
            self.stdout.write(self.style.ERROR('[ERROR] Grupo "coach" NO existe'))
            self.stdout.write('Creando grupo coach...')
            coach_group = Group.objects.create(name='coach')
            self.stdout.write(f'[OK] Grupo "coach" creado (ID: {coach_group.id})')
        
        # Verificar usuarios staff que podrían ser coaches
        self.stdout.write(self.style.SUCCESS('\n=== USUARIOS STAFF (posibles coaches) ==='))
        staff_users = CustomUser.objects.filter(is_staff=True)
        for user in staff_users:
            user_groups = [g.name for g in user.groups.all()]
            self.stdout.write(f'- {user.username} ({user.first_name} {user.last_name}) - Grupos: {user_groups}')
