from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from multas.models import Multa, Pago
from notificaciones.services import notificar


def tiene_multas_pendientes(usuario):
    return Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).exists()


def monto_adeudado(usuario):
    multas = (
        Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE)
        .aggregate(t=Sum("monto"))["t"]
    )
    pagos = (
        Pago.objects.filter(
            multa__usuario=usuario,
            multa__estado=Multa.Estado.PENDIENTE,
        )
        .aggregate(t=Sum("monto"))["t"]
    )
    return max((multas or Decimal("0.00")) - (pagos or Decimal("0.00")), Decimal("0.00"))


@transaction.atomic
def registrar_pago(multa, monto, metodo, folio_recibo, registrado_por_usuario):
    if multa.estado != Multa.Estado.PENDIENTE:
        raise ValidationError("Solo se pueden registrar pagos en multas pendientes.")

    monto_decimal = Decimal(str(monto))
    if monto_decimal <= Decimal("0.00"):
        raise ValidationError("El monto del pago debe ser mayor a cero.")

    pagado_previo = multa.pagos.aggregate(t=Sum("monto"))["t"] or Decimal("0.00")
    saldo_restante = multa.monto - pagado_previo
    if monto_decimal > saldo_restante:
        raise ValidationError("El pago excede el saldo pendiente de la multa.")

    pago = Pago.objects.create(
        multa=multa,
        monto=monto_decimal,
        metodo=metodo,
        folio_recibo=folio_recibo,
        fecha_pago=timezone.now(),
        registrado_por=registrado_por_usuario,
    )

    if pagado_previo + monto_decimal >= multa.monto:
        multa.estado = Multa.Estado.PAGADA
        multa.save(update_fields=["estado"])

    return pago


# --- Devolución, pérdida y daño --------------------------------------------------------
# El estado del ejemplar se cambia solo con el contrato de catalogo, Ejemplar.cambiar_estado(),
# y la cola de reservas con el contrato de prestamos, asignar_siguiente_reserva() (RN-12).
# Orden de bloqueo, igual que en prestamos: préstamo → ejemplar → reserva (RNF-03).

_ESTADOS_EN_CURSO = ("ACTIVO", "VENCIDO")
_TEXTO_MOTIVO = {"RETRASO": "retraso", "DANIO": "daño", "PERDIDA": "pérdida"}


def _bloquear_prestamo_y_ejemplar(prestamo):
    from catalogo.models import Ejemplar
    from prestamos.models import Prestamo

    prestamo = Prestamo.objects.select_for_update().select_related("usuario").get(pk=prestamo.pk)
    ejemplar = Ejemplar.objects.select_for_update().select_related("libro").get(pk=prestamo.ejemplar_id)
    return prestamo, ejemplar


def _generar_multa_por_retraso(prestamo):
    """CU-26 / RN-07: multa por los días de retraso del préstamo ya devuelto, o None si no hubo retraso."""
    dias = prestamo.dias_retraso()
    if dias <= 0:
        return None
    multa = Multa.objects.create(
        prestamo=prestamo,
        usuario=prestamo.usuario,
        motivo=Multa.Motivo.RETRASO,
        dias_retraso=dias,
        monto=prestamo.calcular_multa(),
        estado=Multa.Estado.PENDIENTE,
        fecha_generacion=timezone.now(),
    )
    notificar(
        prestamo.usuario,
        "MULTA",
        f"Se generó una multa de ${multa.monto} por {dias} día(s) de retraso en el préstamo {prestamo.pk}.",
    )
    return multa


def _liberar_ejemplar_devuelto(ejemplar):
    """RN-12: el ejemplar devuelto se aparta para la primera reserva pendiente; si no hay, queda DISPONIBLE."""
    from catalogo.models import Ejemplar
    from prestamos.services import asignar_siguiente_reserva

    if asignar_siguiente_reserva(ejemplar) is None:
        ejemplar.cambiar_estado(Ejemplar.Estado.DISPONIBLE)


