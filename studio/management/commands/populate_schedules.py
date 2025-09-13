from django.core.management.base import BaseCommand
from studio.models import Schedule, ClassType, Sede

class Command(BaseCommand):
    help = "Popula la tabla Schedule con horarios de 6:00 AM a 9:00 PM, lunes a domingo, con los tipos de clase sin coaches asignados."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Limpiar todos los schedules existentes antes de crear nuevos',
        )

    def handle(self, *args, **options):
        # Limpiar datos existentes si se solicita
        if options['clean']:
            deleted_count = Schedule.objects.count()
            Schedule.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"🗑️ Eliminados {deleted_count} schedules existentes"))

        # Obtener la sede Xela (ID 1)
        try:
            sede_xela = Sede.objects.get(id=1)
            self.stdout.write(f"✅ Sede encontrada: {sede_xela.name}")
        except Sede.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ No se encontró la sede con ID 1"))
            return

        # Crear los tipos de clase según el horario real
        pilates_reformer, _ = ClassType.objects.get_or_create(
            name="Pilates Reformer",
            defaults={"description": "Clase de Pilates Reformer - Máxima capacidad: 10 personas"}
        )
        
        pilates_mat, _ = ClassType.objects.get_or_create(
            name="Pilates Mat",
            defaults={"description": "Clase de Pilates Mat - Máxima capacidad: 10 personas"}
        )
        
        yoga, _ = ClassType.objects.get_or_create(
            name="Yoga",
            defaults={"description": "Clase de Yoga - Máxima capacidad: 10 personas"}
        )
        
        personalizada, _ = ClassType.objects.get_or_create(
            name="Personalizada",
            defaults={"description": "Clase Personalizada - Máxima capacidad: 1 persona"}
        )
        
        yoga_mat, _ = ClassType.objects.get_or_create(
            name="Yoga/Mat",
            defaults={"description": "Clase combinada Yoga/Mat - Máxima capacidad: 10 personas"}
        )
        
        self.stdout.write("✅ Tipos de clase creados:")
        self.stdout.write(f"   - {pilates_reformer.name}")
        self.stdout.write(f"   - {pilates_mat.name}")
        self.stdout.write(f"   - {yoga.name}")
        self.stdout.write(f"   - {personalizada.name}")
        self.stdout.write(f"   - {yoga_mat.name}")

        # Definir horarios usando solo los TIME_SLOTS válidos del modelo Schedule
        schedule_data = [
            {'time': '06:00', 'display': '06:00 - 07:00', 'class_type': 'Pilates Reformer', 'audience': 'Adultos'},
            {'time': '07:00', 'display': '07:00 - 08:00', 'class_type': 'Pilates Reformer', 'audience': 'Adultos'},
            {'time': '08:00', 'display': '08:00 - 09:00', 'class_type': 'Pilates Mat', 'audience': 'Adultos'},
            {'time': '09:00', 'display': '09:00 - 10:00', 'class_type': 'Yoga', 'audience': 'Adultos'},
            {'time': '10:00', 'display': '10:00 - 11:00', 'class_type': 'Pilates Reformer', 'audience': 'Adultos'},
            {'time': '11:00', 'display': '11:00 - 12:00', 'class_type': 'Personalizada', 'audience': 'Adultos'},
            {'time': '12:00', 'display': '12:00 - 13:00', 'class_type': 'Personalizada', 'audience': 'Adultos'},
            {'time': '16:00', 'display': '16:00 - 17:00', 'class_type': 'Pilates Reformer', 'audience': 'Teens'},
            {'time': '17:00', 'display': '17:00 - 18:00', 'class_type': 'Yoga/Mat', 'audience': 'Teens'},
            {'time': '18:00', 'display': '18:00 - 19:00', 'class_type': 'Yoga', 'audience': 'Adultos'},
            {'time': '19:00', 'display': '19:00 - 20:00', 'class_type': 'Pilates Mat', 'audience': 'Adultos'},
            {'time': '20:00', 'display': '20:00 - 21:00', 'class_type': 'Pilates Reformer', 'audience': 'Adultos'},
        ]

        # Días de la semana (lunes a domingo)
        days = [
            ('MON', 'Lunes'),
            ('TUE', 'Martes'),
            ('WED', 'Miércoles'),
            ('THU', 'Jueves'),
            ('FRI', 'Viernes'),
            ('SAT', 'Sábado'),
            ('SUN', 'Domingo'),
        ]

        # Mapeo de tipos de clase
        class_type_mapping = {
            'Pilates Reformer': pilates_reformer,
            'Pilates Mat': pilates_mat,
            'Yoga': yoga,
            'Personalizada': personalizada,
            'Yoga/Mat': yoga_mat,
        }

        created_count = 0

        for day_code, day_name in days:
            self.stdout.write(f"\n📅 Procesando {day_name}...")
            
            for schedule_info in schedule_data:
                class_type = class_type_mapping[schedule_info['class_type']]
                
                # Determinar capacidad según el tipo de clase
                if schedule_info['class_type'] == 'Personalizada':
                    capacity = 1
                    is_individual = True
                else:
                    capacity = 10
                    is_individual = False
                
                    schedule, created = Schedule.objects.get_or_create(
                        day=day_code,
                        time_slot=schedule_info['time'],
                        class_type=class_type,
                        sede=sede_xela,
                        defaults={
                            'is_individual': is_individual,
                            'capacity': capacity,
                            'coach': None,   # Sin coach asignado
                            'class_duration_minutes': 50,  # 50 minutos de clase
                            'preparation_time_minutes': 10,  # 10 minutos de preparación
                            'late_tolerance_minutes': 5,  # 5 minutos de tolerancia
                        }
                    )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Creado: {day_name} {schedule_info['display']} - {schedule_info['class_type']} ({schedule_info['audience']}) - {sede_xela.name}"
                    ))
                else:
                    self.stdout.write(f"➡️ Ya existe: {day_name} {schedule_info['display']} - {schedule_info['class_type']} - {sede_xela.name}")

        self.stdout.write(self.style.SUCCESS(f"\n🎉 Total de nuevos schedules creados: {created_count}"))
        self.stdout.write(f"📊 Resumen:")
        self.stdout.write(f"   - Sede: {sede_xela.name} (ID: {sede_xela.id})")
        self.stdout.write(f"   - Días: {len(days)} (Lunes a Domingo)")
        self.stdout.write(f"   - Horarios específicos: {len(schedule_data)}")
        self.stdout.write(f"   - Tipos de clase: {len(class_type_mapping)}")
        self.stdout.write(f"   - Total slots por día: {len(schedule_data)}")
        self.stdout.write(f"   - Total slots semanales: {len(days) * len(schedule_data)}")
        self.stdout.write(f"\n📋 Horarios creados:")
        for schedule_info in schedule_data:
            self.stdout.write(f"   - {schedule_info['display']}: {schedule_info['class_type']} ({schedule_info['audience']})")
        
        self.stdout.write(f"\n💡 Para limpiar y recrear todos los horarios:")
        self.stdout.write(f"   python manage.py populate_schedules --clean")
