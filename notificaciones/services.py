from notificaciones.models import Notificacion


def notificar(usuario, tipo, mensaje):
    return Notificacion.objects.create(usuario=usuario, tipo=tipo, mensaje=mensaje[:500])


def notificaciones_sin_leer(usuario):
    return Notificacion.objects.filter(usuario=usuario, leida=False).count()


def marcar_todas_leidas(usuario):
    """Marca como leídas todas las notificaciones del usuario; devuelve cuántas cambió."""
    return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
