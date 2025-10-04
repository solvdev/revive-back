from django.core.management.base import BaseCommand
from accounts.models import Client
from studio.models import Payment
from django.utils import timezone

class Command(BaseCommand):
    help = "Debug client membership status"

    def add_arguments(self, parser):
        parser.add_argument('--client-id', type=int, help='Client ID to debug')
        parser.add_argument('--client-name', type=str, help='Client name to debug')

    def handle(self, *args, **options):
        client_id = options.get('client_id')
        client_name = options.get('client_name')
        
        if client_id:
            try:
                client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Client with ID {client_id} not found"))
                return
        elif client_name:
            clients = Client.objects.filter(first_name__icontains=client_name)
            if not clients.exists():
                self.stdout.write(self.style.ERROR(f"No clients found with name containing '{client_name}'"))
                return
            client = clients.first()
        else:
            self.stdout.write(self.style.ERROR("Please provide either --client-id or --client-name"))
            return

        self.stdout.write(f"\n🔍 Debugging Client: {client.full_name} (ID: {client.id})")
        self.stdout.write("=" * 50)
        
        # 1. Current membership
        self.stdout.write(f"📋 Current Membership: {client.current_membership}")
        if client.current_membership:
            self.stdout.write(f"   - Name: {client.current_membership.name}")
            self.stdout.write(f"   - Price: {client.current_membership.price}")
        
        # 2. Active membership (property)
        active_membership = client.active_membership
        self.stdout.write(f"✅ Active Membership: {active_membership}")
        if active_membership:
            self.stdout.write(f"   - Name: {active_membership.name}")
            self.stdout.write(f"   - Price: {active_membership.price}")
        
        # 3. Payments
        payments = Payment.objects.filter(client=client).order_by('-date_paid')
        self.stdout.write(f"\n💰 Payments ({payments.count()} total):")
        today = timezone.now().date()
        
        for i, payment in enumerate(payments[:5]):  # Show last 5 payments
            status = "✅ VALID" if payment.valid_until >= today else "❌ EXPIRED"
            self.stdout.write(f"   {i+1}. {payment.membership.name} - {payment.date_paid.date()} to {payment.valid_until} - {status}")
            self.stdout.write(f"      Amount: Q{payment.amount} - Method: {payment.payment_method}")
        
        # 4. Bookings
        bookings = client.booking_set.all().order_by('-class_date')[:3]
        self.stdout.write(f"\n📅 Recent Bookings ({bookings.count()} total):")
        for i, booking in enumerate(bookings):
            self.stdout.write(f"   {i+1}. {booking.class_date} - {booking.schedule}")
            self.stdout.write(f"      Membership: {booking.membership}")
            self.stdout.write(f"      Status: {booking.status} - Attendance: {booking.attendance_status}")
        
        # 5. Summary
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   - Client Status: {client.status}")
        self.stdout.write(f"   - Trial Used: {client.trial_used}")
        self.stdout.write(f"   - Sede: {client.sede}")
        self.stdout.write(f"   - Today: {today}")
        
        # 6. Recommendations
        self.stdout.write(f"\n💡 Recommendations:")
        if not client.current_membership:
            self.stdout.write("   ⚠️  current_membership is None - this should be updated when payment is created")
        if not active_membership:
            self.stdout.write("   ⚠️  active_membership is None - client appears to have no valid membership")
        if payments.exists() and not active_membership:
            latest_payment = payments.first()
            if latest_payment.valid_until < today:
                self.stdout.write(f"   ⚠️  Latest payment expired on {latest_payment.valid_until}")
            else:
                self.stdout.write("   ⚠️  Payment exists but active_membership is None - check current_membership update")
