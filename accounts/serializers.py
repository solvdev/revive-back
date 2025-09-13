from rest_framework import serializers
from .models import CustomUser, Client, PasswordResetToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re

# Import Sede model for serializer
try:
    from studio.models import Sede
except ImportError:
    Sede = None

User = get_user_model()


# Mini para no depender de studio.serializers (evitamos ciclos)
class MembershipMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)
    classes_per_month = serializers.IntegerField(allow_null=True)

class CustomUserSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()
    sede = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'groups', 'sede']

    def get_groups(self, obj):
        return [g.name for g in obj.groups.all()]
    
    def get_sede(self, obj):
        if obj.sede:
            return {
                'id': obj.sede.id,
                'name': obj.sede.name,
                'slug': obj.sede.slug
            }
        return None


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(status=True) if Sede else [],
        write_only=True,
        required=True,
        error_messages={'required': 'Debes seleccionar una sede.'}
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name', 'phone', 'sede']
    
    def validate_first_name(self, value):
        """Validate and sanitize first name"""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre es requerido.")
        
        # Remove extra spaces and validate length
        cleaned_value = ' '.join(value.strip().split())
        if len(cleaned_value) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        
        # Check for numbers or special characters (allow spaces and accents)
        if re.search(r'[0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', cleaned_value):
            raise serializers.ValidationError("El nombre no puede contener números o caracteres especiales.")
        
        # Capitalize first letter of each word
        cleaned_value = ' '.join(word.capitalize() for word in cleaned_value.split())
        
        return cleaned_value
    
    def validate_last_name(self, value):
        """Validate and sanitize last name"""
        if not value or not value.strip():
            raise serializers.ValidationError("El apellido es requerido.")
        
        # Remove extra spaces and validate length
        cleaned_value = ' '.join(value.strip().split())
        if len(cleaned_value) < 2:
            raise serializers.ValidationError("El apellido debe tener al menos 2 caracteres.")
        
        # Check for numbers or special characters (allow spaces and accents)
        if re.search(r'[0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', cleaned_value):
            raise serializers.ValidationError("El apellido no puede contener números o caracteres especiales.")
        
        # Capitalize first letter of each word
        cleaned_value = ' '.join(word.capitalize() for word in cleaned_value.split())
        
        return cleaned_value
    
    def validate_phone(self, value):
        """Validate and format phone number for Guatemala"""
        if not value:
            return value
        
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, str(value)))
        
        # Validate length (Guatemala numbers: 8 digits local, 11 with country code)
        if len(digits_only) == 8:
            # Local number, add country code
            return f"+502{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('502'):
            # Already has country code
            return f"+{digits_only}"
        elif len(digits_only) == 10 and digits_only.startswith('502'):
            # Missing +, add it
            return f"+{digits_only}"
        elif len(digits_only) > 0:
            # Invalid format
            raise serializers.ValidationError("El número de teléfono debe tener 8 dígitos para Guatemala.")
        
        return value
    
    def validate_username(self, value):
        """Validate and sanitize username"""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre de usuario es requerido.")
        
        # Remove extra spaces
        cleaned_value = value.strip()
        if len(cleaned_value) < 3:
            raise serializers.ValidationError("El nombre de usuario debe tener al menos 3 caracteres.")
        
        # Check for special characters (allow letters, numbers, and underscores)
        if re.search(r'[^a-zA-Z0-9_]', cleaned_value):
            raise serializers.ValidationError("El nombre de usuario solo puede contener letras, números y guiones bajos.")
        
        return cleaned_value.lower()
    
    def validate_email(self, value):
        """Validate and sanitize email"""
        if not value or not value.strip():
            raise serializers.ValidationError("El email es requerido.")
        
        # Remove extra spaces and convert to lowercase
        cleaned_value = value.strip().lower()
        
        # Basic email format validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', cleaned_value):
            raise serializers.ValidationError("Formato de email inválido.")
        
        return cleaned_value
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        
        # Check if email already exists
        if CustomUser.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este email. Por favor inicia sesión o usa la opción de recuperar contraseña.")
        
        # Check if username already exists
        if CustomUser.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        
        return attrs
    
    def create(self, validated_data):
        phone = validated_data.pop('phone', None)
        sede = validated_data.pop('sede', None)
        validated_data.pop('password_confirm')
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        
        # Create Client record with phone number and sede
        Client.objects.create(
            user=user,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=phone,
            sede=sede,
            status='I',  # Inactivo por defecto
            source='Registro web'  # Indicar que viene del registro web
        )
        
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("No existe una cuenta con este email.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_new_password(self, value):
        """Enhanced password validation"""
        if len(value) < 8:
            raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres.")
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("La contraseña debe contener al menos una letra mayúscula.")
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("La contraseña debe contener al menos una letra minúscula.")
        
        # Check for at least one number
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("La contraseña debe contener al menos un número.")
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', value):
            raise serializers.ValidationError("La contraseña debe contener al menos un carácter especial.")
        
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        
        try:
            reset_token = PasswordResetToken.objects.get(
                token=attrs['token'],
                is_used=False
            )
            if reset_token.is_expired():
                raise serializers.ValidationError("El enlace de recuperación ha expirado.")
            attrs['reset_token'] = reset_token
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Enlace de recuperación inválido.")
        
        return attrs


class ClientSerializer(serializers.ModelSerializer):
    active_membership = serializers.SerializerMethodField()
    current_membership = serializers.SerializerMethodField()
    latest_payment = serializers.SerializerMethodField()
    booking_summary = serializers.SerializerMethodField()  # C
    next_booking = serializers.SerializerMethodField()     # C
    sede = serializers.SerializerMethodField()
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede", queryset=Sede.objects.all() if Sede else [], write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Client
        fields = '__all__'
        extra_kwargs = {
            'email': {'required': False},
            'first_name': {'required': True, 'min_length': 2, 'max_length': 100},
            'last_name': {'required': True, 'min_length': 2, 'max_length': 100},
            'status': {'required': False},
            'age': {'required': False, 'allow_null': True},
            'phone': {'required': False, 'max_length': 15},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the queryset for sede_id field
        if Sede:
            self.fields['sede_id'].queryset = Sede.objects.all()

    def get_sede(self, obj):
        if obj.sede:
            return {
                'id': obj.sede.id,
                'name': obj.sede.name,
                'slug': obj.sede.slug,
                'status': obj.sede.status
            }
        return None
    
    def validate_first_name(self, value):
        """Validate first name - no numbers or special characters"""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre es requerido.")
        
        # Remove extra spaces and validate length
        cleaned_value = ' '.join(value.strip().split())
        if len(cleaned_value) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        
        # Check for numbers or special characters (allow spaces and accents)
        import re
        if re.search(r'[0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', cleaned_value):
            raise serializers.ValidationError("El nombre no puede contener números o caracteres especiales.")
        
        return cleaned_value
    
    def validate_last_name(self, value):
        """Validate last name - no numbers or special characters"""
        if not value or not value.strip():
            raise serializers.ValidationError("El apellido es requerido.")
        
        # Remove extra spaces and validate length
        cleaned_value = ' '.join(value.strip().split())
        if len(cleaned_value) < 2:
            raise serializers.ValidationError("El apellido debe tener al menos 2 caracteres.")
        
        # Check for numbers or special characters (allow spaces and accents)
        import re
        if re.search(r'[0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', cleaned_value):
            raise serializers.ValidationError("El apellido no puede contener números o caracteres especiales.")
        
        return cleaned_value
    
    def validate_phone(self, value):
        """Validate phone number format"""
        if not value:
            return value
        
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, str(value)))
        
        # Validate length (Guatemala numbers: 8 digits local, 11 with country code)
        if len(digits_only) == 8:
            # Local number, add country code
            return f"+502{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('502'):
            # Already has country code
            return f"+{digits_only}"
        elif len(digits_only) == 10 and digits_only.startswith('502'):
            # Missing +, add it
            return f"+{digits_only}"
        elif len(digits_only) > 0:
            # Other format, return as is but warn
            return value
        
        return value

    def get_active_membership(self, obj):
        m = obj.active_membership
        if m:
            return {
                "id": m.id,
                "name": m.name,
                "price": m.price,
                "classes_per_month": m.classes_per_month,
            }
        return None

    def get_current_membership(self, obj):
        m = obj.current_membership
        if m:
            return {
                "id": m.id,
                "name": m.name,
                "price": m.price,
                "classes_per_month": m.classes_per_month,
            }
        return None

    def get_latest_payment(self, obj):
        from studio.models import Payment
        p = (
            Payment.objects
            .filter(client=obj)
            .order_by('-date_paid')
            .values(
                'id', 'amount', 'date_paid', 'valid_until', 'payment_method',
                'membership__id', 'membership__name', 'membership__price', 'membership__classes_per_month'
            )
            .first()
        )
        if not p:
            return None
        return {
            "id": p["id"],
            "amount": p["amount"],
            "date_paid": p["date_paid"],
            "valid_until": p["valid_until"],
            "payment_method": p["payment_method"],
            "membership": {
                "id": p["membership__id"],
                "name": p["membership__name"],
                "price": p["membership__price"],
                "classes_per_month": p["membership__classes_per_month"],
            } if p["membership__id"] is not None else None
        }

    def get_booking_summary(self, obj):
        """Totales rápidos para dashboard."""
        from studio.models import Booking
        today = timezone.now().date()
        upcoming = Booking.objects.filter(client=obj, status='active', class_date__gte=today).count()
        past = Booking.objects.filter(client=obj, status='active', class_date__lt=today).count()
        cancelled = Booking.objects.filter(client=obj, status='cancelled').count()
        return {"upcoming": upcoming, "past": past, "cancelled": cancelled}

    def get_next_booking(self, obj):
        """Siguiente clase (resumen)."""
        from studio.models import Booking
        today = timezone.now().date()
        b = (
            Booking.objects
            .select_related('schedule', 'schedule__class_type')
            .filter(client=obj, status='active', class_date__gte=today)
            .order_by('class_date', 'date_booked')
            .first()
        )
        if not b:
            return None
        return {
            "id": b.id,
            "class_date": b.class_date,
            "attendance_status": b.attendance_status,
            "schedule": {
                "id": b.schedule.id if b.schedule else None,
                "time_slot": b.schedule.time_slot if b.schedule else None,
                "is_individual": b.schedule.is_individual if b.schedule else None,
                "class_type": (b.schedule.class_type.name if b.schedule and b.schedule.class_type else None),
            }
        }

    def create(self, validated_data):
        """Create client and automatically create associated user"""
        from django.contrib.auth.models import Group
        
        # Extract user-related data
        email = validated_data.get('email')
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name')
        
        # Create user if email is provided
        user = None
        if email:
            # Generate username from email or use email
            username = email.split('@')[0]
            
            # Ensure username is unique
            original_username = username
            counter = 1
            while CustomUser.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            
            # Create user
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password='temp_password_123'  # Temporary password, user should reset it
            )
            
            # Assign client role
            try:
                client_group, created = Group.objects.get_or_create(name="client")
                user.groups.add(client_group)
                print(f"User {user.username} assigned to client group")
            except Exception as e:
                print(f"Error assigning client role: {e}")
        
        # Create client with user reference
        validated_data['user'] = user
        client = super().create(validated_data)
        
        return client

