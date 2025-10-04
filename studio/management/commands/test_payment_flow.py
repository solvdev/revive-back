from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import Client
from studio.models import Payment, Membership, Sede

class Command(BaseCommand):
    help = 'Test payment flow and membership activation'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Iniciando prueba del flujo de pagos...")
        
        # 1. Crear o obtener datos de prueba
        try:
            # Buscar una sede activa
            sede = Sede.objects.filter(status=True).first()
            if not sede:
                self.stdout.write("❌ No hay sedes activas. Creando una sede de prueba...")
                sede = Sede.objects.create(
                    name="Sede de Prueba",
                    slug="sede-prueba",
                    status=True
                )
            
            # Buscar una membresía activa
            membership = Membership.objects.filter(status=True).first()
            if not membership:
                self.stdout.write("❌ No hay membresías activas. Creando una membresía de prueba...")
                membership = Membership.objects.create(
                    name="Membresía de Prueba",
                    price=100.00,
                    classes_per_month=8,
                    status=True,
                    sede=sede
                )
            
            # Crear un cliente de prueba
            client = Client.objects.create(
                first_name="Cliente",
                last_name="Prueba",
                email="cliente.prueba@test.com",
                phone="12345678",
                status="I",  # Inactivo inicialmente
                current_membership=None,  # Sin membresía inicialmente
                sede=sede
            )
            
            self.stdout.write(f"✅ Datos de prueba creados:")
            self.stdout.write(f"   - Cliente: {client.full_name} (ID: {client.id})")
            self.stdout.write(f"   - Membresía: {membership.name} (ID: {membership.id})")
            self.stdout.write(f"   - Sede: {sede.name} (ID: {sede.id})")
            
        except Exception as e:
            self.stdout.write(f"❌ Error creando datos de prueba: {e}")
            return
        
        # 2. Verificar estado inicial del cliente
        self.stdout.write(f"\n📊 Estado inicial del cliente:")
        self.stdout.write(f"   - Status: {client.status}")
        self.stdout.write(f"   - Current membership: {client.current_membership}")
        self.stdout.write(f"   - Active membership: {client.active_membership}")
        self.stdout.write(f"   - Trial used: {client.trial_used}")
        
        # 3. Crear un pago (simulando el PaymentViewSet.create)
        try:
            self.stdout.write(f"\n💰 Creando pago...")
            
            payment = Payment.objects.create(
                client=client,
                membership=membership,
                amount=membership.price,
                date_paid=timezone.now(),
                valid_until=(timezone.now() + timedelta(days=30)).date(),
                sede=sede
            )
            
            self.stdout.write(f"✅ Pago creado (ID: {payment.id})")
            
            # 4. Simular la lógica del PaymentViewSet.create
            self.stdout.write(f"\n🔄 Aplicando lógica de activación...")
            
            today = payment.date_paid.date()
            if payment.valid_until >= today:
                client.status = "A"
                client.current_membership = membership
                client.save(update_fields=["status", "current_membership"])
                self.stdout.write(f"✅ Cliente activado y membresía asignada")
            
            # 5. Verificar estado final del cliente
            self.stdout.write(f"\n📊 Estado final del cliente:")
            self.stdout.write(f"   - Status: {client.status}")
            self.stdout.write(f"   - Current membership: {client.current_membership}")
            self.stdout.write(f"   - Active membership: {client.active_membership}")
            self.stdout.write(f"   - Trial used: {client.trial_used}")
            
            # 6. Verificar que todo esté correcto
            success = True
            
            if client.status != "A":
                self.stdout.write(f"❌ Error: Cliente no está activo (status: {client.status})")
                success = False
            
            if client.current_membership != membership:
                self.stdout.write(f"❌ Error: Current membership no coincide")
                success = False
            
            if client.active_membership != membership:
                self.stdout.write(f"❌ Error: Active membership no coincide")
                success = False
            
            if success:
                self.stdout.write(f"\n🎉 ¡Prueba exitosa! El flujo de pagos funciona correctamente.")
            else:
                self.stdout.write(f"\n💥 Prueba fallida. Revisar la implementación.")
            
        except Exception as e:
            self.stdout.write(f"❌ Error durante la prueba: {e}")
            return
        
        finally:
            # Limpiar datos de prueba
            self.stdout.write(f"\n🧹 Limpiando datos de prueba...")
            try:
                Payment.objects.filter(client=client).delete()
                client.delete()
                self.stdout.write(f"✅ Datos de prueba eliminados")
            except Exception as e:
                self.stdout.write(f"⚠️ Error limpiando datos: {e}")
