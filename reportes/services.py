from decimal import Decimal

from django.db.models import Count, DecimalField, F, Sum
from django.utils import timezone

from multas.models import Multa, Pago
from prestamos.models import Prestamo


def filtrar_periodo(consulta, campo, fecha_inicio=None, fecha_fin=None):
    """Filtra fechas incluyendo ambos extremos del periodo."""
    if fecha_inicio:
        consulta = consulta.filter(
            **{f"{campo}__date__gte": fecha_inicio}
        )

    if fecha_fin:
        consulta = consulta.filter(
            **{f"{campo}__date__lte": fecha_fin}
        )

    return consulta


def prestamos_por_periodo(fecha_inicio=None, fecha_fin=None):
    """Préstamos entregados, según su fecha de entrega."""
    consulta = Prestamo.objects.filter(
        fecha_prestamo__isnull=False,
    ).select_related("usuario", "ejemplar__libro")

    return filtrar_periodo(
        consulta,
        "fecha_prestamo",
        fecha_inicio,
        fecha_fin,
    ).order_by("-fecha_prestamo", "-pk")


def libros_mas_solicitados(fecha_inicio=None, fecha_fin=None):
    """Cuenta solicitudes por título, incluyendo las canceladas."""
    consulta = filtrar_periodo(
        Prestamo.objects.all(),
        "fecha_solicitud",
        fecha_inicio,
        fecha_fin,
    )

    return (
        consulta.order_by()
        .values(
            "ejemplar__libro_id",
            "ejemplar__libro__titulo",
            "ejemplar__libro__isbn",
        )
        .annotate(total_solicitudes=Count("pk"))
        .order_by(
            "-total_solicitudes",
            "ejemplar__libro__titulo",
            "ejemplar__libro_id",
        )
    )


def prestamos_vencidos(fecha_inicio=None, fecha_fin=None):
    """Préstamos sin devolver cuya fecha de vencimiento ya pasó."""
    consulta = Prestamo.objects.filter(
        estado__in=["ACTIVO", "VENCIDO"],
        fecha_devolucion__isnull=True,
        fecha_vencimiento__lt=timezone.localdate(),
    ).select_related("usuario", "ejemplar__libro")

    if fecha_inicio:
        consulta = consulta.filter(
            fecha_vencimiento__gte=fecha_inicio,
        )

    if fecha_fin:
        consulta = consulta.filter(
            fecha_vencimiento__lte=fecha_fin,
        )

    return consulta.order_by("fecha_vencimiento", "pk")


def multas_cobradas(fecha_inicio=None, fecha_fin=None):
    """Pagos recibidos, incluidos los abonos parciales."""
    consulta = Pago.objects.select_related(
        "multa__usuario",
        "multa__prestamo__ejemplar__libro",
        "registrado_por",
    )

    return filtrar_periodo(
        consulta,
        "fecha_pago",
        fecha_inicio,
        fecha_fin,
    ).order_by("-fecha_pago", "-pk")


def multas_pendientes(fecha_inicio=None, fecha_fin=None):
    """Multas pendientes con su saldo actual después de los abonos."""
    consulta = Multa.objects.filter(
        estado="PENDIENTE",
    ).select_related(
        "usuario",
        "prestamo__ejemplar__libro",
    )

    consulta = filtrar_periodo(
        consulta,
        "fecha_generacion",
        fecha_inicio,
        fecha_fin,
    )

    return (
        consulta.annotate(
            total_pagado=Sum(
                "pagos__monto",
                default=Decimal("0.00"),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2,
                ),
            ),
        )
        .annotate(saldo_pendiente=F("monto") - F("total_pagado"))
        .filter(saldo_pendiente__gt=0)
        .order_by("fecha_generacion", "pk")
    )