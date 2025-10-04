from decimal import Decimal

from accounts.models import Client
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from studio.models import Booking, Membership, Payment, Schedule, Sede, Venta

User = get_user_model()


class SedeModelTest(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(name="Sede Test", slug="test", status=True)

    def test_sede_creation(self):
        self.assertEqual(self.sede.name, "Sede Test")
        self.assertEqual(self.sede.slug, "test")
        self.assertTrue(self.sede.status)

    def test_sede_str(self):
        self.assertEqual(str(self.sede), "Sede Test")


class MembershipScopeTest(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(name="Sede Test", slug="test", status=True)

    def test_global_membership(self):
        membership = Membership.objects.create(
            name="Global Membership", price=Decimal("100.00"), scope="GLOBAL"
        )
        self.assertEqual(membership.scope, "GLOBAL")
        self.assertIsNone(membership.sede)

    def test_sede_membership(self):
        membership = Membership.objects.create(
            name="Sede Membership", price=Decimal("80.00"), scope="SEDE", sede=self.sede
        )
        self.assertEqual(membership.scope, "SEDE")
        self.assertEqual(membership.sede, self.sede)

    def test_membership_validation_global_with_sede(self):
        with self.assertRaises(Exception):
            membership = Membership(
                name="Invalid Global",
                price=Decimal("100.00"),
                scope="GLOBAL",
                sede=self.sede,
            )
            membership.clean()

    def test_membership_validation_sede_without_sede(self):
        with self.assertRaises(Exception):
            membership = Membership(
                name="Invalid Sede", price=Decimal("80.00"), scope="SEDE"
            )
            membership.clean()


class SedeFilteringTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.sede1 = Sede.objects.create(name="Sede 1", slug="sede1", status=True)
        self.sede2 = Sede.objects.create(name="Sede 2", slug="sede2", status=True)

        self.client_obj = Client.objects.create(
            first_name="Test",
            last_name="Client",
            email="client@example.com",
            sede=self.sede1,
        )

    def test_sede_list_endpoint(self):
        url = reverse("sede-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_sede_filtering_by_header(self):
        url = reverse("sede-list")
        response = self.client.get(url, HTTP_X_SEDES_SELECTED="1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sede_filtering_by_query_param(self):
        url = reverse("sede-list")
        response = self.client.get(url, {"sede_id": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BookingSedeTest(TestCase):
    def setUp(self):
        self.sede1 = Sede.objects.create(name="Sede 1", slug="sede1", status=True)
        self.sede2 = Sede.objects.create(name="Sede 2", slug="sede2", status=True)

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.client_obj = Client.objects.create(
            first_name="Test",
            last_name="Client",
            email="client@example.com",
            sede=self.sede1,
        )

        self.schedule = Schedule.objects.create(
            day="MON", time_slot="09:00", capacity=10, sede=self.sede1
        )

        self.membership = Membership.objects.create(
            name="Test Membership", price=Decimal("100.00"), scope="GLOBAL"
        )

    def test_booking_with_sede(self):
        booking = Booking.objects.create(
            client=self.client_obj,
            schedule=self.schedule,
            class_date="2024-01-01",
            sede=self.sede1,
        )
        self.assertEqual(booking.sede, self.sede1)

    def test_schedule_sede_relationship(self):
        self.assertEqual(self.schedule.sede, self.sede1)

    def test_client_sede_relationship(self):
        self.assertEqual(self.client_obj.sede, self.sede1)


class PaymentSedeTest(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(name="Sede Test", slug="test", status=True)

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.client_obj = Client.objects.create(
            first_name="Test",
            last_name="Client",
            email="client@example.com",
            sede=self.sede,
        )

        self.membership = Membership.objects.create(
            name="Test Membership", price=Decimal("100.00"), scope="GLOBAL"
        )

    def test_payment_with_sede(self):
        payment = Payment.objects.create(
            client=self.client_obj,
            membership=self.membership,
            amount=Decimal("100.00"),
            sede=self.sede,
        )
        self.assertEqual(payment.sede, self.sede)


class VentaSedeTest(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(name="Sede Test", slug="test", status=True)

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.client_obj = Client.objects.create(
            first_name="Test",
            last_name="Client",
            email="client@example.com",
            sede=self.sede,
        )

    def test_venta_with_sede(self):
        venta = Venta.objects.create(
            client=self.client_obj,
            product_name="Test Product",
            quantity=1,
            price_per_unit=Decimal("50.00"),
            date_sold="2024-01-01",
            sede=self.sede,
        )
        self.assertEqual(venta.sede, self.sede)


class SedeMiddlewareTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.sede = Sede.objects.create(name="Sede Test", slug="test", status=True)

    def test_sede_header_processing(self):
        url = reverse("sede-list")
        response = self.client.get(url, HTTP_X_SEDES_SELECTED="1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("X-Sedes-Selected", response)

    def test_sede_query_param_processing(self):
        url = reverse("sede-list")
        response = self.client.get(url, {"sede_id": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("X-Sedes-Selected", response)
