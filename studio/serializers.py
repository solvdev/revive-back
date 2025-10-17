from accounts.models import Client
from rest_framework import serializers

from .models import (
    Booking,
    BulkBooking,
    ClassType,
    Membership,
    MonthlyRevenue,
    Payment,
    PlanIntent,
    Promotion,
    PromotionInstance,
    Schedule,
    Sede,
    TimeSlot,
    Venta,
)
from .validators import (
    validate_booking_consistency,
    validate_client_for_sede,
    validate_membership_scope_for_sede,
    validate_promotion_scope_for_sede,
    validate_schedule_for_sede,
    validate_sede_consistency,
)

# Note: PasswordResetToken is in accounts.models, not studio.models


class SedeAwareSerializer(serializers.ModelSerializer):
    """
    Serializer base que incluye validaciones de sede automáticamente.
    """
    
    def validate(self, attrs):
        """Validar consistencia de sede."""
        validated_data = super().validate(attrs)
        
        # Obtener la sede del usuario desde el contexto de la request
        request = self.context.get('request')
        if request and hasattr(request, 'user_sede') and request.user_sede:
            user_sede = request.user_sede
            
            # Validar que el objeto sea consistente con la sede del usuario
            if hasattr(self, 'instance') and self.instance:
                validate_sede_consistency(self.instance, user_sede)
            
            # Validar datos específicos según el tipo de serializer
            self._validate_sede_specific_data(validated_data, user_sede)
        
        return validated_data
    
    def _validate_sede_specific_data(self, validated_data, user_sede):
        """Validar datos específicos de sede. Sobrescribir en subclases."""
        pass


class SedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = "__all__"


class TimeSlotSerializer(serializers.ModelSerializer):
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
    )
    time_slot_display = serializers.ReadOnlyField()
    time_slot_value = serializers.ReadOnlyField()
    
    class Meta:
        model = TimeSlot
        fields = [
            "id",
            "sede",
            "sede_id", 
            "start_time",
            "end_time",
            "is_active",
            "created_at",
            "time_slot_display",
            "time_slot_value"
        ]
        read_only_fields = ["id", "created_at"]


class ClassTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassType
        fields = "__all__"


class ScheduleSerializer(serializers.ModelSerializer):
    class_type = ClassTypeSerializer(read_only=True)
    class_type_id = serializers.PrimaryKeyRelatedField(
        source="class_type", queryset=ClassType.objects.all(), write_only=True
    )
    day_display = serializers.CharField(source="get_day_display", read_only=True)
    time_display = serializers.CharField(source="get_time_slot_display", read_only=True)
    coach_username = serializers.CharField(source="coach.username", read_only=True)
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Schedule
        fields = [
            "id",
            "day",
            "day_display",
            "time_slot",
            "time_display",
            "capacity",
            "is_individual",
            "class_type",
            "class_type_id",
            "coach",
            "coach_username",
            "sede",
            "sede_id",
        ]


class SimpleClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"


class BookingAttendanceInlineSerializer(serializers.ModelSerializer):
    client = SimpleClientSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "client", "attendance_status", "class_date"]


class ScheduleWithBookingsSerializer(serializers.ModelSerializer):
    class_type = ClassTypeSerializer(read_only=True)
    bookings = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            "id",
            "day",
            "time_slot",
            "class_type",
            "is_individual",
            "capacity",
            "bookings",
        ]

    def get_bookings(self, obj):
        today = self.context.get("today")
        bookings = Booking.objects.filter(
            schedule=obj, class_date=today, status="active"
        )
        return BookingAttendanceInlineSerializer(bookings, many=True).data


class BookingAttendanceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["attendance_status"]
        extra_kwargs = {
            "attendance_status": {
                "required": True,
                "choices": Booking.ATTENDANCE_CHOICES,
            }
        }


class MembershipSerializer(serializers.ModelSerializer):
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "name",
            "price",
            "classes_per_month",
            "scope",
            "scope_display",
            "sede",
            "sede_id",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    client = serializers.StringRelatedField(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        source="client", queryset=Client.objects.all()
    )
    membership = MembershipSerializer(read_only=True)
    membership_id = serializers.PrimaryKeyRelatedField(
        source="membership", queryset=Membership.objects.all(), write_only=True
    )
    promotion_id = serializers.PrimaryKeyRelatedField(
        source="promotion",
        queryset=Promotion.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    promotion = serializers.StringRelatedField(read_only=True)
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "client",
            "client_id",
            "membership",
            "membership_id",
            "promotion",
            "promotion_id",
            "promotion_instance",
            "payment_method",
            "promotion_instance_id",
            "amount",
            "date_paid",
            "valid_from",
            "valid_until",
            "receipt_number",
            "month_year",
            "extra_classes",
            "sede",
            "sede_id",
            # Campos para pagos anticipados
            "is_advance_payment",
            "target_month",
            "effective_from",
            "effective_until",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "id",
            "valid_from",  # Calculado automáticamente por el backend
            "valid_until",  # Calculado automáticamente por el backend
            "month_year",   # Calculado automáticamente por el backend
            "receipt_number",  # Generado automáticamente
            "effective_from",  # Calculado automáticamente por el backend
            "effective_until",  # Calculado automáticamente por el backend
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]


