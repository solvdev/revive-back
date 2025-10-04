from django.core.management.base import BaseCommand
from studio.models import Payment
from django.utils import timezone


class Command(BaseCommand):
    help = 'Fix valid_from dates for existing payments to use payment date instead of month start'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find payments where valid_from is different from date_paid date
        payments_to_fix = Payment.objects.filter(
            valid_from__isnull=False,
            date_paid__isnull=False
        ).exclude(
            valid_from=timezone.now().date()  # Exclude today's payments
        )
        
        self.stdout.write(f"Found {payments_to_fix.count()} payments to review")
        
        fixed_count = 0
        for payment in payments_to_fix:
            payment_date = payment.date_paid.date()
            valid_from_date = payment.valid_from
            
            # Check if valid_from is different from payment date
            if valid_from_date != payment_date:
                if dry_run:
                    self.stdout.write(f"Would fix Payment {payment.id}:")
                    self.stdout.write(f"  - Client: {payment.client.full_name}")
                    self.stdout.write(f"  - Membership: {payment.membership.name}")
                    self.stdout.write(f"  - Current valid_from: {valid_from_date}")
                    self.stdout.write(f"  - Payment date: {payment_date}")
                    self.stdout.write(f"  - Would change valid_from to: {payment_date}")
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
