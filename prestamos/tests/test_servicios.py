"""Servicios de prestamos: tiene_prestamos_vencidos (RN-08)."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo
from prestamos.services import tiene_prestamos_vencidos

from .utilidades import crear_ejemplar, crear_libro, crear_usuario


class TienePrestamosVencidosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.otro = crear_usuario("a2", "ESTUDIANTE")
        cls.ejemplar = crear_ejemplar(crear_libro(), "EJ-1")

    def crear_prestamo(self, estado, dias_para_vencer, usuario=None):
        return Prestamo.objects.create(
            usuario=usuario or self.estudiante,
            ejemplar=self.ejemplar,
            estado=estado,
            fecha_vencimiento=timezone.localdate() + timedelta(days=dias_para_vencer),
        )

    def test_sin_prestamos(self):
        self.assertFalse(tiene_prestamos_vencidos(self.estudiante))

    def test_prestamo_en_estado_vencido(self):
        self.crear_prestamo(Prestamo.Estado.VENCIDO, -3)
        self.assertTrue(tiene_prestamos_vencidos(self.estudiante))

    def test_activo_con_fecha_pasada_aunque_no_se_haya_marcado(self):
        self.crear_prestamo(Prestamo.Estado.ACTIVO, -1)
        self.assertTrue(tiene_prestamos_vencidos(self.estudiante))

    def test_activo_que_vence_hoy_o_despues_no_cuenta(self):
        self.crear_prestamo(Prestamo.Estado.ACTIVO, 0)
        self.crear_prestamo(Prestamo.Estado.ACTIVO, 5)
        self.assertFalse(tiene_prestamos_vencidos(self.estudiante))

    def test_devuelto_con_fecha_pasada_no_cuenta(self):
        self.crear_prestamo(Prestamo.Estado.DEVUELTO, -10)
        self.assertFalse(tiene_prestamos_vencidos(self.estudiante))

    def test_solo_cuenta_los_del_propio_usuario(self):
        self.crear_prestamo(Prestamo.Estado.VENCIDO, -3, usuario=self.otro)
        self.assertFalse(tiene_prestamos_vencidos(self.estudiante))
