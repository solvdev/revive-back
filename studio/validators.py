# studio/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_sede_consistency(obj, user_sede):
    """
    Valida que un objeto sea consistente con la sede del usuario.
    """
    if not hasattr(obj, 'sede') or not obj.sede:
        return True  # Si no tiene sede, es válido
    
    if not user_sede:
        raise ValidationError(_("No tienes una sede asignada."))
    
    if obj.sede.id != user_sede.id:
        raise ValidationError(
            _("Este recurso pertenece a la sede '{sede_name}', pero tu sede asignada es '{user_sede_name}'.").format(
                sede_name=obj.sede.name,
                user_sede_name=user_sede.name
            )
        )
    
    return True


def validate_membership_scope_for_sede(membership, sede_id):
    """
    Valida que una membresía sea válida para la sede especificada.
    """
    if membership.scope == "GLOBAL":
        return True  # Las membresías globales son válidas en todas las sedes
    
    if membership.scope == "SEDE":
        if not membership.sede:
            raise ValidationError(_("La membresía de sede específica no tiene sede asignada."))
        
        if membership.sede.id != sede_id:
            raise ValidationError(
                _("Esta membresía es específica de la sede '{membership_sede}', no de la sede actual.").format(
                    membership_sede=membership.sede.name
                )
            )
    
    return True


def validate_promotion_scope_for_sede(promotion, sede_id):
    """
    Valida que una promoción sea válida para la sede especificada.
    """
    if promotion.scope == "GLOBAL":
        return True  # Las promociones globales son válidas en todas las sedes
    
    if promotion.scope == "SEDE":
        if not promotion.sede:
            raise ValidationError(_("La promoción de sede específica no tiene sede asignada."))
        
        if promotion.sede.id != sede_id:
            raise ValidationError(
                _("Esta promoción es específica de la sede '{promotion_sede}', no de la sede actual.").format(
                    promotion_sede=promotion.sede.name
                )
            )
    
    return True


def validate_schedule_for_sede(schedule, sede_id):
    """
    Valida que un horario pertenezca a la sede especificada.
    """
    if not schedule.sede:
        raise ValidationError(_("El horario no tiene sede asignada."))
    
    if schedule.sede.id != sede_id:
        raise ValidationError(
            _("Este horario pertenece a la sede '{schedule_sede}', no a la sede actual.").format(
                schedule_sede=schedule.sede.name
            )
        )
    
    return True


def validate_client_for_sede(client, sede_id):
    """
    Valida que un cliente pertenezca a la sede especificada.
    """
    if not client.sede:
        raise ValidationError(_("El cliente no tiene sede asignada."))
    
    if client.sede.id != sede_id:
        raise ValidationError(
            _("Este cliente pertenece a la sede '{client_sede}', no a la sede actual.").format(
                client_sede=client.sede.name
            )
        )
    
    return True


def validate_booking_consistency(booking_data, user_sede):
    """
    Valida la consistencia de datos para una reserva.
    """
    if not user_sede:
        raise ValidationError(_("No tienes una sede asignada."))
    
    # Validar que el cliente pertenezca a la sede del usuario
    if 'client' in booking_data:
        client = booking_data['client']
        validate_client_for_sede(client, user_sede.id)
    
    # Validar que el horario pertenezca a la sede del usuario
    if 'schedule' in booking_data:
        schedule = booking_data['schedule']
        validate_schedule_for_sede(schedule, user_sede.id)
    
    # Validar que la membresía sea válida para la sede del usuario
    if 'membership' in booking_data and booking_data['membership']:
        membership = booking_data['membership']
        validate_membership_scope_for_sede(membership, user_sede.id)
    
    return True
