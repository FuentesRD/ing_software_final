from notificaciones.models import Notificacion


def notificar(usuario, tipo, mensaje):
    return Notificacion.objects.create(usuario=usuario, tipo=tipo, mensaje=mensaje[:500])
