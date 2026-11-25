"""CU-08 cancelar_solicitud: préstamo CANCELADO y ejemplar liberado (a la cola de reservas o DISPONIBLE)."""

from unittest import mock

from django.test import TestCase

from prestamos.models import Prestamo, Reserva, TransicionInvalida
from prestamos.services import (
    OperacionNoPermitida,
    cancelar_solicitud,
    entregar_prestamo,
    solicitar_prestamo,
)

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class CancelarSolicitudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        cls.libro = crear_libro()

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.ejemplar = crear_ejemplar(self.libro, "EJ-1")
        self.solicitud = solicitar_prestamo(self.estudiante, self.libro)

    def test_cancelar_libera_el_ejemplar(self):
        cancelar_solicitud(self.solicitud, self.estudiante)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Prestamo.Estado.CANCELADO)
        self.assertEqual(estado_de(self.ejemplar), "DISPONIBLE")

    def test_rn12_el_ejemplar_pasa_a_la_siguiente_reserva(self):
        reserva = Reserva.objects.create(usuario=crear_usuario("a2"), libro=self.libro)
        cancelar_solicitud(self.solicitud, self.estudiante)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(reserva.ejemplar_asignado, self.ejemplar)
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_otro_usuario_no_puede_cancelar(self):
        with self.assertRaises(OperacionNoPermitida):
            cancelar_solicitud(self.solicitud, crear_usuario("a2"))
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Prestamo.Estado.SOLICITADO)
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_un_prestamo_entregado_no_se_cancela(self):
        entregar_prestamo(self.solicitud, self.bibliotecario)
        with self.assertRaises(TransicionInvalida):
            cancelar_solicitud(self.solicitud, self.estudiante)
        self.assertEqual(estado_de(self.ejemplar), "PRESTADO")
