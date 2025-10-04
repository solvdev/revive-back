from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Client
from studio.models import Payment
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Test active_membership logic'

    def handle(self, *args, **options):
        # Find a client with payments
        client = Client.objects.filter(payment__isnull=False).first()
        
        if not client:
            self.stdout.write("No clients with payments found")
            return
        
        self.stdout.write(f"Testing client: {client.full_name}")
        
        # Show all payments
        payments = Payment.objects.filter(client=client).order_by('-date_paid')
        self.stdout.write(f"\nAll payments for {client.full_name}:")
        
        today = timezone.now().date()
        for payment in payments:
            self.stdout.write(f"- Payment {payment.id}:")
            self.stdout.write(f"  - Membership: {payment.membership.name}")
            self.stdout.write(f"  - Date paid: {payment.date_paid.date()}")
            self.stdout.write(f"  - Valid from: {payment.valid_from}")
            self.stdout.write(f"  - Valid until: {payment.valid_until}")
            
            # Check if this payment would be considered active
            is_active = (
                payment.valid_from and 
                payment.valid_until and
                payment.valid_from <= today and 
                payment.valid_until >= today
            )
            self.stdout.write(f"  - Would be active today: {is_active}")
            self.stdout.write("-" * 40)
        
        # Test the active_membership property
        active_membership = client.active_membership
        self.stdout.write(f"\nActive membership property: {active_membership}")
        
        if active_membership:
            self.stdout.write(f"- Name: {active_membership.name}")
            self.stdout.write(f"- Price: {active_membership.price}")
        
        # Test with a specific date (e.g., October 1st)
        october_1st = timezone.datetime(2024, 10, 1).date()
        self.stdout.write(f"\nTesting with October 1st, 2024:")
        
        # Manually check what would be active on Oct 1st
        october_payments = Payment.objects.filter(
            client=client,
            valid_from__lte=october_1st,
            valid_until__gte=october_1st
        ).order_by('valid_until')
        
        self.stdout.write(f"Payments active on Oct 1st: {october_payments.count()}")
        for payment in october_payments:
            self.stdout.write(f"- {payment.membership.name} (valid until: {payment.valid_until})")
