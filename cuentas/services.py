from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Usuario


@transaction.atomic
def cambiar_estado_cuenta(*, responsable, usuario_id, activar):
    if (
        not responsable.is_authenticated
        or not responsable.is_active
        or responsable.tipo_usuario != Usuario.TipoUsuario.BIBLIOTECARIO
    ):
        raise PermissionDenied(
            "Solo el bibliotecario puede cambiar el estado de una cuenta."
        )

    usuario = Usuario.objects.select_for_update().get(pk=usuario_id)

    if usuario.pk == responsable.pk and not activar:
        raise ValidationError("No puedes desactivar tu propia cuenta.")

    usuario.is_active = activar
    usuario.save(update_fields=["is_active"])

    return usuario

@transaction.atomic
def cambiar_bloqueo_cuenta(
    *,
    responsable,
    usuario_id,
    bloquear,
    motivo="",
):
    if (
        not responsable.is_authenticated
        or not responsable.is_active
        or responsable.tipo_usuario != Usuario.TipoUsuario.BIBLIOTECARIO
    ):
        raise PermissionDenied(
            "Solo el bibliotecario puede cambiar el bloqueo."
        )

    motivo = motivo.strip()

    if bloquear and not motivo:
        raise ValidationError("Debes indicar el motivo del bloqueo.")

    if bloquear and len(motivo) > 255:
        raise ValidationError("El motivo no puede superar 255 caracteres.")

    usuario = Usuario.objects.select_for_update().get(pk=usuario_id)
    usuario.bloqueado = bloquear
    usuario.motivo_bloqueo = motivo if bloquear else None
    usuario.save(update_fields=["bloqueado", "motivo_bloqueo"])

    return usuario