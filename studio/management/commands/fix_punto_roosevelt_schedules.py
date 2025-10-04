from django.core.management.base import BaseCommand
from studio.models import Schedule, TimeSlot, Sede, ClassType
from django.db import transaction

class Command(BaseCommand):
    help = 'Corrige los horarios de Punto Roosevelt para que empiecen a las 16:30'

    def handle(self, *args, **options):
        try:
            punto_roosevelt = Sede.objects.get(name="Punto Roosevelt")
            pilates_reformer = ClassType.objects.get(name="Pilates Reformer")
            
            with transaction.atomic():
                # Actualizar schedules existentes de 17:30 a 16:30
                schedules_to_update = Schedule.objects.filter(
                    sede=punto_roosevelt,
                    time_slot='17:30'
                )
                
                updated_count = 0
                for schedule in schedules_to_update:
                    schedule.time_slot = '16:30'
                    schedule.save()
                    updated_count += 1
                    self.stdout.write(f"✅ Actualizado: {schedule.get_day_display()} {schedule.time_slot}")
                
                # Actualizar schedules de 18:30 a 17:30
                schedules_1830 = Schedule.objects.filter(
                    sede=punto_roosevelt,
                    time_slot='18:30'
                )
                
                for schedule in schedules_1830:
                    schedule.time_slot = '17:30'
                    schedule.save()
                    updated_count += 1
                    self.stdout.write(f"✅ Actualizado: {schedule.get_day_display()} {schedule.time_slot}")
                
                # Actualizar schedules de 19:30 a 18:30
                schedules_1930 = Schedule.objects.filter(
                    sede=punto_roosevelt,
                    time_slot='19:30'
                )
                
                for schedule in schedules_1930:
                    schedule.time_slot = '18:30'
                    schedule.save()
                    updated_count += 1
                    self.stdout.write(f"✅ Actualizado: {schedule.get_day_display()} {schedule.time_slot}")
                
                # Actualizar schedules de 20:30 a 19:30
                schedules_2030 = Schedule.objects.filter(
                    sede=punto_roosevelt,
                    time_slot='20:30'
                )
                
                for schedule in schedules_2030:
                    schedule.time_slot = '19:30'
                    schedule.save()
                    updated_count += 1
                    self.stdout.write(f"✅ Actualizado: {schedule.get_day_display()} {schedule.time_slot}")
                
                self.stdout.write(self.style.SUCCESS(f"\n🎉 Se actualizaron {updated_count} schedules en Punto Roosevelt"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
