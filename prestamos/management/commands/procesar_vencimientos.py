"""Tareas del reloj del sistema (paquete D, usa los métodos de prestamos):

- CU-34: marca como VENCIDO cada préstamo ACTIVO cuya fecha de vencimiento ya pasó y avisa al lector.
- CU-35: expira las solicitudes y reservas que no se recogieron a tiempo (RN-06) y libera el ejemplar:
  pasa a la siguiente reserva (RN-12) o queda DISPONIBLE.
- CU-36: envía un recordatorio a quien tiene un préstamo que vence pronto (una vez al día por préstamo).

Se ejecuta a mano o desde el programador de tareas:
    python manage.py procesar_vencimientos
    python manage.py procesar_vencimientos --dias-aviso 2

Cada préstamo o reserva se procesa en su propia transacción con select_for_update() (RNF-03),
en el orden préstamo → ejemplar → reserva, igual que los servicios de prestamos.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalogo.models import Ejemplar
from notificaciones.models import Notificacion
from notificaciones.services import notificar
from prestamos.models import Prestamo, Reserva
from prestamos.services import asignar_siguiente_reserva

ESTADOS_NO_ASIGNABLES = {Ejemplar.Estado.EN_REPARACION, Ejemplar.Estado.PERDIDO, Ejemplar.Estado.BAJA}


def _liberar(ejemplar):
    """El ejemplar apartado queda libre: siguiente reserva o DISPONIBLE (RN-12)."""
    if ejemplar.estado in ESTADOS_NO_ASIGNABLES:
        return
    if asignar_siguiente_reserva(ejemplar) is None:
        ejemplar.cambiar_estado(Ejemplar.Estado.DISPONIBLE)


def marcar_vencidos(hoy=None):
    """CU-34. Devuelve cuántos préstamos pasaron a VENCIDO."""
    hoy = hoy or timezone.localdate()
    total = 0
    ids = Prestamo.objects.filter(estado=Prestamo.Estado.ACTIVO, fecha_vencimiento__lt=hoy).values_list("pk", flat=True)
    for pk in list(ids):
        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().select_related("usuario", "ejemplar__libro").get(pk=pk)
            if prestamo.estado != Prestamo.Estado.ACTIVO:
                continue
            prestamo.marcar_vencido()
            notificar(
                prestamo.usuario,
                "VENCIDO",
                f"Tu préstamo de «{prestamo.ejemplar.libro}» venció el {prestamo.fecha_vencimiento:%d/%m/%Y}. "
                f"Devuélvelo cuanto antes: cada día de retraso genera multa (préstamo {prestamo.pk}).",
            )
            total += 1
    return total


def expirar_solicitudes(ahora=None):
    """CU-35 (solicitudes). Devuelve cuántas solicitudes expiraron."""
    ahora = ahora or timezone.now()
    total = 0
    ids = Prestamo.objects.filter(
        estado=Prestamo.Estado.SOLICITADO, fecha_limite_recoger__lt=ahora
    ).values_list("pk", flat=True)
    for pk in list(ids):
        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().select_related("usuario").get(pk=pk)
            if prestamo.estado != Prestamo.Estado.SOLICITADO:
                continue
            ejemplar = Ejemplar.objects.select_for_update().select_related("libro").get(pk=prestamo.ejemplar_id)
            prestamo.expirar()
            _liberar(ejemplar)
            notificar(
                prestamo.usuario,
                "GENERAL",
                f"Tu solicitud de «{ejemplar.libro}» expiró porque no se recogió a tiempo (préstamo {prestamo.pk}).",
            )
            total += 1
    return total


def expirar_reservas(ahora=None):
    """CU-35 (reservas). Devuelve cuántas reservas expiraron."""
    ahora = ahora or timezone.now()
    total = 0
    pendientes = Reserva.objects.filter(
        estado=Reserva.Estado.DISPONIBLE, fecha_expiracion__lt=ahora
    ).values_list("pk", "ejemplar_asignado_id")
    for pk, ejemplar_id in list(pendientes):
        with transaction.atomic():
            ejemplar = (
                Ejemplar.objects.select_for_update().select_related("libro").get(pk=ejemplar_id)
                if ejemplar_id else None
            )
            reserva = Reserva.objects.select_for_update().select_related("usuario", "libro").get(pk=pk)
            if reserva.estado != Reserva.Estado.DISPONIBLE or reserva.ejemplar_asignado_id != ejemplar_id:
                continue
            reserva.expirar()
            if ejemplar is not None:
                _liberar(ejemplar)
            notificar(
                reserva.usuario,
                "GENERAL",
                f"Tu reserva de «{reserva.libro}» expiró porque no se recogió a tiempo.",
            )
            total += 1
    return total


def enviar_recordatorios(hoy=None, dias_aviso=1):
    """CU-36. Avisa de préstamos ACTIVOS que vencen entre hoy y hoy + dias_aviso; una vez al día por préstamo."""
    hoy = hoy or timezone.localdate()
    total = 0
    prestamos = Prestamo.objects.filter(
        estado=Prestamo.Estado.ACTIVO,
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timedelta(days=dias_aviso),
    ).select_related("usuario", "ejemplar__libro")
    for prestamo in prestamos:
        marca = f"(préstamo {prestamo.pk})"
        ya_avisado = Notificacion.objects.filter(
            usuario=prestamo.usuario,
            tipo="VENCE_PRONTO",
            mensaje__contains=marca,
            fecha__date=hoy,
        ).exists()
        if ya_avisado:
            continue
        cuando = "hoy" if prestamo.fecha_vencimiento == hoy else f"el {prestamo.fecha_vencimiento:%d/%m/%Y}"
        notificar(
            prestamo.usuario,
            "VENCE_PRONTO",
            f"Tu préstamo de «{prestamo.ejemplar.libro}» vence {cuando}. Devuélvelo o renuévalo a tiempo {marca}.",
        )
        total += 1
    return total


class Command(BaseCommand):
    help = "Marca préstamos vencidos (CU-34), expira solicitudes y reservas (CU-35) y envía recordatorios (CU-36)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias-aviso",
            type=int,
            default=1,
            help="Días de anticipación para el recordatorio de vencimiento (por omisión, 1).",
        )

    def handle(self, *args, **opciones):
        vencidos = marcar_vencidos()
        solicitudes = expirar_solicitudes()
        reservas = expirar_reservas()
        recordatorios = enviar_recordatorios(dias_aviso=opciones["dias_aviso"])
        self.stdout.write(self.style.SUCCESS(
            f"Préstamos vencidos: {vencidos} · Solicitudes expiradas: {solicitudes} · "
            f"Reservas expiradas: {reservas} · Recordatorios enviados: {recordatorios}"
        ))
