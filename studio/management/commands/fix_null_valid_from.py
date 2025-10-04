from django.core.management.base import BaseCommand
from studio.models import Payment
from django.utils import timezone


class Command(BaseCommand):
    help = 'Fix payments with null valid_from by setting it to date_paid'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find payments with null valid_from
        payments_to_fix = Payment.objects.filter(valid_from__isnull=True)
        
        self.stdout.write(f"Found {payments_to_fix.count()} payments with null valid_from")
        
        fixed_count = 0
        for payment in payments_to_fix:
            if payment.date_paid:
                payment_date = payment.date_paid.date()
                
                if dry_run:
                    self.stdout.write(f"Would fix Payment {payment.id}:")
                    self.stdout.write(f"  - Client: {payment.client.full_name}")
                    self.stdout.write(f"  - Membership: {payment.membership.name}")
                    self.stdout.write(f"  - Date paid: {payment_date}")
                    self.stdout.write(f"  - Valid until: {payment.valid_until}")
                    self.stdout.write(f"  - Would set valid_from to: {payment_date}")
                    self.stdout.write("-" * 50)
                else:
                    payment.valid_from = payment_date
                    payment.save(update_fields=['valid_from'])
                    self.stdout.write(f"✅ Fixed Payment {payment.id} for {payment.client.full_name}")
                
                fixed_count += 1
        
        if dry_run:
            self.stdout.write(f"\nWould fix {fixed_count} payments")
            self.stdout.write("Run without --dry-run to apply changes")
        else:
            self.stdout.write(f"\n✅ Fixed {fixed_count} payments")
