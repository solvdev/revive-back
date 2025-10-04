# studio/management/mails/mails.py
# from django.conf import settings
from django.core.mail import send_mail

# from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_user_generated_email(user, client, temp_password):
    """Enviar email cuando se genera un usuario para un cliente existente"""
    frontend_url = "https://booking.revivepilatesgt.com"

    login_url = f"{frontend_url}/auth/login"

    subject = "¡Bienvenido a Revive Pilates - Tu cuenta está lista!"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">¡Bienvenido a Revive Pilates!</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>¡Excelente noticia! Hemos creado tu cuenta en nuestro sistema de reservas online.
            Ahora puedes gestionar tus clases de manera fácil y rápida.</p>

            <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #27ae60; margin-top: 0;">📱 Tus credenciales de acceso:</h3>
                <p><strong>Email:</strong> {user.email}</p>
                <p><strong>Contraseña temporal:</strong> <code style="background-color: #f1f1f1; padding: 4px 8px; border-radius: 4px;">{temp_password}</code></p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}"
                   style="background-color: #27ae60; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">
                    🚀 Iniciar Sesión Ahora
                </a>
            </div>

            <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="color: #856404; margin-top: 0;">🔒 Importante - Seguridad:</h4>
                <ul style="color: #856404;">
                    <li>Cambia tu contraseña temporal después del primer inicio de sesión</li>
                    <li>Tu contraseña temporal es válida por 7 días</li>
                    <li>Si no cambias la contraseña, se desactivará tu cuenta</li>
                </ul>
            </div>

            <h3>🎯 ¿Qué puedes hacer ahora?</h3>
            <ul>
                <li>📅 <strong>Reservar clases:</strong> Ve las clases disponibles y reserva tu lugar</li>
                <li>📊 <strong>Ver tu historial:</strong> Revisa tus clases pasadas y futuras</li>
                <li>💳 <strong>Gestionar membresías:</strong> Administra tus planes y pagos</li>
                <li>📱 <strong>Perfil personal:</strong> Actualiza tu información de contacto</li>
            </ul>

            <p>Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.</p>

            <p>¡Esperamos verte pronto en clase!</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>

        <div style="text-align: center; padding: 20px; background-color: #f8f9fa; color: #6c757d; font-size: 12px;">
            <p>Este email fue enviado automáticamente. Por favor no respondas a este mensaje.</p>
            <p>Si no solicitaste esta cuenta, contacta con nosotros inmediatamente.</p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_welcome_email(user, client):
    """Enviar email de bienvenida para nuevos registros"""
    frontend_url = "https://booking.revivepilatesgt.com"

    login_url = f"{frontend_url}/auth/login"

    subject = "¡Bienvenido a Revive Pilates!"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">¡Bienvenido a Revive Pilates!</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>¡Gracias por registrarte en Revive Pilates! Estamos emocionados de tenerte como parte de nuestra comunidad.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}"
                   style="background-color: #27ae60; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">
                    🚀 Iniciar Sesión
                </a>
            </div>

            <h3>🎯 ¿Qué puedes hacer ahora?</h3>
            <ul>
                <li>📅 <strong>Reservar clases:</strong> Ve las clases disponibles y reserva tu lugar</li>
                <li>📊 <strong>Ver tu historial:</strong> Revisa tus clases pasadas y futuras</li>
                <li>💳 <strong>Gestionar membresías:</strong> Administra tus planes y pagos</li>
                <li>📱 <strong>Perfil personal:</strong> Actualiza tu información de contacto</li>
            </ul>

            <p>Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.</p>

            <p>¡Esperamos verte pronto en clase!</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_membership_cancellation_email(client):
    """Enviar email cuando se cancela una membresía"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = "Membresía cancelada - Revive Pilates"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Membresía Cancelada</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Te informamos que tu membresía ha sido cancelada. Si tienes alguna pregunta sobre esta acción, por favor contacta con nosotros.</p>

            <p>Si deseas reactivar tu membresía o tienes alguna consulta, no dudes en contactarnos.</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_booking_confirmation_email(booking, client):
    """Enviar email de confirmación de reserva"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = f"Reserva confirmada - {booking.schedule.class_type.name}"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Reserva Confirmada</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Tu reserva ha sido confirmada exitosamente.</p>

            <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #27ae60; margin-top: 0;">📅 Detalles de tu clase:</h3>
                <p><strong>Clase:</strong> {booking.schedule.class_type.name if booking.schedule.class_type else 'Sin tipo'}</p>
                <p><strong>Fecha:</strong> {booking.class_date}</p>
                <p><strong>Hora:</strong> {booking.schedule.time_slot}</p>
                <p><strong>Instructor:</strong> {booking.schedule.coach.first_name + ' ' + booking.schedule.coach.last_name if booking.schedule.coach else 'Por asignar'}</p>
            </div>

            <p>¡Esperamos verte en clase!</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_subscription_confirmation_email(client, membership):
    """Enviar email de confirmación de suscripción"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = "Suscripción confirmada - Revive Pilates"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Suscripción Confirmada</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Tu suscripción ha sido confirmada exitosamente.</p>

            <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #27ae60; margin-top: 0;">📋 Detalles de tu membresía:</h3>
                <p><strong>Plan:</strong> {membership.plan.name if membership.plan else 'N/A'}</p>
                <p><strong>Fecha de inicio:</strong> {membership.start_date}</p>
                <p><strong>Fecha de vencimiento:</strong> {membership.end_date}</p>
            </div>

            <p>¡Disfruta de tu membresía!</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_individual_booking_pending_email(booking, client):
    """Enviar email de reserva pendiente"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = f"Reserva pendiente - {booking.schedule.class_type.name}"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Reserva Pendiente</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Tu reserva está pendiente de confirmación.</p>

            <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #856404; margin-top: 0;">⏳ Detalles de tu reserva:</h3>
                <p><strong>Clase:</strong> {booking.schedule.class_type.name if booking.schedule.class_type else 'Sin tipo'}</p>
                <p><strong>Fecha:</strong> {booking.class_date}</p>
                <p><strong>Hora:</strong> {booking.schedule.time_slot}</p>
            </div>

            <p>Te notificaremos cuando tu reserva sea confirmada.</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_booking_cancellation_email(booking, client):
    """Enviar email de cancelación de reserva"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = f"Reserva cancelada - {booking.schedule.class_type.name}"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Reserva Cancelada</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Tu reserva ha sido cancelada exitosamente.</p>

            <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #721c24; margin-top: 0;">❌ Detalles de la reserva cancelada:</h3>
                <p><strong>Clase:</strong> {booking.schedule.class_type.name if booking.schedule.class_type else 'Sin tipo'}</p>
                <p><strong>Fecha:</strong> {booking.class_date}</p>
                <p><strong>Hora:</strong> {booking.schedule.time_slot}</p>
            </div>

            <p>Si necesitas hacer una nueva reserva, puedes hacerlo desde tu cuenta.</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_booking_reschedule_email(booking, client):
    """Enviar email de reprogramación de reserva"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = f"Reserva reprogramada - {booking.schedule.class_type.name}"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Reserva Reprogramada</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Tu reserva ha sido reprogramada exitosamente.</p>

            <div style="background-color: #d1ecf1; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #0c5460; margin-top: 0;">🔄 Nuevos detalles de tu clase:</h3>
                <p><strong>Clase:</strong> {booking.schedule.class_type.name if booking.schedule.class_type else 'Sin tipo'}</p>
                <p><strong>Fecha:</strong> {booking.class_date}</p>
                <p><strong>Hora:</strong> {booking.schedule.time_slot}</p>
            </div>

            <p>¡Esperamos verte en tu nueva clase!</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_bulk_booking_confirmation_email(client, bookings):
    """Enviar email de confirmación de reservas múltiples"""
    frontend_url = "https://booking.revivepilatesgt.com"

    subject = f"Reservas confirmadas - {len(bookings)} clases"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa;">
            <img src="https://revivepilates.s3.us-east-2.amazonaws.com/imgs/revivewhite.png" alt="Revive Pilates" style="max-width: 200px;">
            <h1 style="color: #2c3e50; margin-top: 20px;">Reservas Confirmadas</h1>
        </div>

        <div style="padding: 30px;">
            <p>Hola {client.first_name},</p>

            <p>Se han confirmado {len(bookings)} reservas exitosamente.</p>

            <div style="background-color: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #27ae60; margin-top: 0;">📅 Tus clases reservadas:</h3>
                <ul>
                    {''.join([f'<li><strong>{booking.schedule.class_type.name if booking.schedule.class_type else "Sin tipo"}</strong> - {booking.class_date} a las {booking.schedule.time_slot}</li>' for booking in bookings])}
                </ul>
            </div>

            <p>¡Esperamos verte en todas tus clases!</p>

            <p>Saludos,<br>
            <strong>Equipo Revive Pilates</strong></p>
        </div>
    </div>
    """

    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "no-reply@revivepilatesgt.com",
        [client.email],
        html_message=html_message,
        fail_silently=False,
    )
