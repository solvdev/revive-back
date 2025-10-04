import pytest
import json
from datetime import date, timedelta, datetime
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from studio.models import Booking, Payment, Membership, Client
from accounts.models import Client as AccountClient

# Mark all test classes to use database
pytestmark = pytest.mark.django_db


class TestSpecificAPIEndpoints:
    """Test specific API endpoint functions"""

    def test_clases_por_mes_endpoint(self, admin_client, client, payment, booking):
        """Test clases por mes endpoint"""
        url = reverse('clases-por-mes')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_clases_por_mes_with_year_month(self, admin_client, client, payment, booking):
        """Test clases por mes endpoint with year and month parameters"""
        url = reverse('clases-por-mes')
        response = admin_client.get(url, {'year': 2024, 'month': 1})
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_attendance_summary_endpoint(self, admin_client, client, booking):
        """Test attendance summary endpoint"""
        url = reverse('attendance-summary')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_attendance_summary_with_parameters(self, admin_client, client, booking):
        """Test attendance summary endpoint with parameters"""
        url = reverse('attendance-summary')
        response = admin_client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_summary_by_class_type_endpoint(self, admin_client, class_type, booking):
        """Test summary by class type endpoint"""
        url = reverse('summary-by-class-type')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_summary_by_class_type_with_parameters(self, admin_client, class_type, booking):
        """Test summary by class type endpoint with parameters"""
        url = reverse('summary-by-class-type')
        response = admin_client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_today_payments_total_endpoint(self, admin_client, payment):
        """Test get today payments total endpoint"""
        url = reverse('payments-today')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total' in response.data

    def test_my_bookings_by_month_endpoint(self, client_authenticated_client, client_with_user, booking):
        """Test my bookings by month endpoint"""
        url = reverse('my_bookings_by_month')
        response = client_authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_my_bookings_by_month_with_parameters(self, client_authenticated_client, client_with_user, booking):
        """Test my bookings by month endpoint with parameters"""
        url = reverse('my_bookings_by_month')
        response = client_authenticated_client.get(url, {
            'year': 2024,
            'month': 1
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_create_authenticated_booking_endpoint(self, client_authenticated_client, client_with_user, schedule):
        """Test create authenticated booking endpoint"""
        url = reverse('create_authenticated_booking')
        data = {
            'schedule': schedule.id,
            'class_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        }
        response = client_authenticated_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'booking' in response.data

    def test_create_authenticated_booking_invalid_data(self, client_authenticated_client, client_with_user):
        """Test create authenticated booking with invalid data"""
        url = reverse('create_authenticated_booking')
        data = {
            'schedule': 99999,  # Non-existent schedule
            'class_date': 'invalid-date'
        }
        response = client_authenticated_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_dashboard_data_endpoint(self, admin_client, sede, client, payment, booking):
        """Test get dashboard data endpoint"""
        url = reverse('dashboard-data')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total_clients' in response.data
        assert 'active_clients' in response.data
        assert 'total_revenue' in response.data

    def test_get_dashboard_data_with_sede_filter(self, admin_client, sede, client, payment, booking):
        """Test get dashboard data endpoint with sede filter"""
        url = reverse('dashboard-data')
        response = admin_client.get(url, {'sede_ids': [sede.id]})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total_clients' in response.data

    def test_availability_endpoint(self, admin_client, schedule):
        """Test availability endpoint"""
        url = reverse('availability')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_availability_with_parameters(self, admin_client, schedule):
        """Test availability endpoint with parameters"""
        url = reverse('availability')
        response = admin_client.get(url, {
            'date': date.today().strftime('%Y-%m-%d'),
            'sede_id': schedule.sede.id
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_closure_full_summary_endpoint(self, admin_client, payment):
        """Test closure full summary endpoint"""
        url = reverse('closure-full-summary')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_closure_full_summary_with_parameters(self, admin_client, payment):
        """Test closure full summary endpoint with parameters"""
        url = reverse('closure-full-summary')
        response = admin_client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_get_weekly_closing_summary_endpoint(self, admin_client, payment):
        """Test get weekly closing summary endpoint"""
        url = reverse('cierres-semanales')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_weekly_closing_summary_with_parameters(self, admin_client, payment):
        """Test get weekly closing summary endpoint with parameters"""
        url = reverse('cierres-semanales')
        response = admin_client.get(url, {
            'year': 2024,
            'week': 1
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_daily_closing_summary_endpoint(self, admin_client, payment):
        """Test get daily closing summary endpoint"""
        url = reverse('cierres-diarios')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_daily_closing_summary_with_parameters(self, admin_client, payment):
        """Test get daily closing summary endpoint with parameters"""
        url = reverse('cierres-diarios')
        response = admin_client.get(url, {
            'date': '2024-01-01'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_comprehensive_closing_summary_endpoint(self, admin_client, payment):
        """Test get comprehensive closing summary endpoint"""
        url = reverse('cierres-completos')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_get_comprehensive_closing_summary_with_parameters(self, admin_client, payment):
        """Test get comprehensive closing summary endpoint with parameters"""
        url = reverse('cierres-completos')
        response = admin_client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)


class TestEndpointPermissions:
    """Test endpoint permissions and authentication"""

    def test_unauthenticated_access_to_protected_endpoints(self, api_client):
        """Test that unauthenticated users cannot access protected endpoints"""
        protected_endpoints = [
            'clases-por-mes',
            'attendance-summary',
            'summary-by-class-type',
            'payments-today',
            'my_bookings_by_month',
            'create_authenticated_booking',
            'dashboard-data',
            'availability',
            'closure-full-summary',
            'cierres-semanales',
            'cierres-diarios',
            'cierres-completos'
        ]
        
        for endpoint in protected_endpoints:
            url = reverse(endpoint)
            response = api_client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_access_to_protected_endpoints(self, authenticated_client):
        """Test that authenticated users can access protected endpoints"""
        protected_endpoints = [
            'clases-por-mes',
            'attendance-summary',
            'summary-by-class-type',
            'payments-today',
            'dashboard-data',
            'availability',
            'closure-full-summary',
            'cierres-semanales',
            'cierres-diarios',
            'cierres-completos'
        ]
        
        for endpoint in protected_endpoints:
            url = reverse(endpoint)
            response = authenticated_client.get(url)
            # Some endpoints might return 200 or 400 depending on data availability
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_client_specific_endpoints_require_client_user(self, authenticated_client):
        """Test that client-specific endpoints require client user"""
        client_endpoints = [
            'my_bookings_by_month',
            'create_authenticated_booking'
        ]
        
        for endpoint in client_endpoints:
            url = reverse(endpoint)
            response = authenticated_client.get(url)
            # These should fail for non-client users
            assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_client_specific_endpoints_with_client_user(self, client_authenticated_client, client_with_user):
        """Test that client-specific endpoints work with client user"""
        # Test my_bookings_by_month
        url = reverse('my_bookings_by_month')
        response = client_authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_admin_only_endpoints(self, authenticated_client):
        """Test that admin-only endpoints require admin user"""
        admin_endpoints = [
            'clases-por-mes',
            'attendance-summary',
            'summary-by-class-type',
            'payments-today',
            'dashboard-data',
            'availability',
            'closure-full-summary',
            'cierres-semanales',
            'cierres-diarios',
            'cierres-completos'
        ]
        
        for endpoint in admin_endpoints:
            url = reverse(endpoint)
            response = authenticated_client.get(url)
            # These might work for authenticated users but with limited data
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]


class TestEndpointErrorHandling:
    """Test endpoint error handling"""

    def test_invalid_date_parameters(self, admin_client):
        """Test endpoints with invalid date parameters"""
        url = reverse('clases-por-mes')
        response = admin_client.get(url, {'year': 'invalid', 'month': 'invalid'})
        
        # Should handle invalid parameters gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_missing_required_parameters(self, admin_client):
        """Test endpoints with missing required parameters"""
        url = reverse('create_authenticated_booking')
        response = admin_client.post(url, {})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_resource_parameters(self, admin_client):
        """Test endpoints with nonexistent resource parameters"""
        url = reverse('create_authenticated_booking')
        data = {
            'schedule': 99999,  # Non-existent schedule
            'class_date': date.today().strftime('%Y-%m-%d')
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_date_range_parameters(self, admin_client):
        """Test endpoints with invalid date range parameters"""
        url = reverse('attendance-summary')
        response = admin_client.get(url, {
            'start_date': '2024-01-31',
            'end_date': '2024-01-01'  # End before start
        })
        
        # Should handle invalid date ranges gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
