from django.core.management.base import BaseCommand
from studio.models import Sede


class Command(BaseCommand):
    help = "Create initial sedes for multisite support"

    def add_arguments(self, parser):
        parser.add_argument(
            "--default",
            action="store_true",
            help="Create a default sede for existing data",
        )

    def handle(self, *args, **options):
        if options["default"]:
            # Create a default sede for existing data
            sede, created = Sede.objects.get_or_create(
                slug="principal_SL", defaults={"name": "San Lucas", "status": True}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created default sede: {sede.name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Default sede already exists: {sede.name}")
                )
        else:
            # Create sample sedes
            sedes_data = [
                {"name": "San Lucas", "slug": "principal_SL", "status": True},
                {"name": "Punto Roosevelt", "slug": "centro_PR", "status": True},
            ]

            created_count = 0
            for sede_data in sedes_data:
                sede, created = Sede.objects.get_or_create(
                    slug=sede_data["slug"], defaults=sede_data
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully created sede: {sede.name}")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Sede already exists: {sede.name}")
                    )

            self.stdout.write(self.style.SUCCESS(f"Created {created_count} new sedes"))
