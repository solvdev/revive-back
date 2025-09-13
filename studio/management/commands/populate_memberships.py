from django.core.management.base import BaseCommand
from studio.models import Membership, Sede

class Command(BaseCommand):
    help = "Crea los paquetes de membresía según las políticas de Revive Studio con prioridades."

    def handle(self, *args, **options):
        # Obtener la sede Xela (ID 1)
        try:
            sede_xela = Sede.objects.get(id=1)
            self.stdout.write(f"✅ Sede encontrada: {sede_xela.name}")
        except Sede.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ No se encontró la sede con ID 1"))
            return

        # Definir los paquetes según las políticas de Revive
        memberships_data = [
            # Paquetes con ALTA PRIORIDAD (booking_priority=1)
            {
                'name': 'Reformer Revive Power',
                'price': 0,  # Precio a definir
                'classes_per_month': None,  # Ilimitado
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 1,
                'description': 'Paquete de alta prioridad para Pilates Reformer'
            },
            {
                'name': 'Revive Élite',
                'price': 0,  # Precio a definir
                'classes_per_month': None,  # Ilimitado
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 1,
                'description': 'Paquete Elite con prioridad de reserva'
            },
            {
                'name': 'Revive Élite Trimestral',
                'price': 0,  # Precio a definir
                'classes_per_month': None,  # Ilimitado
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 1,
                'description': 'Paquete Elite Trimestral con prioridad de reserva'
            },
            {
                'name': 'Élite Mat',
                'price': 0,  # Precio a definir
                'classes_per_month': None,  # Ilimitado
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 1,
                'description': 'Paquete Elite para Pilates Mat'
            },
            {
                'name': 'Élite Mat Trimestral',
                'price': 0,  # Precio a definir
                'classes_per_month': None,  # Ilimitado
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 1,
                'description': 'Paquete Elite Mat Trimestral'
            },
            {
                'name': 'Yoga Élite',
                'price': 0,  # Precio a definir
                'classes_per_month': None,  # Ilimitado
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 1,
                'description': 'Paquete Elite para Yoga'
            },
            
            # Paquetes con PRIORIDAD NORMAL (booking_priority=0)
            {
                'name': 'Paquete Básico',
                'price': 0,  # Precio a definir
                'classes_per_month': 8,
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 0,
                'description': 'Paquete básico con acceso según disponibilidad'
            },
            {
                'name': 'Paquete Intermedio',
                'price': 0,  # Precio a definir
                'classes_per_month': 12,
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 0,
                'description': 'Paquete intermedio con acceso según disponibilidad'
            },
            {
                'name': 'Clase Individual',
                'price': 0,  # Precio a definir
                'classes_per_month': 1,
                'scope': 'GLOBAL',
                'sede': None,
                'booking_priority': 0,
                'description': 'Clase individual'
            },
        ]

        created_count = 0

        for membership_data in memberships_data:
            membership, created = Membership.objects.get_or_create(
                name=membership_data['name'],
                defaults={
                    'price': membership_data['price'],
                    'classes_per_month': membership_data['classes_per_month'],
                    'scope': membership_data['scope'],
                    'sede': membership_data['sede'],
                    'booking_priority': membership_data['booking_priority'],
                }
            )
            
            if created:
                created_count += 1
                priority_text = "ALTA PRIORIDAD" if membership_data['booking_priority'] == 1 else "PRIORIDAD NORMAL"
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Creado: {membership.name} - {priority_text}"
                ))
            else:
                self.stdout.write(f"➡️ Ya existe: {membership.name}")

        self.stdout.write(self.style.SUCCESS(f"\n🎉 Total de nuevas membresías creadas: {created_count}"))
        self.stdout.write(f"📊 Resumen:")
        self.stdout.write(f"   - Paquetes con ALTA PRIORIDAD: {len([m for m in memberships_data if m['booking_priority'] == 1])}")
        self.stdout.write(f"   - Paquetes con PRIORIDAD NORMAL: {len([m for m in memberships_data if m['booking_priority'] == 0])}")
        self.stdout.write(f"\n💡 Los paquetes Elite/Power tienen prioridad de reserva en la plataforma")
        self.stdout.write(f"💡 Los demás paquetes tienen acceso según disponibilidad")
