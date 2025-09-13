from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    get_current_user, get_my_client, get_my_profile, get_auth_session,
    register_user, request_password_reset, confirm_password_reset,
    generate_user_for_client, set_password_for_generated_user
)
from .views import CustomUserViewSet, ClientViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Vista personalizada para login que permite usar email o username
    """
    serializer_class = CustomTokenObtainPairSerializer

def test_login_debug(request):
    """
    Endpoint de debug para probar el login
    """
    from .models import CustomUser
    from django.db.models import Q
    
    login = request.GET.get('login', '')
    if not login:
        return Response({'error': 'Provide login parameter'}, status=400)
    
    try:
        user = CustomUser.objects.get(Q(username=login) | Q(email__iexact=login))
        return Response({
            'found': True,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_enabled': user.is_enabled
        })
    except CustomUser.DoesNotExist:
        return Response({'found': False, 'message': 'User not found'})

def test_serializer(request):
    """
    Endpoint para probar el serializer directamente
    """
    from .serializers import CustomTokenObtainPairSerializer
    import json
    
    if request.method != 'POST':
        return Response({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        serializer = CustomTokenObtainPairSerializer(data=data)
        
        if serializer.is_valid():
            return Response({
                'success': True,
                'message': 'Serializer validation passed',
                'data': serializer.validated_data
            })
        else:
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=400)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

router = DefaultRouter()
router.register(r'users', CustomUserViewSet, basename='users')
router.register(r'clients', ClientViewSet, basename='clients')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', get_current_user, name='get_current_user'),
    path('me/client/', get_my_client, name='get_my_client'),
    path('me/profile/', get_my_profile, name='get_my_profile'),
    path('auth/session/', get_auth_session, name='get_auth_session'),
    
    # New endpoints for registration and password reset
    path('register/', register_user, name='register_user'),
    path('password-reset/', request_password_reset, name='request_password_reset'),
    path('password-reset/confirm/', confirm_password_reset, name='confirm_password_reset'),
    
    # Migration endpoints for existing clients
    path('generate-user-for-client/', generate_user_for_client, name='generate_user_for_client'),
    path('set-password-for-generated-user/', set_password_for_generated_user, name='set_password_for_generated_user'),
    
    # Debug endpoints
    path('debug/login/', test_login_debug, name='test_login_debug'),
    path('debug/serializer/', test_serializer, name='test_serializer'),
]
