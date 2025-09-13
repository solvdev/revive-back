"""
Environment configuration for Revive Pilates Studio
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables with defaults
def get_env_var(key, default=None):
    """Get environment variable with fallback to default"""
    return os.environ.get(key, default)

# Frontend URLs
FRONTEND_URL = get_env_var('FRONTEND_URL', 'https://booking-testing.revivepilates.com')  # Same as booking URL
FRONTEND_BOOKING_URL = get_env_var('FRONTEND_BOOKING_URL', 'https://booking-testing.revivepilates.com')

# Database configuration
DATABASE_CONFIG = {
    'ENGINE': get_env_var('DB_ENGINE', 'django.db.backends.postgresql'),
    'NAME': get_env_var('DB_NAME', 'revive'),
    'USER': get_env_var('DB_USER', 'reviveadmin'),
    'PASSWORD': get_env_var('DB_PASSWORD', 'revive2025!'),
    'HOST': get_env_var('DB_HOST', 'revive-db.c7okeymccfwd.us-east-2.rds.amazonaws.com'),
    'PORT': get_env_var('DB_PORT', '5432'),
}

# Email configuration
EMAIL_CONFIG = {
    'BACKEND': get_env_var('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'),
    'HOST': get_env_var('EMAIL_HOST', 'in-v3.mailjet.com'),
    'PORT': int(get_env_var('EMAIL_PORT', '587')),
    'USE_TLS': get_env_var('EMAIL_USE_TLS', 'True').lower() == 'true',
    'HOST_USER': get_env_var('EMAIL_HOST_USER', 'c15bdbc4c6cbd885363c6dbd7e0db70d'),
    'HOST_PASSWORD': get_env_var('EMAIL_HOST_PASSWORD', '1484577f04215c3451f7ca851d7be3ba'),
    'FROM_EMAIL': get_env_var('DEFAULT_FROM_EMAIL', 'no-reply@revivepilates.com'),
}

# Security configuration
SECURITY_CONFIG = {
    'SECRET_KEY': get_env_var('SECRET_KEY', 'django-insecure-revive-pilates-secret-key-2025'),
    'DEBUG': get_env_var('DEBUG', 'True').lower() == 'true',
    'ALLOWED_HOSTS': get_env_var('ALLOWED_HOSTS', 'config-testing.revivepilates.com,booking-testing.revivepilates.com,localhost,127.0.0.1').split(','),
}

# CORS configuration
CORS_CONFIG = {
    'ALLOW_ALL_ORIGINS': get_env_var('CORS_ALLOW_ALL_ORIGINS', 'True').lower() == 'true',
    'ALLOWED_ORIGINS': get_env_var('CORS_ALLOWED_ORIGINS', 'https://config-testing.revivepilates.com,https://booking-testing.revivepilates.com').split(',') if get_env_var('CORS_ALLOWED_ORIGINS') else ['https://config-testing.revivepilates.com', 'https://booking-testing.revivepilates.com'],
}
