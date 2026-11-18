from decimal import Decimal

from django.db.models import Sum

from multas.models import Multa


def tiene_multas_pendientes(usuario):
    return Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).exists()


def monto_adeudado(usuario):
    total = Multa.objects.filter(usuario=usuario, estado=Multa.Estado.PENDIENTE).aggregate(t=Sum("monto"))["t"]
    return total or Decimal("0.00")