class ClientMinimalSerializer(serializers.ModelSerializer):
    """Serializer minimalista para listas - solo campos básicos, sin consultas adicionales"""
    class Meta:
        model = Client
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'status', 'created_at']

class CombinedProfileSerializer(serializers.Serializer):
    user = CustomUserSerializer()
    client = ClientSerializer(allow_null=True)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Permite login con username o email.
    El campo sigue siendo "username" en el body, para no romper el frontend.
    """
    def validate(self, attrs):
        
        
        login = attrs.get("username")  # mantiene el nombre "username"
        password = attrs.get("password")

        

        if not login or not password:
            
            self.error_messages["no_active_account"] = "Credenciales inválidas."
            raise self.fail("no_active_account")

        try:
            user = CustomUser.objects.get(Q(username=login) | Q(email__iexact=login))
            
        except CustomUser.DoesNotExist:
            
            self.error_messages["no_active_account"] = "Credenciales inválidas."
            raise self.fail("no_active_account")

        if not user.check_password(password):
            
            self.error_messages["no_active_account"] = "Credenciales inválidas."
            raise self.fail("no_active_account")
        
        # Verificar que el usuario esté activo y habilitado
        if not user.is_active or not user.is_enabled:
            
            self.error_messages["no_active_account"] = "Cuenta desactivada."
            raise self.fail("no_active_account")

        
        data = super().validate({"username": user.username, "password": password})
        

        # agregar grupos al payload como ya tenías
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "groups": [g.name for g in user.groups.all()],
        }
        
        return data