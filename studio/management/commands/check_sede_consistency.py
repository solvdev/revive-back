# studio/management/commands/check_sede_consistency.py
from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import Client
from studio.models import Booking, Schedule, Payment, Venta, Membership, Promotion


class Command(BaseCommand):
    help = 'Verifica la consistencia de datos multi-sede'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Intentar corregir inconsistencias automáticamente',
        )

    def handle(self, *args, **options):
        self.stdout.write('Verificando consistencia de datos multi-sede...\n')
        
        issues_found = 0
        
        # 1. Verificar clientes sin sede
        clients_without_sede = Client.objects.filter(sede__isnull=True)
        if clients_without_sede.exists():
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {clients_without_sede.count()} clientes sin sede asignada'
                )
            )
            if options['fix']:
                # Asignar a la primera sede disponible
                first_sede = Sede.objects.first()
                if first_sede:
                    clients_without_sede.update(sede=first_sede)
                    self.stdout.write(f'  ✅ Asignados a sede: {first_sede.name}')
        
        # 2. Verificar bookings con sede inconsistente
        bookings_issues = []
        for booking in Booking.objects.select_related('client', 'schedule', 'sede'):
            if booking.client.sede and booking.sede and booking.client.sede != booking.sede:
                bookings_issues.append(booking)
            elif booking.schedule.sede and booking.sede and booking.schedule.sede != booking.sede:
                bookings_issues.append(booking)
        
        if bookings_issues:
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {len(bookings_issues)} bookings con sede inconsistente'
                )
            )
            if options['fix']:
                for booking in bookings_issues:
                    # Usar la sede del cliente como referencia
                    if booking.client.sede:
                        booking.sede = booking.client.sede
                        booking.save()
                        self.stdout.write(f'  ✅ Booking {booking.id} corregido')
        
        # 3. Verificar horarios sin sede
        schedules_without_sede = Schedule.objects.filter(sede__isnull=True)
        if schedules_without_sede.exists():
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {schedules_without_sede.count()} horarios sin sede asignada'
                )
            )
            if options['fix']:
                first_sede = Sede.objects.first()
                if first_sede:
                    schedules_without_sede.update(sede=first_sede)
                    self.stdout.write(f'  ✅ Asignados a sede: {first_sede.name}')
        
        # 4. Verificar pagos con sede inconsistente
        payments_issues = []
        for payment in Payment.objects.select_related('client', 'sede'):
            if payment.client.sede and payment.sede and payment.client.sede != payment.sede:
                payments_issues.append(payment)
        
        if payments_issues:
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {len(payments_issues)} pagos con sede inconsistente'
                )
            )
            if options['fix']:
                for payment in payments_issues:
                    if payment.client.sede:
                        payment.sede = payment.client.sede
                        payment.save()
                        self.stdout.write(f'  ✅ Pago {payment.id} corregido')
        
        # 5. Verificar ventas con sede inconsistente
        ventas_issues = []
        for venta in Venta.objects.select_related('client', 'sede'):
            if venta.client.sede and venta.sede and venta.client.sede != venta.sede:
                ventas_issues.append(venta)
        
        if ventas_issues:
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {len(ventas_issues)} ventas con sede inconsistente'
                )
            )
            if options['fix']:
                for venta in ventas_issues:
                    if venta.client.sede:
                        venta.sede = venta.client.sede
                        venta.save()
                        self.stdout.write(f'  ✅ Venta {venta.id} corregida')
        
        # 6. Verificar membresías de sede sin sede asignada
        memberships_issues = Membership.objects.filter(scope='SEDE', sede__isnull=True)
        if memberships_issues.exists():
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {memberships_issues.count()} membresías de sede sin sede asignada'
                )
            )
            if options['fix']:
                first_sede = Sede.objects.first()
                if first_sede:
                    memberships_issues.update(sede=first_sede)
                    self.stdout.write(f'  ✅ Asignadas a sede: {first_sede.name}')
        
        # 7. Verificar promociones de sede sin sede asignada
        promotions_issues = Promotion.objects.filter(scope='SEDE', sede__isnull=True)
        if promotions_issues.exists():
            issues_found += 1
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {promotions_issues.count()} promociones de sede sin sede asignada'
                )
            )
            if options['fix']:
                first_sede = Sede.objects.first()
                if first_sede:
                    promotions_issues.update(sede=first_sede)
                    self.stdout.write(f'  ✅ Asignadas a sede: {first_sede.name}')
        
        # Resumen
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ No se encontraron inconsistencias')
            )
        else:
            if options['fix']:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Se corrigieron {issues_found} tipos de inconsistencias')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Se encontraron {issues_found} tipos de inconsistencias. '
                        'Ejecuta con --fix para corregirlas automáticamente.'
                    )
                )
