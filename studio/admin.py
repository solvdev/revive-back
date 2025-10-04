# studio/admin.py
from django.contrib import admin

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


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "slug")
    ordering = ("name",)


@admin.register(ClassType)
class ClassTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("sede", "start_time", "end_time", "is_active", "created_at")
    list_filter = ("sede", "is_active", "created_at")
    search_fields = ("sede__name",)
    ordering = ("sede", "start_time")


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("day", "time_slot", "is_individual", "capacity", "sede")
    list_filter = ("sede", "day", "is_individual")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "classes_per_month", "scope", "sede")
    list_filter = ("scope", "sede")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "membership",
        "amount",
        "date_paid",
        "valid_until",
        "extra_classes",
        "sede",
    )
    list_filter = ("sede", "payment_method", "date_paid")
    date_hierarchy = "date_paid"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "schedule", "class_date", "sede")
    list_filter = ("sede", "class_date", "attendance_status")
    date_hierarchy = "class_date"


@admin.register(PlanIntent)
class PlanIntentAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "membership", "selected_at", "is_confirmed", "sede")
    list_filter = ("is_confirmed", "selected_at", "sede")
    search_fields = ("client__first_name", "client__last_name", "membership__name")


@admin.register(MonthlyRevenue)
class MonthlyRevenueAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "month",
        "total_amount",
        "payment_count",
        "last_updated",
        "sede",
    )
    list_filter = ("year", "month", "sede")
    ordering = ("-year", "-month")


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "membership",
        "price",
        "start_date",
        "end_date",
        "scope",
        "sede",
    )
    list_filter = ("start_date", "end_date", "membership", "scope", "sede")
    search_fields = ("name", "membership__name")


@admin.register(PromotionInstance)
class PromotionInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "promotion", "created_at")
    filter_horizontal = ("clients",)
    list_filter = ("promotion", "created_at")
    search_fields = ("promotion__name",)


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "product_name",
        "quantity",
        "price_per_unit",
        "total_amount",
        "payment_method",
        "date_sold",
        "sede",
    )
    list_filter = ("payment_method", "date_sold", "sede")
    search_fields = ("client__first_name", "client__last_name", "product_name")
    date_hierarchy = "date_sold"


@admin.register(BulkBooking)
class BulkBookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "status",
        "total_bookings",
        "successful_bookings",
        "failed_bookings",
        "created_at",
        "sede",
    )
    list_filter = ("status", "created_at", "sede")
    search_fields = ("client__first_name", "client__last_name")
    date_hierarchy = "created_at"
    readonly_fields = (
        "total_bookings",
        "successful_bookings",
        "failed_bookings",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("client")
