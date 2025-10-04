from django.core.management.base import BaseCommand
from studio.models import Sede, TimeSlot
from datetime import time


class Command(BaseCommand):
    help = 'Create initial time slots for each sede'

    def handle(self, *args, **options):
        # Time slots para Sede 1 (San Lucas)
        san_lucas_slots = [
            (time(5, 0), time(6, 0)),   # 05:00 - 06:00
            (time(6, 0), time(7, 0)),   # 06:00 - 07:00
            (time(7, 0), time(8, 0)),   # 07:00 - 08:00
            (time(8, 0), time(9, 0)),   # 08:00 - 09:00
            (time(9, 0), time(10, 0)),  # 09:00 - 10:00
            (time(10, 0), time(11, 0)), # 10:00 - 11:00
            (time(11, 0), time(12, 0)), # 11:00 - 12:00
            (time(12, 0), time(13, 0)),  # 12:00 - 13:00
            (time(16, 0), time(17, 0)),  # 16:00 - 17:00
            (time(17, 0), time(18, 0)),  # 17:00 - 18:00
            (time(18, 0), time(19, 0)),  # 18:00 - 19:00
            (time(19, 0), time(20, 0)),  # 19:00 - 20:00
        ]
        
        # Time slots para Sede 2 (Punto Roosevelt)
        punto_roosevelt_slots = [
            (time(5, 0), time(6, 0)),   # 05:00 - 06:00
            (time(6, 0), time(7, 0)),   # 06:00 - 07:00
            (time(7, 0), time(8, 0)),   # 07:00 - 08:00
            (time(8, 0), time(9, 0)),   # 08:00 - 09:00
            (time(9, 0), time(10, 0)),  # 09:00 - 10:00
            (time(10, 0), time(11, 0)), # 10:00 - 11:00
            (time(11, 0), time(12, 0)), # 11:00 - 12:00
            (time(12, 0), time(13, 0)),  # 12:00 - 13:00
            (time(16, 30), time(17, 30)), # 16:30 - 17:30
            (time(17, 30), time(18, 30)), # 17:30 - 18:30
            (time(18, 30), time(19, 30)), # 18:30 - 19:30
            (time(19, 30), time(20, 30)), # 19:30 - 20:30
        ]
        
        # Obtener las sedes
        try:
            san_lucas = Sede.objects.get(id=1)
            punto_roosevelt = Sede.objects.get(id=2)
        except Sede.DoesNotExist:
            self.stdout.write(self.style.ERROR("No se encontraron las sedes. Asegúrate de que existan las sedes con ID 1 y 2."))
            return
        
        # Crear time slots para San Lucas
        self.stdout.write("Creando time slots para San Lucas...")
        for start_time, end_time in san_lucas_slots:
            time_slot, created = TimeSlot.objects.get_or_create(
                sede=san_lucas,
                start_time=start_time,
                end_time=end_time,
                defaults={'is_active': True}
            )
            if created:
                self.stdout.write(f"✅ Creado: {time_slot}")
            else:
                self.stdout.write(f"⚠️  Ya existe: {time_slot}")
        
        # Crear time slots para Punto Roosevelt
        self.stdout.write("\nCreando time slots para Punto Roosevelt...")
        for start_time, end_time in punto_roosevelt_slots:
            time_slot, created = TimeSlot.objects.get_or_create(
                sede=punto_roosevelt,
                start_time=start_time,
                end_time=end_time,
                defaults={'is_active': True}
            )
            if created:
                self.stdout.write(f"✅ Creado: {time_slot}")
            else:
                self.stdout.write(f"⚠️  Ya existe: {time_slot}")
        
        self.stdout.write(self.style.SUCCESS("\n🎉 Time slots creados exitosamente!"))
