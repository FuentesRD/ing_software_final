from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from multas.models import Multa, Pago


def tiene_multas_pendientes(usuario):
    return Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).exists()


def monto_adeudado(usuario):
    multas = Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).aggregate(t=Sum("monto"))["t"]
    pagos = Pago.objects.filter(multa__usuario=usuario, multa__estado=Multa.Estado.PENDIENTE).aggregate(t=Sum("monto"))["t"]
    return max((multas or Decimal("0.00")) - (pagos or Decimal("0.00")), Decimal("0.00"))


@transaction.atomic
def registrar_pago(multa, monto, metodo, folio_recibo, registrado_por_usuario):
    if multa.estado != Multa.Estado.PENDIENTE:
        raise ValidationError("Solo se pueden registrar pagos en multas pendientes.")

    monto_decimal = Decimal(monto)
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