class BookingSerializer(SedeAwareSerializer):
    client = serializers.StringRelatedField(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=__import__("accounts.models").models.Client.objects.all(),
        write_only=True,
    )
    schedule = serializers.StringRelatedField(read_only=True)
    schedule_id = serializers.PrimaryKeyRelatedField(
        source="schedule", queryset=Schedule.objects.all(), write_only=True
    )
    membership = serializers.StringRelatedField(read_only=True)
    membership_id = serializers.PrimaryKeyRelatedField(
        source="membership",
        queryset=Membership.objects.all(),
        write_only=True,
        required=False,
    )
    # Agregar la membresía activa del cliente
    client_active_membership = serializers.SerializerMethodField()
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "client",
            "client_id",
            "schedule",
            "schedule_id",
            "class_date",
            "date_booked",
            "membership",
            "membership_id",
            "client_active_membership",
            "sede",
            "sede_id",
        ]

    def get_client_active_membership(self, obj):
        """Obtener la membresía activa del cliente"""
        if obj.client.current_membership:
            return obj.client.current_membership.name
        return None

    def _validate_sede_specific_data(self, validated_data, user_sede):
        """Validar datos específicos de sede para bookings."""
        # Validar que el cliente pertenezca a la sede del usuario
        if 'client' in validated_data:
            validate_client_for_sede(validated_data['client'], user_sede.id)
        
        # Validar que el horario pertenezca a la sede del usuario
        if 'schedule' in validated_data:
            validate_schedule_for_sede(validated_data['schedule'], user_sede.id)
        
        # Validar que la membresía sea válida para la sede del usuario
        if 'membership' in validated_data and validated_data['membership']:
            validate_membership_scope_for_sede(validated_data['membership'], user_sede.id)


class PlanIntentSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = PlanIntent
        fields = "__all__"

    def get_client(self, obj):
        from accounts.serializers import ClientSerializer

        return ClientSerializer(obj.client).data

    def get_membership(self, obj):
        return MembershipSerializer(obj.membership).data


class BookingHistorialSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    client_id = serializers.IntegerField(source="client.id", read_only=True)
    membership = serializers.SerializerMethodField()
    client_active_membership = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    schedule_id = serializers.IntegerField(
        source="schedule.id", read_only=True
    )  # 🔥 importante
    class_date = serializers.DateField(format="%Y-%m-%d")

    class Meta:
        model = Booking
        fields = [
            "id",
            "client",
            "client_id",
            "schedule",
            "schedule_id",
            "class_date",
            "attendance_status",
            "date_booked",
            "membership",
            "client_active_membership",
            "cancellation_reason",
        ]

    def get_client(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}"

    def get_membership(self, obj):
        if obj.membership:
            return f"{obj.membership.name} ({obj.membership.price})"
        return "-"

    def get_client_active_membership(self, obj):
        """Obtener la membresía activa del cliente"""
        if obj.client.current_membership:
            return obj.client.current_membership.name
        return None

    def get_schedule(self, obj):
        if obj.schedule:
            day_name = obj.class_date.strftime("%A")
            day_name_es = {
                "Monday": "Lunes",
                "Tuesday": "Martes",
                "Wednesday": "Miércoles",
                "Thursday": "Jueves",
                "Friday": "Viernes",
                "Saturday": "Sábado",
                "Sunday": "Domingo",
            }.get(day_name, day_name)
            return f"{day_name_es} {obj.schedule.time_slot} ({'Individual' if obj.schedule.is_individual else 'Grupal'})"
        return "-"


class MonthlyRevenueSerializer(serializers.ModelSerializer):
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MonthlyRevenue
        fields = [
            "id",
            "year",
            "month",
            "total_amount",
            "payment_count",
            "venta_total",
            "venta_count",
            "last_updated",
            "sede",
            "sede_id",
        ]


class PromotionSerializer(serializers.ModelSerializer):
    membership = serializers.SerializerMethodField()
    membership_id = serializers.PrimaryKeyRelatedField(
        source="membership", queryset=Membership.objects.all(), write_only=True
    )
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)

    class Meta:
        model = Promotion
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "price",
            "membership",
            "membership_id",
            "scope",
            "scope_display",
            "sede",
            "sede_id",
        ]

    def get_membership(self, obj):
        # No se importa nada, MembershipSerializer ya está en este archivo
        return MembershipSerializer(obj.membership).data


