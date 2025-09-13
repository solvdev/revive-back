from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import my_bookings_by_month, create_authenticated_booking, AvailabilityView, BookingViewSet, MembershipViewSet, PlanIntentViewSet, PaymentViewSet, PromotionInstanceViewSet, PromotionViewSet, ScheduleViewSet, MonthlyRevenueViewSet, VentaViewSet, summary_by_class_type, attendance_summary, clases_por_mes, get_today_payments_total, get_weekly_closing_summary, get_daily_closing_summary, get_comprehensive_closing_summary, closure_full_summary, BulkBookingViewSet, SedeViewSet, get_dashboard_data, ClassTypeViewSet

# Crear un router para manejar las rutas
router = DefaultRouter()
router.register(r'bookings', BookingViewSet, basename='bookings')
router.register(r'bulk-bookings', BulkBookingViewSet, basename='bulk-bookings')
router.register(r'planintents', PlanIntentViewSet, basename='planintents')
router.register(r'memberships', MembershipViewSet, basename='memberships')
router.register(r'payments', PaymentViewSet, basename='payments')
router.register(r'schedules', ScheduleViewSet, basename='schedule')
router.register(r'monthly-revenue', MonthlyRevenueViewSet, basename='monthly-revenue')
router.register(r'promotions', PromotionViewSet, basename='promotions')
router.register(r'promotion-instances', PromotionInstanceViewSet, basename='promotion-instances')
router.register(r'ventas', VentaViewSet)
router.register(r'sedes', SedeViewSet, basename='sedes')
router.register(r'class-types', ClassTypeViewSet, basename='class-types')

urlpatterns = [
    # Specific endpoints first (before router)
    path('cierres-semanales/', get_weekly_closing_summary, name='cierres-semanales'),
    path('cierres-diarios/', get_daily_closing_summary, name='cierres-diarios'),
    path('cierres-completos/', get_comprehensive_closing_summary, name='cierres-completos'),
    path('availability/', AvailabilityView.as_view(), name='availability'),
    path('summary-by-class-type/', summary_by_class_type),
    path('attendance-summary/', attendance_summary),
    path('clases-por-mes/', clases_por_mes, name='clases-por-mes'),
    path('today/', get_today_payments_total, name='payments-today'),
    path('me/bookings/month/', my_bookings_by_month, name='my_bookings_by_month'),
    path('me/bookings/create/', create_authenticated_booking, name='create_authenticated_booking'),
    path('dashboard-data/', get_dashboard_data, name='dashboard-data'),
    
    # Router endpoints (after specific paths)
    path('payments/closure-full-summary/', closure_full_summary, name='closure-full-summary'),
    path('', include(router.urls)),
]   