@transaction.atomic
def registrar_devolucion(prestamo, recibido_por_usuario, fecha_devolucion=None):
    """CU-25: marca el préstamo como devuelto, genera la multa por retraso (CU-26) y libera el ejemplar."""
    prestamo, ejemplar = _bloquear_prestamo_y_ejemplar(prestamo)
    prestamo.marcar_devuelto(bibliotecario=recibido_por_usuario, fecha=fecha_devolucion)
    multa = _generar_multa_por_retraso(prestamo)
    _liberar_ejemplar_devuelto(ejemplar)
    return multa


@transaction.atomic
def registrar_perdida_o_danio(prestamo, motivo, costo_reposicion, recibido_por_usuario=None):
    """CU-27 / RN-13: registra pérdida o daño y genera la multa por el costo de reposición.

    - Pérdida: el préstamo en curso pasa a PERDIDO y el ejemplar a PERDIDO.
    - Daño: si el préstamo sigue en curso se registra su devolución (con multa por retraso si aplica);
      el ejemplar pasa a EN_REPARACION y no se aparta para reservas (RN-15).
    """
    from catalogo.models import Ejemplar
    from prestamos.models import Prestamo

    try:
        monto_decimal = Decimal(str(costo_reposicion))
    except InvalidOperation:
        raise ValidationError("El costo de reposición no es válido.")
    if monto_decimal <= Decimal("0.00"):
        raise ValidationError("El costo de reposición debe ser mayor a cero.")
    if motivo not in {Multa.Motivo.PERDIDA, Multa.Motivo.DANIO}:
        raise ValidationError("El motivo debe ser pérdida o daño.")

    prestamo, ejemplar = _bloquear_prestamo_y_ejemplar(prestamo)

    if motivo == Multa.Motivo.PERDIDA:
        if prestamo.estado not in _ESTADOS_EN_CURSO:
            raise ValidationError("Solo se puede registrar la pérdida de un préstamo activo o vencido.")
        prestamo.marcar_perdido()
        ejemplar.cambiar_estado(Ejemplar.Estado.PERDIDO)
    else:
        if prestamo.estado in _ESTADOS_EN_CURSO:
            prestamo.marcar_devuelto(bibliotecario=recibido_por_usuario)
            _generar_multa_por_retraso(prestamo)
            ejemplar.cambiar_estado(Ejemplar.Estado.EN_REPARACION)
        elif prestamo.estado == Prestamo.Estado.DEVUELTO:
            # Daño detectado después de recibirlo: solo se retira si nadie lo tiene apartado.
            if ejemplar.estado == Ejemplar.Estado.DISPONIBLE:
                ejemplar.cambiar_estado(Ejemplar.Estado.EN_REPARACION)
        else:
            raise ValidationError("Solo se puede registrar daño de un préstamo activo, vencido o devuelto.")

    multa = Multa.objects.create(
        prestamo=prestamo,
        usuario=prestamo.usuario,
        motivo=motivo,
        dias_retraso=0,
        monto=monto_decimal,
        estado=Multa.Estado.PENDIENTE,
        fecha_generacion=timezone.now(),
    )
    notificar(
        prestamo.usuario,
        "MULTA",
        f"Se generó una multa de ${multa.monto} por {_TEXTO_MOTIVO[motivo]} "
        f"de «{ejemplar.libro}» (préstamo {prestamo.pk}).",
    )
    return multa


def saldo_de(multa):
    """Lo que falta pagar de una multa: monto menos pagos registrados."""
    pagado = multa.pagos.aggregate(t=Sum("monto"))["t"] or Decimal("0.00")
    return max(multa.monto - pagado, Decimal("0.00"))


@transaction.atomic
def condonar_multa(multa, justificacion, condonada_por_usuario):
    """CU-29: Condona una multa pendiente con justificación obligatoria."""
    if multa.estado != Multa.Estado.PENDIENTE:
        raise ValidationError("Solo se pueden condonar multas pendientes.")

    texto = (justificacion or "").strip()
    if not texto:
        raise ValidationError("La justificación de condonación es obligatoria.")

    multa.estado = Multa.Estado.CONDONADA
    multa.justificacion_condonacion = texto
    multa.condonada_por = condonada_por_usuario
    multa.save(update_fields=["estado", "justificacion_condonacion", "condonada_por"])

    return multa
