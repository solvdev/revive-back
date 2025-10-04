# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
import secrets
import string

from .models import Client, CustomUser
from studio.models import Sede
from studio.management.mails.mails import send_user_generated_email


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permisos",
            {
                "fields": (
                    "is_active",
                    "is_enabled",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas importantes", {"fields": ("last_login", "date_joined")}),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "sede",
        "created_at",
        "email_sent_status",
        "first_login_status",
        "user_status",
        "status",
    )
    list_filter = (
        "status",
        "email_sent",
        "first_login",
        "sede",
        "created_at",
        "trial_used",
    )
    search_fields = ("first_name", "last_name", "email", "phone")
    list_editable = ("status",)
    readonly_fields = ("created_at", "email_sent", "first_login")
    
    fieldsets = (
        ("Información Personal", {
            "fields": ("first_name", "last_name", "email", "phone")
        }),
        ("Información Adicional", {
            "fields": ("address", "age", "dpi", "sex")
        }),
        ("Estado y Seguimiento", {
            "fields": ("status", "trial_used", "email_sent", "first_login", "created_at")
        }),
        ("Relaciones", {
            "fields": ("user", "sede", "current_membership")
        }),
        ("Otros", {
            "fields": ("source", "notes"),
            "classes": ("collapse",)
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'send-new-user-emails/',
                self.admin_site.admin_view(self.send_new_user_emails_view),
                name='accounts_client_send_new_user_emails',
            ),
        ]
        return custom_urls + urls
    
    def email_sent_status(self, obj):
        """Muestra el estado del envío de correo con colores"""
        if obj.email_sent:
            return format_html('<span style="color: green;">✅ Enviado</span>')
        else:
            return format_html('<span style="color: red;">❌ Pendiente</span>')
    email_sent_status.short_description = 'Correo Enviado'
    
    def first_login_status(self, obj):
        """Muestra el estado del primer login con colores"""
        if obj.user and obj.user.last_login:
            return format_html('<span style="color: green;">✅ Sí</span>')
        elif obj.user:
            return format_html('<span style="color: orange;">⏳ Pendiente</span>')
        else:
            return format_html('<span style="color: red;">❌ Sin usuario</span>')
    first_login_status.short_description = 'Primer Login'
    
    def user_status(self, obj):
        """Muestra si tiene usuario asociado"""
        if obj.user:
            return format_html('<span style="color: green;">✅ Asociado</span>')
        else:
            return format_html('<span style="color: red;">❌ Sin usuario</span>')
    user_status.short_description = 'Usuario'
    
    def changelist_view(self, request, extra_context=None):
        """Agrega botón personalizado a la vista de lista"""
        extra_context = extra_context or {}
        extra_context['show_send_emails_button'] = True
        return super().changelist_view(request, extra_context=extra_context)
    
    def send_new_user_emails_view(self, request):
        """Vista para enviar correos a usuarios nuevos"""
        if request.method == 'POST':
            sede_id = request.POST.get('sede_id')
            days_old = int(request.POST.get('days_old', 1))
            
            # Calcular fecha límite
            cutoff_date = timezone.now() - timedelta(days=days_old)
            
            # Construir queryset
            queryset = Client.objects.filter(
                user__isnull=False,
                email_sent=False,
                user__last_login__isnull=True,
                user__date_joined__lte=cutoff_date,
                email__isnull=False,
                email__gt=''
            ).select_related('user', 'sede')
            
            # Filtrar por sede si se especifica
            if sede_id:
                try:
                    sede = Sede.objects.get(id=sede_id, status=True)
                    queryset = queryset.filter(sede=sede)
                except Sede.DoesNotExist:
                    messages.error(request, f'Sede con ID {sede_id} no encontrada')
                    return HttpResponseRedirect(reverse('admin:accounts_client_changelist'))
            
            candidates = queryset.all()
            total_candidates = candidates.count()
            
            if total_candidates == 0:
                messages.info(request, 'No hay usuarios nuevos pendientes de correo')
                return HttpResponseRedirect(reverse('admin:accounts_client_changelist'))
            
            # Procesar envío
            emails_sent = 0
            emails_failed = 0
            
            for client in candidates:
                try:
                    user = client.user
                    
                    # Generar contraseña temporal
                    temp_password = self.generate_temp_password()
                    
                    # Establecer contraseña
                    user.set_password(temp_password)
                    user.save()
                    
                    # Enviar correo
                    send_user_generated_email(user, client, temp_password)
                    
                    # Marcar como enviado
                    client.email_sent = True
                    client.save(update_fields=['email_sent'])
                    
                    emails_sent += 1
                    
                except Exception as e:
                    emails_failed += 1
                    continue
            
            # Mostrar resultado
            if emails_sent > 0:
                messages.success(
                    request, 
                    f'Se enviaron {emails_sent} correos exitosamente. '
                    f'Fallos: {emails_failed}'
                )
            else:
                messages.error(request, f'No se pudo enviar ningún correo. Fallos: {emails_failed}')
            
            return HttpResponseRedirect(reverse('admin:accounts_client_changelist'))
        
        # GET request - mostrar formulario
        sedes = Sede.objects.filter(status=True)
        context = {
            'title': 'Enviar Correos a Usuarios Nuevos',
            'sedes': sedes,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
        }
        return render(request, 'admin/accounts/client/send_new_user_emails.html', context)
    
    def generate_temp_password(self):
        """Genera una contraseña temporal segura"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(characters) for _ in range(12))
