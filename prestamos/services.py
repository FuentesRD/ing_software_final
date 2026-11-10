"""Servicios de la app prestamos: reglas de negocio que usan varias apps.

Las otras apps se usan solo a través de los contratos de PLAN_DE_TRABAJO.md (sección 3).
"""

from django.db.models import Q
from django.utils import timezone

from .models import Prestamo


def tiene_prestamos_vencidos(usuario):
    """RN-08: ¿el usuario tiene algún préstamo vencido? (contrato C → C, D).

    Cuenta los préstamos en estado VENCIDO y también los ACTIVOS cuya fecha de vencimiento
    ya pasó, aunque el comando de vencimientos (CU-34) todavía no los haya marcado.
    """
    hoy = timezone.localdate()
    return Prestamo.objects.filter(
        Q(estado=Prestamo.Estado.VENCIDO)
        | Q(estado=Prestamo.Estado.ACTIVO, fecha_vencimiento__lt=hoy),
        usuario=usuario,
    ).exists()
