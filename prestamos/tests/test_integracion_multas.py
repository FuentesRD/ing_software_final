"""Integración con multas (paquete D), sin mocks: RN-08 y CU-06 excepción 4a.

Usa los servicios reales tiene_multas_pendientes() y monto_adeudado() contra la base de pruebas.
"""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from multas.models import Multa
from prestamos.models import Prestamo
from prestamos.services import UsuarioNoElegible, solicitar_prestamo

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


@mock.patch("prestamos.services.notificar")
class SolicitarConMultaRealTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.libro_anterior = crear_libro(isbn="9780000000010", titulo="Libro ya devuelto")
        cls.libro = crear_libro(isbn="9780000000011", titulo="Libro que quiere pedir")
        # Préstamo ya devuelto que originó las multas (Multa exige un préstamo).
        cls.prestamo_devuelto = Prestamo.objects.create(
            usuario=cls.estudiante,
            ejemplar=crear_ejemplar(cls.libro_anterior, "EJ-ANT"),
            estado=Prestamo.Estado.DEVUELTO,
            fecha_vencimiento=timezone.localdate() - timedelta(days=20),
        )

    def crear_multa(self, monto, estado=Multa.Estado.PENDIENTE):
        monto = Decimal(monto)
        return Multa.objects.create(
            prestamo=self.prestamo_devuelto,
            usuario=self.estudiante,
            motivo=Multa.Motivo.RETRASO,
            dias_retraso=int(monto // 10),
            monto=monto,
            estado=estado,
        )

    def test_rn08_multa_pendiente_rechaza_con_el_monto_adeudado(self, notificar):
        self.crear_multa("120.00")
        self.crear_multa("30.50")
        self.crear_multa("80.00", estado=Multa.Estado.PAGADA)  # no cuenta para el adeudo
        ejemplar = crear_ejemplar(self.libro, "EJ-1")

        with self.assertRaises(UsuarioNoElegible) as error:
            solicitar_prestamo(self.estudiante, self.libro)

        self.assertEqual(
            error.exception.motivos,
            ["Tienes multas pendientes de pago. Monto adeudado: $150.50."],
        )
        self.assertFalse(Prestamo.objects.filter(ejemplar=ejemplar).exists())
        self.assertEqual(estado_de(ejemplar), "DISPONIBLE")
        notificar.assert_not_called()

    def test_multas_pagadas_o_condonadas_no_impiden_solicitar(self, notificar):
        self.crear_multa("80.00", estado=Multa.Estado.PAGADA)
        self.crear_multa("40.00", estado=Multa.Estado.CONDONADA)
        crear_ejemplar(self.libro, "EJ-1")

        prestamo = solicitar_prestamo(self.estudiante, self.libro)

        self.assertEqual(prestamo.estado, Prestamo.Estado.SOLICITADO)
