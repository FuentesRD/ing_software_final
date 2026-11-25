"""RN-12 asignar_siguiente_reserva: cola FIFO por fecha_reserva y aviso al usuario."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Reserva
from prestamos.services import OperacionNoPermitida, asignar_siguiente_reserva

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


@mock.patch("prestamos.services.notificar")
class AsignarSiguienteReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.libro = crear_libro()
        cls.otro_libro = crear_libro(isbn="9780000000002", titulo="Otro libro")

    def setUp(self):
        self.ejemplar = crear_ejemplar(self.libro, "EJ-1", estado="PRESTADO")

    def reservar(self, username, horas_atras, libro=None, estado=Reserva.Estado.PENDIENTE):
        return Reserva.objects.create(
            usuario=crear_usuario(username),
            libro=libro or self.libro,
            estado=estado,
            fecha_reserva=timezone.now() - timedelta(hours=horas_atras),
        )

    def test_asigna_a_la_reserva_mas_antigua(self, notificar):
        reciente = self.reservar("a1", horas_atras=1)
        antigua = self.reservar("a2", horas_atras=5)

        asignada = asignar_siguiente_reserva(self.ejemplar)

        self.assertEqual(asignada, antigua)
        antigua.refresh_from_db()
        reciente.refresh_from_db()
        self.assertEqual(antigua.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(antigua.ejemplar_asignado, self.ejemplar)
        self.assertIsNotNone(antigua.fecha_expiracion)
        self.assertEqual(reciente.estado, Reserva.Estado.PENDIENTE)
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")
        notificar.assert_called_once()
        self.assertEqual(notificar.call_args.args[:2], (antigua.usuario, "RESERVA_DISPONIBLE"))

    def test_ignora_reservas_de_otro_libro_o_no_pendientes(self, notificar):
        self.reservar("a1", horas_atras=9, libro=self.otro_libro)
        self.reservar("a2", horas_atras=8, estado=Reserva.Estado.CANCELADA)
        self.reservar("a3", horas_atras=7, estado=Reserva.Estado.ATENDIDA)
        valida = self.reservar("a4", horas_atras=1)
        self.assertEqual(asignar_siguiente_reserva(self.ejemplar), valida)

    def test_sin_reservas_devuelve_none_y_no_toca_el_ejemplar(self, notificar):
        self.assertIsNone(asignar_siguiente_reserva(self.ejemplar))
        self.assertEqual(estado_de(self.ejemplar), "PRESTADO")
        notificar.assert_not_called()

    def test_ejemplar_danado_perdido_o_de_baja(self, notificar):
        reserva = self.reservar("a1", horas_atras=1)
        for estado in ["EN_REPARACION", "PERDIDO", "BAJA"]:
            with self.subTest(estado=estado):
                ejemplar = crear_ejemplar(self.libro, f"EJ-{estado}", estado=estado)
                with self.assertRaises(OperacionNoPermitida):
                    asignar_siguiente_reserva(ejemplar)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)

    def test_dos_devoluciones_atienden_la_cola_en_orden(self, notificar):
        primera = self.reservar("a1", horas_atras=3)
        segunda = self.reservar("a2", horas_atras=2)
        otro_ejemplar = crear_ejemplar(self.libro, "EJ-2", estado="PRESTADO")
        self.assertEqual(asignar_siguiente_reserva(self.ejemplar), primera)
        self.assertEqual(asignar_siguiente_reserva(otro_ejemplar), segunda)
