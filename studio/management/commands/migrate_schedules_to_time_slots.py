from django.core.management.base import BaseCommand
from studio.models import Schedule, TimeSlot, Sede
from django.db import transaction


class Command(BaseCommand):
    help = 'Migrate existing schedules to use the new TimeSlot model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
        
        # Get all schedules that need migration
        schedules_to_migrate = Schedule.objects.filter(sede__isnull=False)
        
        self.stdout.write(f"Found {schedules_to_migrate.count()} schedules to migrate")
        
        migrated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for schedule in schedules_to_migrate:
                # Find matching TimeSlot for this schedule's sede and time_slot
                try:
                    time_slot = TimeSlot.objects.get(
                        sede=schedule.sede,
                        start_time=schedule.time_slot,
                        is_active=True
                    )
                    
                    if dry_run:
                        self.stdout.write(f"Would migrate Schedule {schedule.id}:")
                        self.stdout.write(f"  - Sede: {schedule.sede.name}")
                        self.stdout.write(f"  - Day: {schedule.day}")
                        self.stdout.write(f"  - Time: {schedule.time_slot}")
                        self.stdout.write(f"  - Would link to TimeSlot: {time_slot}")
                        self.stdout.write("-" * 50)
                    else:
                        # The schedule already has the correct time_slot value
                        # We just need to ensure it's valid
                        self.stdout.write(f"✅ Schedule {schedule.id} already compatible")
                    
                    migrated_count += 1
                    
                except TimeSlot.DoesNotExist:
                    # This schedule has a time_slot that doesn't exist in TimeSlot
                    self.stdout.write(f"⚠️  Schedule {schedule.id} has invalid time_slot: {schedule.time_slot}")
                    self.stdout.write(f"   Sede: {schedule.sede.name}")
                    self.stdout.write(f"   Day: {schedule.day}")
                    
                    # Try to find the closest TimeSlot
                    closest_time_slot = TimeSlot.objects.filter(
                        sede=schedule.sede,
                        is_active=True
                    ).order_by('start_time').first()
                    
                    if closest_time_slot:
                        if dry_run:
                            self.stdout.write(f"   Would update to: {closest_time_slot.start_time}")
                        else:
                            schedule.time_slot = closest_time_slot.start_time.strftime('%H:%M')
                            schedule.save()
                            self.stdout.write(f"   ✅ Updated to: {closest_time_slot.start_time}")
                        migrated_count += 1
                    else:
                        self.stdout.write(f"   ❌ No TimeSlots found for sede {schedule.sede.name}")
                        skipped_count += 1
        
        if dry_run:
            self.stdout.write(f"\nWould migrate: {migrated_count} schedules")
            self.stdout.write(f"Would skip: {skipped_count} schedules")
            self.stdout.write("Run without --dry-run to apply changes")
        else:
            self.stdout.write(f"\n✅ Migration completed!")
            self.stdout.write(f"✅ Migrated: {migrated_count} schedules")
            self.stdout.write(f"⚠️  Skipped: {skipped_count} schedules")
