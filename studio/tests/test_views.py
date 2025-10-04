import pytest
import json
from datetime import date, timedelta, datetime
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from studio.models import (
    Sede, ClassType, Schedule, Membership, Payment, Booking, 
    PlanIntent, Promotion, PromotionInstance, Venta, MonthlyRevenue, 
    BulkBooking
)
from accounts.models import Client

User = get_user_model()

# Mark all test classes to use database
pytestmark = pytest.mark.django_db


class TestScheduleEndpoints:
    """Test schedule-related endpoints"""

    def test_schedule_list_authenticated(self, admin_client, schedule):
        """Test listing schedules as admin"""
        url = reverse('schedule-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_schedule_create_authenticated(self, admin_client, sede, class_type, coach_user):
        """Test creating schedule as admin"""
        url = reverse('schedule-list')
        data = {
            'day': 'TUE',
            'time_slot': '10:00',
            'class_type': class_type.id,
            'is_individual': False,
            'capacity': 8,
            'coach': coach_user.id,
            'sede': sede.id
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['day'] == 'TUE'
        assert response.data['time_slot'] == '10:00'

    def test_schedule_retrieve_authenticated(self, admin_client, schedule):
        """Test retrieving specific schedule as admin"""
        url = reverse('schedule-detail', kwargs={'pk': schedule.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['day'] == schedule.day

    def test_schedule_update_authenticated(self, admin_client, schedule):
        """Test updating schedule as admin"""
        url = reverse('schedule-detail', kwargs={'pk': schedule.id})
        data = {
            'day': schedule.day,
            'time_slot': '10:00',
            'class_type': schedule.class_type.id if schedule.class_type else None,
            'is_individual': True,
            'capacity': 1,
            'coach': schedule.coach.id if schedule.coach else None,
            'sede': schedule.sede.id if schedule.sede else None
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_individual'] is True

    def test_schedule_delete_authenticated(self, admin_client, schedule):
        """Test deleting schedule as admin"""
        url = reverse('schedule-detail', kwargs={'pk': schedule.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Schedule.objects.filter(id=schedule.id).exists()

    def test_schedule_list_unauthenticated(self, api_client):
        """Test listing schedules without authentication"""
        url = reverse('schedule-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestBookingEndpoints:
    """Test booking-related endpoints"""

    def test_booking_list_authenticated(self, admin_client, booking):
        """Test listing bookings as admin"""
        url = reverse('bookings-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_booking_create_authenticated(self, admin_client, client, schedule):
        """Test creating booking as admin"""
        url = reverse('bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'class_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'attendance_status': 'pending'
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['client'] == client.id
        assert response.data['schedule'] == schedule.id

    def test_booking_retrieve_authenticated(self, admin_client, booking):
        """Test retrieving specific booking as admin"""
        url = reverse('bookings-detail', kwargs={'pk': booking.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['client'] == booking.client.id

    def test_booking_update_attendance(self, admin_client, booking):
        """Test updating booking attendance status"""
        url = reverse('bookings-detail', kwargs={'pk': booking.id})
        data = {
            'attendance_status': 'attended',
            'cancellation_reason': ''
        }
        response = admin_client.patch(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['attendance_status'] == 'attended'

    def test_booking_delete_authenticated(self, admin_client, booking):
        """Test deleting booking as admin"""
        url = reverse('bookings-detail', kwargs={'pk': booking.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Booking.objects.filter(id=booking.id).exists()

    def test_booking_list_unauthenticated(self, api_client):
        """Test listing bookings without authentication"""
        url = reverse('bookings-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMembershipEndpoints:
    """Test membership-related endpoints"""

    def test_membership_list_authenticated(self, admin_client, membership):
        """Test listing memberships as admin"""
        url = reverse('memberships-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_membership_create_authenticated(self, admin_client, sede):
        """Test creating membership as admin"""
        url = reverse('memberships-list')
        data = {
            'name': 'Weekly Pass',
            'description': '4 classes per week',
            'price': 75.00,
            'classes_per_month': 16,
            'duration_days': 7,
            'is_active': True,
            'sede': sede.id
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Weekly Pass'
        assert response.data['price'] == '75.00'

    def test_membership_retrieve_authenticated(self, admin_client, membership):
        """Test retrieving specific membership as admin"""
        url = reverse('memberships-detail', kwargs={'pk': membership.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == membership.name

    def test_membership_update_authenticated(self, admin_client, membership):
        """Test updating membership as admin"""
        url = reverse('memberships-detail', kwargs={'pk': membership.id})
        data = {
            'name': 'Updated Monthly',
            'description': membership.description,
            'price': 175.00,
            'classes_per_month': membership.classes_per_month,
            'duration_days': membership.duration_days,
            'is_active': membership.is_active,
            'sede': membership.sede.id if membership.sede else None
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Monthly'

    def test_membership_delete_authenticated(self, admin_client, membership):
        """Test deleting membership as admin"""
        url = reverse('memberships-detail', kwargs={'pk': membership.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Membership.objects.filter(id=membership.id).exists()


class TestPaymentEndpoints:
    """Test payment-related endpoints"""

    def test_payment_list_authenticated(self, admin_client, payment):
        """Test listing payments as admin"""
        url = reverse('payments-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_payment_create_authenticated(self, admin_client, client, membership):
        """Test creating payment as admin"""
        url = reverse('payments-list')
        data = {
            'client': client.id,
            'membership': membership.id,
            'amount': 200.00,
            'date_paid': date.today().strftime('%Y-%m-%d'),
            'valid_until': (date.today() + timedelta(days=30)).strftime('%Y-%m-%d'),
            'payment_method': 'card'
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['client'] == client.id
        assert response.data['amount'] == '200.00'

    def test_payment_retrieve_authenticated(self, admin_client, payment):
        """Test retrieving specific payment as admin"""
        url = reverse('payments-detail', kwargs={'pk': payment.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['client'] == payment.client.id

    def test_payment_update_authenticated(self, admin_client, payment):
        """Test updating payment as admin"""
        url = reverse('payments-detail', kwargs={'pk': payment.id})
        data = {
            'client': payment.client.id,
            'membership': payment.membership.id,
            'amount': 180.00,
            'date_paid': payment.date_paid.strftime('%Y-%m-%d'),
            'valid_until': payment.valid_until.strftime('%Y-%m-%d'),
            'payment_method': 'transfer'
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['amount'] == '180.00'

    def test_payment_delete_authenticated(self, admin_client, payment):
        """Test deleting payment as admin"""
        url = reverse('payments-detail', kwargs={'pk': payment.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Payment.objects.filter(id=payment.id).exists()


class TestSedeEndpoints:
    """Test sede-related endpoints"""

    def test_sede_list_authenticated(self, admin_client, sede):
        """Test listing sedes as admin"""
        url = reverse('sedes-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_sede_create_authenticated(self, admin_client):
        """Test creating sede as admin"""
        url = reverse('sedes-list')
        data = {
            'name': 'New Sede',
            'slug': 'new-sede',
            'status': True
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Sede'
        assert response.data['slug'] == 'new-sede'

    def test_sede_retrieve_authenticated(self, admin_client, sede):
        """Test retrieving specific sede as admin"""
        url = reverse('sedes-detail', kwargs={'pk': sede.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == sede.name

    def test_sede_update_authenticated(self, admin_client, sede):
        """Test updating sede as admin"""
        url = reverse('sedes-detail', kwargs={'pk': sede.id})
        data = {
            'name': 'Updated Sede',
            'slug': sede.slug,
            'status': sede.status
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Sede'

    def test_sede_delete_authenticated(self, admin_client, sede):
        """Test deleting sede as admin"""
        url = reverse('sedes-detail', kwargs={'pk': sede.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Sede.objects.filter(id=sede.id).exists()


class TestClassTypeEndpoints:
    """Test class type-related endpoints"""

    def test_class_type_list_authenticated(self, admin_client, class_type):
        """Test listing class types as admin"""
        url = reverse('class-types-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_class_type_create_authenticated(self, admin_client):
        """Test creating class type as admin"""
        url = reverse('class-types-list')
        data = {
            'name': 'Pilates Reformer',
            'description': 'Pilates using reformer equipment'
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Pilates Reformer'

    def test_class_type_retrieve_authenticated(self, admin_client, class_type):
        """Test retrieving specific class type as admin"""
        url = reverse('class-types-detail', kwargs={'pk': class_type.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == class_type.name

    def test_class_type_update_authenticated(self, admin_client, class_type):
        """Test updating class type as admin"""
        url = reverse('class-types-detail', kwargs={'pk': class_type.id})
        data = {
            'name': 'Updated Pilates Mat',
            'description': class_type.description
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Pilates Mat'

    def test_class_type_delete_authenticated(self, admin_client, class_type):
        """Test deleting class type as admin"""
        url = reverse('class-types-detail', kwargs={'pk': class_type.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ClassType.objects.filter(id=class_type.id).exists()


class TestPlanIntentEndpoints:
    """Test plan intent-related endpoints"""

    def test_plan_intent_list_authenticated(self, admin_client, plan_intent):
        """Test listing plan intents as admin"""
        url = reverse('planintents-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_plan_intent_create_authenticated(self, admin_client, client, membership):
        """Test creating plan intent as admin"""
        url = reverse('planintents-list')
        data = {
            'client': client.id,
            'membership': membership.id,
            'is_confirmed': False
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['client'] == client.id
        assert response.data['membership'] == membership.id

    def test_plan_intent_retrieve_authenticated(self, admin_client, plan_intent):
        """Test retrieving specific plan intent as admin"""
        url = reverse('planintents-detail', kwargs={'pk': plan_intent.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['client'] == plan_intent.client.id

    def test_plan_intent_update_authenticated(self, admin_client, plan_intent):
        """Test updating plan intent as admin"""
        url = reverse('planintents-detail', kwargs={'pk': plan_intent.id})
        data = {
            'client': plan_intent.client.id,
            'membership': plan_intent.membership.id,
            'is_confirmed': True
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_confirmed'] is True

    def test_plan_intent_delete_authenticated(self, admin_client, plan_intent):
        """Test deleting plan intent as admin"""
        url = reverse('planintents-detail', kwargs={'pk': plan_intent.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not PlanIntent.objects.filter(id=plan_intent.id).exists()


class TestPromotionEndpoints:
    """Test promotion-related endpoints"""

    def test_promotion_list_authenticated(self, admin_client, promotion):
        """Test listing promotions as admin"""
        url = reverse('promotions-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_promotion_create_authenticated(self, admin_client, sede):
        """Test creating promotion as admin"""
        url = reverse('promotions-list')
        data = {
            'name': 'Summer Special',
            'description': '30% off summer classes',
            'discount_percentage': 30.0,
            'is_active': True,
            'sede': sede.id
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Summer Special'
        assert response.data['discount_percentage'] == 30.0

    def test_promotion_retrieve_authenticated(self, admin_client, promotion):
        """Test retrieving specific promotion as admin"""
        url = reverse('promotions-detail', kwargs={'pk': promotion.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == promotion.name

    def test_promotion_update_authenticated(self, admin_client, promotion):
        """Test updating promotion as admin"""
        url = reverse('promotions-detail', kwargs={'pk': promotion.id})
        data = {
            'name': 'Updated New Year Special',
            'description': promotion.description,
            'discount_percentage': promotion.discount_percentage,
            'is_active': promotion.is_active,
            'sede': promotion.sede.id if promotion.sede else None
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated New Year Special'

    def test_promotion_delete_authenticated(self, admin_client, promotion):
        """Test deleting promotion as admin"""
        url = reverse('promotions-detail', kwargs={'pk': promotion.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Promotion.objects.filter(id=promotion.id).exists()


class TestPromotionInstanceEndpoints:
    """Test promotion instance-related endpoints"""

    def test_promotion_instance_list_authenticated(self, admin_client, promotion_instance):
        """Test listing promotion instances as admin"""
        url = reverse('promotion-instances-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_promotion_instance_create_authenticated(self, admin_client, promotion, client):
        """Test creating promotion instance as admin"""
        url = reverse('promotion-instances-list')
        data = {
            'promotion': promotion.id,
            'client': client.id,
            'is_used': False
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['promotion'] == promotion.id
        assert response.data['client'] == client.id

    def test_promotion_instance_retrieve_authenticated(self, admin_client, promotion_instance):
        """Test retrieving specific promotion instance as admin"""
        url = reverse('promotion-instances-detail', kwargs={'pk': promotion_instance.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['promotion'] == promotion_instance.promotion.id

    def test_promotion_instance_update_authenticated(self, admin_client, promotion_instance):
        """Test updating promotion instance as admin"""
        url = reverse('promotion-instances-detail', kwargs={'pk': promotion_instance.id})
        data = {
            'promotion': promotion_instance.promotion.id,
            'client': promotion_instance.client.id,
            'is_used': True
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_used'] is True

    def test_promotion_instance_delete_authenticated(self, admin_client, promotion_instance):
        """Test deleting promotion instance as admin"""
        url = reverse('promotion-instances-detail', kwargs={'pk': promotion_instance.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not PromotionInstance.objects.filter(id=promotion_instance.id).exists()


class TestVentaEndpoints:
    """Test venta-related endpoints"""

    def test_venta_list_authenticated(self, admin_client, venta):
        """Test listing ventas as admin"""
        url = reverse('ventas-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_venta_create_authenticated(self, admin_client, client, membership):
        """Test creating venta as admin"""
        url = reverse('ventas-list')
        data = {
            'client': client.id,
            'membership': membership.id,
            'amount': 300.00,
            'payment_method': 'card'
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['client'] == client.id
        assert response.data['amount'] == '300.00'

    def test_venta_retrieve_authenticated(self, admin_client, venta):
        """Test retrieving specific venta as admin"""
        url = reverse('ventas-detail', kwargs={'pk': venta.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['client'] == venta.client.id

    def test_venta_update_authenticated(self, admin_client, venta):
        """Test updating venta as admin"""
        url = reverse('ventas-detail', kwargs={'pk': venta.id})
        data = {
            'client': venta.client.id,
            'membership': venta.membership.id,
            'amount': 250.00,
            'payment_method': 'transfer'
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['amount'] == '250.00'

    def test_venta_delete_authenticated(self, admin_client, venta):
        """Test deleting venta as admin"""
        url = reverse('ventas-detail', kwargs={'pk': venta.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Venta.objects.filter(id=venta.id).exists()


class TestMonthlyRevenueEndpoints:
    """Test monthly revenue-related endpoints"""

    def test_monthly_revenue_list_authenticated(self, admin_client, monthly_revenue):
        """Test listing monthly revenues as admin"""
        url = reverse('monthly-revenue-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_monthly_revenue_create_authenticated(self, admin_client, sede):
        """Test creating monthly revenue as admin"""
        url = reverse('monthly-revenue-list')
        data = {
            'sede': sede.id,
            'year': 2024,
            'month': 2,
            'total_revenue': 2000.00
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['sede'] == sede.id
        assert response.data['total_revenue'] == '2000.00'

    def test_monthly_revenue_retrieve_authenticated(self, admin_client, monthly_revenue):
        """Test retrieving specific monthly revenue as admin"""
        url = reverse('monthly-revenue-detail', kwargs={'pk': monthly_revenue.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['sede'] == monthly_revenue.sede.id

    def test_monthly_revenue_update_authenticated(self, admin_client, monthly_revenue):
        """Test updating monthly revenue as admin"""
        url = reverse('monthly-revenue-detail', kwargs={'pk': monthly_revenue.id})
        data = {
            'sede': monthly_revenue.sede.id,
            'year': monthly_revenue.year,
            'month': monthly_revenue.month,
            'total_revenue': 1800.00
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_revenue'] == '1800.00'

    def test_monthly_revenue_delete_authenticated(self, admin_client, monthly_revenue):
        """Test deleting monthly revenue as admin"""
        url = reverse('monthly-revenue-detail', kwargs={'pk': monthly_revenue.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not MonthlyRevenue.objects.filter(id=monthly_revenue.id).exists()


class TestBulkBookingEndpoints:
    """Test bulk booking-related endpoints"""

    def test_bulk_booking_list_authenticated(self, admin_client, bulk_booking):
        """Test listing bulk bookings as admin"""
        url = reverse('bulk-bookings-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_bulk_booking_create_authenticated(self, admin_client, client, schedule):
        """Test creating bulk booking as admin"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON', 'WED', 'FRI']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['client'] == client.id
        assert response.data['schedule'] == schedule.id

    def test_bulk_booking_retrieve_authenticated(self, admin_client, bulk_booking):
        """Test retrieving specific bulk booking as admin"""
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['client'] == bulk_booking.client.id

    def test_bulk_booking_update_authenticated(self, admin_client, bulk_booking):
        """Test updating bulk booking as admin"""
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking.id})
        data = {
            'client': bulk_booking.client.id,
            'schedule': bulk_booking.schedule.id,
            'start_date': bulk_booking.start_date.strftime('%Y-%m-%d'),
            'end_date': bulk_booking.end_date.strftime('%Y-%m-%d'),
            'days_of_week': ['TUE', 'THU', 'SAT']
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['days_of_week'] == ['TUE', 'THU', 'SAT']

    def test_bulk_booking_delete_authenticated(self, admin_client, bulk_booking):
        """Test deleting bulk booking as admin"""
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not BulkBooking.objects.filter(id=bulk_booking.id).exists()
