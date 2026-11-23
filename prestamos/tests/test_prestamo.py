"""Prestamo: transiciones de estado, RN-01, RN-03 y cálculo de multa (RN-07)."""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo, TransicionInvalida

from .utilidades import crear_ejemplar, crear_libro, crear_usuario


class BasePrestamoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.profesor = crear_usuario("p1", "PROFESOR")
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        cls.libro = crear_libro()
        cls.ejemplar = crear_ejemplar(cls.libro, "EJ-1")

    def crear_prestamo(self, usuario=None, **campos):
        return Prestamo.objects.create(usuario=usuario or self.estudiante, ejemplar=self.ejemplar, **campos)


class ValoresPorDefectoTests(BasePrestamoTests):
    def test_nace_solicitado_y_sin_renovaciones(self):
        prestamo = self.crear_prestamo()
        self.assertEqual(prestamo.estado, Prestamo.Estado.SOLICITADO)
        self.assertEqual(prestamo.num_renovaciones, 0)
        self.assertIsNotNone(prestamo.fecha_solicitud)

    def test_estado_invalido_lo_rechaza_la_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_prestamo(estado="PRESTADO")


class EntregarTests(BasePrestamoTests):
    """CU-23 y RN-01: la fecha de vencimiento depende del tipo de usuario."""

    def test_estudiante_vence_en_7_dias(self):
        prestamo = self.crear_prestamo(self.estudiante)
        prestamo.entregar(self.bibliotecario)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=7))
        self.assertEqual(prestamo.entregado_por, self.bibliotecario)
        self.assertIsNotNone(prestamo.fecha_prestamo)

    def test_profesor_vence_en_30_dias(self):
        prestamo = self.crear_prestamo(self.profesor)
        prestamo.entregar(self.bibliotecario)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=30))

    def test_no_se_entrega_un_prestamo_activo(self):
        prestamo = self.crear_prestamo(estado=Prestamo.Estado.ACTIVO)
        with self.assertRaises(TransicionInvalida):
            prestamo.entregar(self.bibliotecario)


class TransicionesTests(BasePrestamoTests):
    """Diagrama de estados 10.3."""

    def test_transiciones_validas(self):
        casos = [
            (Prestamo.Estado.ACTIVO, "marcar_vencido", Prestamo.Estado.VENCIDO),
            (Prestamo.Estado.ACTIVO, "marcar_perdido", Prestamo.Estado.PERDIDO),
            (Prestamo.Estado.VENCIDO, "marcar_perdido", Prestamo.Estado.PERDIDO),
            (Prestamo.Estado.SOLICITADO, "cancelar", Prestamo.Estado.CANCELADO),
            (Prestamo.Estado.SOLICITADO, "expirar", Prestamo.Estado.EXPIRADO),
        ]
        for origen, metodo, destino in casos:
            with self.subTest(origen=origen, metodo=metodo):
                prestamo = self.crear_prestamo(estado=origen)
                getattr(prestamo, metodo)()
                prestamo.refresh_from_db()
                self.assertEqual(prestamo.estado, destino)

    def test_devolver_activo_o_vencido(self):
        for origen in (Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO):
            with self.subTest(origen=origen):
                prestamo = self.crear_prestamo(estado=origen)
                prestamo.marcar_devuelto(self.bibliotecario)
                prestamo.refresh_from_db()
                self.assertEqual(prestamo.estado, Prestamo.Estado.DEVUELTO)
                self.assertEqual(prestamo.recibido_por, self.bibliotecario)
                self.assertIsNotNone(prestamo.fecha_devolucion)

    def test_transiciones_invalidas(self):
        casos = [
            (Prestamo.Estado.SOLICITADO, "marcar_vencido"),
            (Prestamo.Estado.SOLICITADO, "marcar_perdido"),
            (Prestamo.Estado.ACTIVO, "cancelar"),
            (Prestamo.Estado.ACTIVO, "expirar"),
            (Prestamo.Estado.DEVUELTO, "marcar_vencido"),
            (Prestamo.Estado.CANCELADO, "expirar"),
        ]
        for origen, metodo in casos:
            with self.subTest(origen=origen, metodo=metodo):
                prestamo = self.crear_prestamo(estado=origen)
                with self.assertRaises(TransicionInvalida):
                    getattr(prestamo, metodo)()
                prestamo.refresh_from_db()
                self.assertEqual(prestamo.estado, origen)

    def test_no_se_devuelve_un_prestamo_solicitado(self):
        prestamo = self.crear_prestamo()
        with self.assertRaises(TransicionInvalida):
            prestamo.marcar_devuelto(self.bibliotecario)


class RenovacionesRestantesTests(BasePrestamoTests):
    """RN-03: renovaciones permitidas por tipo de usuario."""

    def test_estudiante(self):
        self.assertEqual(self.crear_prestamo(self.estudiante).renovaciones_restantes(), 1)
        self.assertEqual(self.crear_prestamo(self.estudiante, num_renovaciones=1).renovaciones_restantes(), 0)

    def test_profesor(self):
        self.assertEqual(self.crear_prestamo(self.profesor).renovaciones_restantes(), 2)
        self.assertEqual(self.crear_prestamo(self.profesor, num_renovaciones=1).renovaciones_restantes(), 1)
        self.assertEqual(self.crear_prestamo(self.profesor, num_renovaciones=2).renovaciones_restantes(), 0)


class MultaPorRetrasoTests(BasePrestamoTests):
    """RN-07 con casos límite: 0 días, 1 día, varios días y tope máximo."""

    def prestamo_vencido_el(self, fecha_vencimiento):
        return self.crear_prestamo(estado=Prestamo.Estado.ACTIVO, fecha_vencimiento=fecha_vencimiento)

    def test_dias_retraso(self):
        vence = timezone.localdate()
        prestamo = self.prestamo_vencido_el(vence)
        self.assertEqual(prestamo.dias_retraso(vence - timedelta(days=3)), 0)  # devuelto antes
        self.assertEqual(prestamo.dias_retraso(vence), 0)
        self.assertEqual(prestamo.dias_retraso(vence + timedelta(days=1)), 1)
        self.assertEqual(prestamo.dias_retraso(vence + timedelta(days=5)), 5)

    def test_sin_fecha_de_vencimiento_no_hay_retraso(self):
        self.assertEqual(self.crear_prestamo().dias_retraso(), 0)

    def test_monto_de_la_multa(self):
        hoy = timezone.localdate()
        casos = [(0, Decimal("0.00")), (1, Decimal("10.00")), (5, Decimal("50.00")),
                 (30, Decimal("300.00")), (45, Decimal("300.00"))]
        for dias, esperado in casos:
            with self.subTest(dias=dias):
                prestamo = self.prestamo_vencido_el(hoy - timedelta(days=dias))
                self.assertEqual(prestamo.calcular_multa(), esperado)

    def test_usa_la_fecha_de_devolucion_si_ya_se_devolvio(self):
        hoy = timezone.localdate()
        prestamo = self.prestamo_vencido_el(hoy - timedelta(days=10))
        prestamo.marcar_devuelto(self.bibliotecario, fecha=timezone.now() - timedelta(days=8))
        self.assertEqual(prestamo.dias_retraso(), 2)
        self.assertEqual(prestamo.calcular_multa(), Decimal("20.00"))
