from decimal import Decimal

from django.db.models import Sum

from multas.models import Multa, Pago


def tiene_multas_pendientes(usuario):
    return Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).exists()


def monto_adeudado(usuario):
    multas = Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).aggregate(t=Sum("monto"))["t"]
    pagos = Pago.objects.filter(multa__usuario=usuario, multa__estado=Multa.Estado.PENDIENTE).aggregate(t=Sum("monto"))["t"]
    return max((multas or Decimal("0.00")) - (pagos or Decimal("0.00")), Decimal("0.00"))
