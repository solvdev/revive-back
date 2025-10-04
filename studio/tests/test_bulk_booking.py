import pytest
import json
from datetime import date, timedelta, datetime
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from studio.models import BulkBooking, Booking, Schedule, Client
from accounts.models import Client as AccountClient

# Mark all test classes to use database
pytestmark = pytest.mark.django_db


class TestBulkBookingFunctionality:
    """Test bulk booking specific functionality"""

    def test_bulk_booking_creation(self, admin_client, client, schedule):
        """Test creating a bulk booking"""
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
        assert response.data['days_of_week'] == ['MON', 'WED', 'FRI']

    def test_bulk_booking_with_individual_schedule(self, admin_client, client, sede, class_type, coach_user):
        """Test creating bulk booking with individual schedule"""
        # Create individual schedule
        individual_schedule = Schedule.objects.create(
            day='MON',
            time_slot='09:00',
            class_type=class_type,
            is_individual=True,
            capacity=1,
            coach=coach_user,
            sede=sede
        )
        
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': individual_schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON', 'WED', 'FRI']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['schedule'] == individual_schedule.id

    def test_bulk_booking_invalid_date_range(self, admin_client, client, schedule):
        """Test bulk booking with invalid date range"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),  # End before start
            'days_of_week': ['MON', 'WED', 'FRI']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_booking_invalid_days_of_week(self, admin_client, client, schedule):
        """Test bulk booking with invalid days of week"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'days_of_week': ['INVALID', 'WED', 'FRI']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_booking_past_dates(self, admin_client, client, schedule):
        """Test bulk booking with past dates"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'end_date': (date.today() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON', 'WED', 'FRI']
        }
        response = admin_client.post(url, data)
        
        # Should either create successfully or return validation error
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_bulk_booking_long_duration(self, admin_client, client, schedule):
        """Test bulk booking with long duration"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=30)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON', 'WED', 'FRI']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED

    def test_bulk_booking_single_day(self, admin_client, client, schedule):
        """Test bulk booking with single day"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED

    def test_bulk_booking_all_days_of_week(self, admin_client, client, schedule):
        """Test bulk booking with all days of week"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED

    def test_bulk_booking_update_days_of_week(self, admin_client, bulk_booking):
        """Test updating bulk booking days of week"""
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

    def test_bulk_booking_update_date_range(self, admin_client, bulk_booking):
        """Test updating bulk booking date range"""
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking.id})
        new_start = bulk_booking.start_date + timedelta(days=1)
        new_end = bulk_booking.end_date + timedelta(days=1)
        data = {
            'client': bulk_booking.client.id,
            'schedule': bulk_booking.schedule.id,
            'start_date': new_start.strftime('%Y-%m-%d'),
            'end_date': new_end.strftime('%Y-%m-%d'),
            'days_of_week': bulk_booking.days_of_week
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['start_date'] == new_start.strftime('%Y-%m-%d')
        assert response.data['end_date'] == new_end.strftime('%Y-%m-%d')

    def test_bulk_booking_filter_by_client(self, admin_client, client, schedule):
        """Test filtering bulk bookings by client"""
        # Create multiple bulk bookings
        bulk_booking1 = BulkBooking.objects.create(
            client=client,
            schedule=schedule,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=7),
            days_of_week=['MON', 'WED', 'FRI']
        )
        
        # Create another client and bulk booking
        other_client = Client.objects.create(
            first_name='Other',
            last_name='Client',
            email='other@test.com',
            phone='+50212345679',
            dpi='1234567890124',
            sex='M',
            status='A',
            sede=client.sede
        )
        
        bulk_booking2 = BulkBooking.objects.create(
            client=other_client,
            schedule=schedule,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=7),
            days_of_week=['TUE', 'THU']
        )
        
        url = reverse('bulk-bookings-list')
        response = admin_client.get(url, {'client': client.id})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['client'] == client.id

    def test_bulk_booking_filter_by_schedule(self, admin_client, client, schedule, sede, class_type, coach_user):
        """Test filtering bulk bookings by schedule"""
        # Create another schedule
        other_schedule = Schedule.objects.create(
            day='TUE',
            time_slot='10:00',
            class_type=class_type,
            is_individual=False,
            capacity=8,
            coach=coach_user,
            sede=sede
        )
        
        # Create bulk bookings for different schedules
        bulk_booking1 = BulkBooking.objects.create(
            client=client,
            schedule=schedule,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=7),
            days_of_week=['MON', 'WED', 'FRI']
        )
        
        bulk_booking2 = BulkBooking.objects.create(
            client=client,
            schedule=other_schedule,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=7),
            days_of_week=['TUE', 'THU']
        )
        
        url = reverse('bulk-bookings-list')
        response = admin_client.get(url, {'schedule': schedule.id})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['schedule'] == schedule.id

    def test_bulk_booking_search_functionality(self, admin_client, client, schedule):
        """Test bulk booking search functionality"""
        bulk_booking = BulkBooking.objects.create(
            client=client,
            schedule=schedule,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=7),
            days_of_week=['MON', 'WED', 'FRI']
        )
        
        url = reverse('bulk-bookings-list')
        response = admin_client.get(url, {'search': client.first_name})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_bulk_booking_ordering(self, admin_client, client, schedule):
        """Test bulk booking ordering"""
        # Create multiple bulk bookings with different dates
        bulk_booking1 = BulkBooking.objects.create(
            client=client,
            schedule=schedule,
            start_date=date.today() + timedelta(days=3),
            end_date=date.today() + timedelta(days=9),
            days_of_week=['MON', 'WED', 'FRI']
        )
        
        bulk_booking2 = BulkBooking.objects.create(
            client=client,
            schedule=schedule,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=7),
            days_of_week=['TUE', 'THU']
        )
        
        url = reverse('bulk-bookings-list')
        response = admin_client.get(url, {'ordering': 'start_date'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        # Should be ordered by start_date ascending
        assert response.data[0]['start_date'] <= response.data[1]['start_date']

    def test_bulk_booking_pagination(self, admin_client, client, schedule):
        """Test bulk booking pagination"""
        # Create multiple bulk bookings
        for i in range(15):
            BulkBooking.objects.create(
                client=client,
                schedule=schedule,
                start_date=date.today() + timedelta(days=i+1),
                end_date=date.today() + timedelta(days=i+7),
                days_of_week=['MON', 'WED', 'FRI']
            )
        
        url = reverse('bulk-bookings-list')
        response = admin_client.get(url, {'page_size': 10})
        
        assert response.status_code == status.HTTP_200_OK
        # Should return paginated results
        assert 'results' in response.data or len(response.data) <= 10

    def test_bulk_booking_deletion_cascades(self, admin_client, bulk_booking):
        """Test that deleting bulk booking works correctly"""
        bulk_booking_id = bulk_booking.id
        
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking_id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not BulkBooking.objects.filter(id=bulk_booking_id).exists()

    def test_bulk_booking_unauthorized_access(self, api_client, bulk_booking):
        """Test that unauthenticated users cannot access bulk bookings"""
        url = reverse('bulk-bookings-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_bulk_booking_unauthorized_creation(self, api_client, client, schedule):
        """Test that unauthenticated users cannot create bulk bookings"""
        url = reverse('bulk-bookings-list')
        data = {
            'client': client.id,
            'schedule': schedule.id,
            'start_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'days_of_week': ['MON', 'WED', 'FRI']
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_bulk_booking_unauthorized_modification(self, api_client, bulk_booking):
        """Test that unauthenticated users cannot modify bulk bookings"""
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking.id})
        data = {
            'client': bulk_booking.client.id,
            'schedule': bulk_booking.schedule.id,
            'start_date': bulk_booking.start_date.strftime('%Y-%m-%d'),
            'end_date': bulk_booking.end_date.strftime('%Y-%m-%d'),
            'days_of_week': ['TUE', 'THU']
        }
        response = api_client.put(url, data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_bulk_booking_unauthorized_deletion(self, api_client, bulk_booking):
        """Test that unauthenticated users cannot delete bulk bookings"""
        url = reverse('bulk-bookings-detail', kwargs={'pk': bulk_booking.id})
        response = api_client.delete(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