class PromotionInstanceSerializer(serializers.ModelSerializer):
    promotion = PromotionSerializer(read_only=True)
    promotion_id = serializers.PrimaryKeyRelatedField(
        source="promotion", queryset=Promotion.objects.all(), write_only=True
    )
    clients = serializers.SerializerMethodField()
    client_ids = serializers.PrimaryKeyRelatedField(
        source="clients", many=True, queryset=Client.objects.all(), write_only=True
    )

    class Meta:
        model = PromotionInstance
        fields = [
            "id",
            "promotion",
            "promotion_id",
            "clients",
            "client_ids",
            "created_at",
        ]

    def get_clients(self, obj):
        from accounts.serializers import ClientSerializer

        return ClientSerializer(obj.clients.all(), many=True).data


class VentaSerializer(serializers.ModelSerializer):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client", queryset=Client.objects.all()
    )
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id",
            "client_id",
            "product_name",
            "quantity",
            "price_per_unit",
            "total_amount",
            "payment_method",
            "notes",
            "date_sold",
            "sede",
            "sede_id",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "id",
            "total_amount",
            "created_at",
            "updated_at",
            "created_by",
            "modified_by",
        ]


class BookingMiniSerializer(serializers.ModelSerializer):
    schedule = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "class_date",
            "status",
            "attendance_status",
            "date_booked",
            "schedule",
            "membership",
        ]

    def get_schedule(self, obj):
        if not obj.schedule:
            return None
        return {
            "id": obj.schedule.id,
            "time_slot": obj.schedule.time_slot,
            "is_individual": obj.schedule.is_individual,
            "class_type": (
                obj.schedule.class_type.name if obj.schedule.class_type else None
            ),
        }

    def get_membership(self, obj):
        if not obj.membership:
            return None
        return {
            "id": obj.membership.id,
            "name": obj.membership.name,
            "price": obj.membership.price,
        }


class BulkBookingRequestSerializer(serializers.Serializer):
    """Serializer for bulk booking requests"""

    client_id = serializers.IntegerField()
    bookings = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=20,  # Limit to prevent abuse
    )
    number_of_slots = serializers.IntegerField(
        min_value=1,
        required=False,
        default=1,
        help_text="Number of slots to book for each schedule (default: 1, max depends on schedule capacity)",
    )

    def validate_bookings(self, value):
        """Validate each booking in the list"""
        for i, booking in enumerate(value):
            if not isinstance(booking, dict):
                raise serializers.ValidationError(f"Booking {i} must be a dictionary")

            required_fields = ["schedule_id", "class_date"]
            for field in required_fields:
                if field not in booking:
                    raise serializers.ValidationError(
                        f"Booking {i} missing required field: {field}"
                    )

            # Validate class_date format
            try:
                from datetime import datetime

                datetime.strptime(booking["class_date"], "%Y-%m-%d")
            except ValueError:
                raise serializers.ValidationError(
                    f"Booking {i} has invalid date format. Use YYYY-MM-DD"
                )

        return value


class BulkBookingSerializer(serializers.ModelSerializer):
    """Serializer for bulk booking model"""

    client = serializers.StringRelatedField(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        source="client", queryset=Client.objects.all(), write_only=True
    )
    sede = SedeSerializer(read_only=True)
    sede_id = serializers.PrimaryKeyRelatedField(
        source="sede",
        queryset=Sede.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    bookings = serializers.SerializerMethodField()

    class Meta:
        model = BulkBooking
        fields = [
            "id",
            "client",
            "client_id",
            "status",
            "total_bookings",
            "successful_bookings",
            "failed_bookings",
            "created_at",
            "updated_at",
            "notes",
            "sede",
            "sede_id",
            "bookings",
        ]
        read_only_fields = [
            "status",
            "total_bookings",
            "successful_bookings",
            "failed_bookings",
            "created_at",
            "updated_at",
        ]

    def get_bookings(self, obj):
        """Get related bookings for this bulk booking"""
        return BookingSerializer(obj.bookings.all(), many=True).data


class BulkBookingResultSerializer(serializers.Serializer):
    """Serializer for bulk booking results"""

    bulk_booking_id = serializers.IntegerField()
    status = serializers.CharField()
    total_requested = serializers.IntegerField()
    successful = serializers.IntegerField()
    failed = serializers.IntegerField()
    successful_bookings = serializers.ListField(child=serializers.DictField())
    failed_bookings = serializers.ListField(child=serializers.DictField())
    errors = serializers.ListField(child=serializers.CharField(), required=False)
