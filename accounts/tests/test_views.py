import pytest
import json
from datetime import timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Client, PasswordResetToken

User = get_user_model()

# Mark all test classes to use database
pytestmark = pytest.mark.django_db


class TestAuthenticationEndpoints:
    """Test authentication related endpoints"""

    def test_login_success(self, api_client, regular_user):
        """Test successful login with username"""
        url = reverse('token_obtain_pair')
        data = {
            'username': regular_user.username,
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_with_email(self, api_client, regular_user):
        """Test successful login with email"""
        url = reverse('token_obtain_pair')
        data = {
            'username': regular_user.email,
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials"""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'nonexistent',
            'password': 'wrongpassword'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, regular_user):
        """Test token refresh"""
        # First get tokens
        url = reverse('token_obtain_pair')
        data = {
            'username': regular_user.username,
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        refresh_token = response.data['refresh']
        
        # Now refresh
        url = reverse('token_refresh')
        data = {'refresh': refresh_token}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_token_refresh_invalid(self, api_client):
        """Test token refresh with invalid token"""
        url = reverse('token_refresh')
        data = {'refresh': 'invalid_token'}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserRegistration:
    """Test user registration endpoints"""

    def test_register_user_success(self, api_client, sede):
        """Test successful user registration"""
        url = reverse('register_user')
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'testpass123',
            'first_name': 'New',
            'last_name': 'User',
            'client_data': {
                'first_name': 'New',
                'last_name': 'User',
                'email': 'newuser@test.com',
                'phone': '+50212345678',
                'dpi': '1234567890123',
                'sex': 'F',
                'sede': sede.id
            }
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'message' in response.data
        assert 'user' in response.data
        
        # Check user was created
        user = User.objects.get(username='newuser')
        assert user.email == 'newuser@test.com'
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        
        # Check client was created
        client = Client.objects.get(user=user)
        assert client.first_name == 'New'
        assert client.last_name == 'User'
        assert client.sede == sede

    def test_register_user_duplicate_email(self, api_client, regular_user, sede):
        """Test registration with duplicate email"""
        url = reverse('register_user')
        data = {
            'username': 'anotheruser',
            'email': regular_user.email,  # Duplicate email
            'password': 'testpass123',
            'first_name': 'Another',
            'last_name': 'User',
            'client_data': {
                'first_name': 'Another',
                'last_name': 'User',
                'email': regular_user.email,
                'phone': '+50212345678',
                'dpi': '1234567890124',
                'sex': 'M',
                'sede': sede.id
            }
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_user_invalid_data(self, api_client):
        """Test registration with invalid data"""
        url = reverse('register_user')
        data = {
            'username': 'newuser',
            'email': 'invalid-email',
            'password': '123',  # Too short
            'first_name': 'New',
            'last_name': 'User'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPasswordReset:
    """Test password reset endpoints"""

    def test_request_password_reset_success(self, api_client, regular_user):
        """Test successful password reset request"""
        url = reverse('request_password_reset')
        data = {'email': regular_user.email}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        
        # Check token was created
        token = PasswordResetToken.objects.get(user=regular_user)
        assert not token.is_used
        assert not token.is_expired()

    def test_request_password_reset_invalid_email(self, api_client):
        """Test password reset request with invalid email"""
        url = reverse('request_password_reset')
        data = {'email': 'nonexistent@test.com'}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_password_reset_success(self, api_client, password_reset_token):
        """Test successful password reset confirmation"""
        url = reverse('confirm_password_reset')
        data = {
            'reset_token': str(password_reset_token.token),
            'new_password': 'newpass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        
        # Check token was marked as used
        password_reset_token.refresh_from_db()
        assert password_reset_token.is_used

    def test_confirm_password_reset_invalid_token(self, api_client):
        """Test password reset confirmation with invalid token"""
        url = reverse('confirm_password_reset')
        data = {
            'reset_token': 'invalid-token',
            'new_password': 'newpass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_password_reset_expired_token(self, api_client, regular_user):
        """Test password reset confirmation with expired token"""
        # Create expired token
        token = PasswordResetToken.objects.create(
            user=regular_user,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        url = reverse('confirm_password_reset')
        data = {
            'reset_token': str(token.token),
            'new_password': 'newpass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUserEndpoints:
    """Test user-related endpoints"""

    def test_get_current_user_authenticated(self, authenticated_client, regular_user):
        """Test getting current user when authenticated"""
        url = reverse('get_current_user')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == regular_user.username
        assert response.data['email'] == regular_user.email

    def test_get_current_user_unauthenticated(self, api_client):
        """Test getting current user when not authenticated"""
        url = reverse('get_current_user')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_my_client_authenticated(self, client_authenticated_client, client_with_user):
        """Test getting current user's client when authenticated"""
        url = reverse('get_my_client')
        response = client_authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == client_with_user.first_name
        assert response.data['last_name'] == client_with_user.last_name

    def test_get_my_client_no_client(self, authenticated_client):
        """Test getting client when user has no client"""
        url = reverse('get_my_client')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_my_profile_authenticated(self, client_authenticated_client, client_with_user):
        """Test getting combined profile when authenticated"""
        url = reverse('get_my_profile')
        response = client_authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'user' in response.data
        assert 'client' in response.data

    def test_get_auth_session_authenticated(self, authenticated_client, regular_user, sede):
        """Test getting auth session when authenticated"""
        url = reverse('get_auth_session')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'user' in response.data
        assert 'available_sedes' in response.data
        assert 'client_sede' in response.data


class TestClientEndpoints:
    """Test client-related endpoints"""

    def test_client_list_authenticated(self, admin_client, client):
        """Test listing clients as admin"""
        url = reverse('clients-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['first_name'] == client.first_name

    def test_client_list_unauthenticated(self, api_client):
        """Test listing clients without authentication"""
        url = reverse('clients-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK  # AllowAny permission

    def test_client_create_authenticated(self, admin_client, sede):
        """Test creating client as admin"""
        url = reverse('clients-list')
        data = {
            'first_name': 'New',
            'last_name': 'Client',
            'email': 'newclient@test.com',
            'phone': '+50212345678',
            'dpi': '1234567890125',
            'sex': 'M',
            'status': 'A',
            'sede': sede.id
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['first_name'] == 'New'
        assert response.data['last_name'] == 'Client'

    def test_client_retrieve_authenticated(self, admin_client, client):
        """Test retrieving specific client as admin"""
        url = reverse('clients-detail', kwargs={'pk': client.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == client.first_name

    def test_client_update_authenticated(self, admin_client, client):
        """Test updating client as admin"""
        url = reverse('clients-detail', kwargs={'pk': client.id})
        data = {
            'first_name': 'Updated',
            'last_name': 'Client',
            'email': client.email,
            'phone': client.phone,
            'dpi': client.dpi,
            'sex': client.sex,
            'status': 'A',
            'sede': client.sede.id if client.sede else None
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'Updated'

    def test_client_delete_authenticated(self, admin_client, client):
        """Test deleting client as admin"""
        url = reverse('clients-detail', kwargs={'pk': client.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Client.objects.filter(id=client.id).exists()

    def test_client_simple_list(self, admin_client, client):
        """Test client simple list endpoint"""
        url = reverse('clients-simple-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert 'id' in response.data[0]
        assert 'first_name' in response.data[0]
        assert 'last_name' in response.data[0]

    def test_client_minimal_list(self, admin_client, client):
        """Test client minimal list endpoint"""
        url = reverse('clients-minimal-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert 'id' in response.data[0]
        assert 'name' in response.data[0]

    def test_client_dashboard(self, admin_client, client, payment, booking):
        """Test client dashboard endpoint"""
        url = reverse('clients-dashboard', kwargs={'pk': client.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'client' in response.data
        assert 'current_membership' in response.data
        assert 'statistics' in response.data
        assert 'recent_bookings' in response.data
        assert 'payment_history' in response.data

    def test_client_clases_por_mes(self, admin_client, client):
        """Test client clases por mes endpoint"""
        url = reverse('clients-clases-por-mes', kwargs={'pk': client.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'client_id' in response.data
        assert 'client_name' in response.data
        assert 'membership' in response.data
        assert 'expected_classes' in response.data

    def test_client_estado(self, admin_client, client):
        """Test client estado endpoint"""
        url = reverse('clients-estado', kwargs={'pk': client.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'estado' in response.data
        assert 'puede_agendar' in response.data
        assert 'trial_used' in response.data

    def test_client_por_dpi(self, admin_client, client):
        """Test client por DPI endpoint"""
        url = reverse('clients-client-por-dpi')
        response = admin_client.get(url, {'dpi': client.dpi})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'client' in response.data
        assert 'estado' in response.data

    def test_client_por_dpi_not_found(self, admin_client):
        """Test client por DPI with non-existent DPI"""
        url = reverse('clients-client-por-dpi')
        response = admin_client.get(url, {'dpi': '9999999999999'})
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_client_count(self, admin_client, client):
        """Test client count endpoint"""
        url = reverse('clients-count')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total' in response.data
        assert 'active' in response.data
        assert 'inactive' in response.data
        assert 'new_this_month' in response.data


class TestUserViewSet:
    """Test UserViewSet endpoints"""

    def test_user_list_admin_only(self, admin_client, regular_user):
        """Test listing users as admin"""
        url = reverse('users-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_user_list_non_admin(self, authenticated_client):
        """Test listing users as non-admin"""
        url = reverse('users-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_create_admin(self, admin_client, sede):
        """Test creating user as admin"""
        url = reverse('users-list')
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'testpass123',
            'first_name': 'New',
            'last_name': 'User',
            'is_active': True,
            'is_enabled': True,
            'sede': sede.id
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == 'newuser'

    def test_user_retrieve_admin(self, admin_client, regular_user):
        """Test retrieving user as admin"""
        url = reverse('users-detail', kwargs={'pk': regular_user.id})
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == regular_user.username

    def test_user_update_admin(self, admin_client, regular_user):
        """Test updating user as admin"""
        url = reverse('users-detail', kwargs={'pk': regular_user.id})
        data = {
            'username': regular_user.username,
            'email': regular_user.email,
            'first_name': 'Updated',
            'last_name': 'User',
            'is_active': True,
            'is_enabled': True
        }
        response = admin_client.put(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'Updated'

    def test_user_delete_admin(self, admin_client, regular_user):
        """Test deleting user as admin"""
        url = reverse('users-detail', kwargs={'pk': regular_user.id})
        response = admin_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(id=regular_user.id).exists()

    def test_user_list_coaches(self, admin_client, coach_user):
        """Test listing coaches"""
        url = reverse('users-list-coaches')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['username'] == coach_user.username


class TestMigrationEndpoints:
    """Test migration-related endpoints"""

    def test_generate_user_for_client_success(self, api_client, client):
        """Test generating user for existing client"""
        url = reverse('generate_user_for_client')
        data = {'email': client.email}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'message' in response.data
        assert 'user' in response.data
        
        # Check user was created and linked
        client.refresh_from_db()
        assert client.user is not None
        assert client.user.email == client.email

    def test_generate_user_for_client_not_found(self, api_client):
        """Test generating user for non-existent client"""
        url = reverse('generate_user_for_client')
        data = {'email': 'nonexistent@test.com'}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_generate_user_for_client_already_has_user(self, api_client, client_with_user):
        """Test generating user for client that already has user"""
        url = reverse('generate_user_for_client')
        data = {'email': client_with_user.email}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_set_password_for_generated_user_success(self, api_client, client_with_user):
        """Test setting password for generated user"""
        url = reverse('set_password_for_generated_user')
        data = {
            'email': client_with_user.user.email,
            'new_password': 'NewPass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data

    def test_set_password_for_generated_user_invalid_password(self, api_client, client_with_user):
        """Test setting invalid password for generated user"""
        url = reverse('set_password_for_generated_user')
        data = {
            'email': client_with_user.user.email,
            'new_password': '123'  # Too short
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_set_password_for_generated_user_not_found(self, api_client):
        """Test setting password for non-existent user"""
        url = reverse('set_password_for_generated_user')
        data = {
            'email': 'nonexistent@test.com',
            'new_password': 'NewPass123'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDebugEndpoints:
    """Test debug endpoints"""

    def test_debug_login_found(self, api_client, regular_user):
        """Test debug login endpoint with existing user"""
        url = reverse('test_login_debug')
        response = api_client.get(url, {'login': regular_user.username})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['found'] is True
        assert response.data['username'] == regular_user.username

    def test_debug_login_not_found(self, api_client):
        """Test debug login endpoint with non-existent user"""
        url = reverse('test_login_debug')
        response = api_client.get(url, {'login': 'nonexistent'})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['found'] is False

    def test_debug_login_no_parameter(self, api_client):
        """Test debug login endpoint without parameter"""
        url = reverse('test_login_debug')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_debug_serializer_valid(self, api_client, regular_user):
        """Test debug serializer endpoint with valid data"""
        url = reverse('test_serializer')
        data = {
            'username': regular_user.username,
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

    def test_debug_serializer_invalid(self, api_client):
        """Test debug serializer endpoint with invalid data"""
        url = reverse('test_serializer')
        data = {
            'username': 'nonexistent',
            'password': 'wrong'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is False

    def test_debug_serializer_wrong_method(self, api_client):
        """Test debug serializer endpoint with wrong method"""
        url = reverse('test_serializer')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
