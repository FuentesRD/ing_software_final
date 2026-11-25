from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from multas.models import Multa, Pago


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


@transaction.atomic
def registrar_devolucion(prestamo, recibido_por_usuario, fecha_devolucion=None):
    """CU-25: Marca el préstamo como devuelto y genera multa si hubo días de retraso."""
    from prestamos.models import Prestamo
    prestamo.marcar_devuelto(bibliotecario=recibido_por_usuario, fecha=fecha_devolucion)

    dias = prestamo.dias_retraso()
    multa = None
    if dias > 0:
        monto = prestamo.calcular_multa()
        multa = Multa.objects.create(
            prestamo=prestamo,
            usuario=prestamo.usuario,
            motivo=Multa.Motivo.RETRASO,
            dias_retraso=dias,
            monto=monto,
            estado=Multa.Estado.PENDIENTE,
            fecha_generacion=timezone.now(),
        )

    return multa


@transaction.atomic
def registrar_perdida_o_danio(prestamo, motivo, costo_reposicion, recibido_por_usuario=None):
    """CU-27: Registra pérdida o daño y genera la multa correspondiente."""
    from prestamos.models import Prestamo
    monto_decimal = Decimal(str(costo_reposicion))
    if monto_decimal <= Decimal("0.00"):
        raise ValidationError("El costo de reposición debe ser mayor a cero.")

    if motivo not in {Multa.Motivo.PERDIDA, Multa.Motivo.DANIO}:
        raise ValidationError("El motivo debe ser pérdida o daño.")

    if motivo == Multa.Motivo.PERDIDA and prestamo.estado in {
        Prestamo.Estado.ACTIVO,
        Prestamo.Estado.VENCIDO,
    }:
        prestamo.marcar_perdido()

    multa = Multa.objects.create(
        prestamo=prestamo,
        usuario=prestamo.usuario,
        motivo=motivo,
        dias_retraso=0,
        monto=monto_decimal,
        estado=Multa.Estado.PENDIENTE,
        fecha_generacion=timezone.now(),
    )

    return multa


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
