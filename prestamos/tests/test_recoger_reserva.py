"""recoger_reserva: una reserva DISPONIBLE se convierte en préstamo ACTIVO y queda ATENDIDA."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo, Reserva
from prestamos.services import (
    OperacionNoPermitida,
    UsuarioNoElegible,
    asignar_siguiente_reserva,
    recoger_reserva,
    reservar_libro,
)

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class RecogerReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.profesor = crear_usuario("p1", "PROFESOR")
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        cls.libro = crear_libro()

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.ejemplar = crear_ejemplar(self.libro, "EJ-1", estado="PRESTADO")

    def reserva_disponible(self, usuario):
        reserva = reservar_libro(usuario, self.libro)
        asignar_siguiente_reserva(self.ejemplar)  # se devolvió el ejemplar y se le apartó
        reserva.refresh_from_db()
        self.notificar.reset_mock()
        return reserva

    def test_recoger_estudiante(self):
        reserva = self.reserva_disponible(self.estudiante)

        prestamo = recoger_reserva(reserva, self.bibliotecario)

        prestamo.refresh_from_db()
        reserva.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(prestamo.usuario, self.estudiante)
        self.assertEqual(prestamo.ejemplar, self.ejemplar)
        self.assertEqual(prestamo.entregado_por, self.bibliotecario)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=7))
        self.assertEqual(reserva.estado, Reserva.Estado.ATENDIDA)
        self.assertEqual(estado_de(self.ejemplar), "PRESTADO")
        self.notificar.assert_called_once()

    def test_recoger_profesor_vence_en_30_dias(self):
        reserva = self.reserva_disponible(self.profesor)
        prestamo = recoger_reserva(reserva, self.bibliotecario)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=30))

    def test_plazo_para_recoger_vencido(self):
        reserva = self.reserva_disponible(self.estudiante)
        Reserva.objects.filter(pk=reserva.pk).update(fecha_expiracion=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(OperacionNoPermitida):
            recoger_reserva(reserva, self.bibliotecario)
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_reserva_pendiente_no_se_recoge(self):
        reserva = reservar_libro(self.estudiante, self.libro)
        with self.assertRaises(OperacionNoPermitida):
            recoger_reserva(reserva, self.bibliotecario)
        self.assertFalse(Prestamo.objects.exists())

    def test_solo_un_bibliotecario_registra(self):
        reserva = self.reserva_disponible(self.estudiante)
        with self.assertRaises(OperacionNoPermitida):
            recoger_reserva(reserva, self.estudiante)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.DISPONIBLE)

    def test_rn08_multa_antes_de_recoger_no_cambia_nada(self):
        reserva = self.reserva_disponible(self.estudiante)
        with mock.patch("multas.services.tiene_multas_pendientes", return_value=True):
            with self.assertRaises(UsuarioNoElegible):
                recoger_reserva(reserva, self.bibliotecario)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.DISPONIBLE)
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_no_se_recoge_dos_veces(self):
        reserva = self.reserva_disponible(self.estudiante)
        recoger_reserva(reserva, self.bibliotecario)
        with self.assertRaises(OperacionNoPermitida):
            recoger_reserva(reserva, self.bibliotecario)
        self.assertEqual(Prestamo.objects.count(), 1)
