"""CU-11 reservar_libro, CU-12 cancelar_reserva y posicion_en_cola (RN-12, cola FIFO)."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo, Reserva, TransicionInvalida
from prestamos.services import (
    OperacionNoPermitida,
    UsuarioNoElegible,
    asignar_siguiente_reserva,
    cancelar_reserva,
    posicion_en_cola,
    reservar_libro,
)

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class BaseReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.libro = crear_libro()

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        # El único ejemplar del libro está prestado: no hay disponibles.
        self.ejemplar = crear_ejemplar(self.libro, "EJ-1", estado="PRESTADO")


class ReservarLibroTests(BaseReservaTests):
    def test_reserva_exitosa(self):
        reserva = reservar_libro(self.estudiante, self.libro)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        self.assertEqual(reserva.usuario, self.estudiante)
        self.assertEqual(posicion_en_cola(reserva), 1)
        self.notificar.assert_called_once()

    def test_con_ejemplares_disponibles_no_se_reserva(self):
        crear_ejemplar(self.libro, "EJ-2")
        with self.assertRaises(OperacionNoPermitida):
            reservar_libro(self.estudiante, self.libro)
        self.assertFalse(Reserva.objects.exists())

    def test_no_dos_reservas_activas_del_mismo_libro(self):
        reservar_libro(self.estudiante, self.libro)
        with self.assertRaises(OperacionNoPermitida):
            reservar_libro(self.estudiante, self.libro)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_despues_de_cancelar_puede_volver_a_reservar(self):
        primera = reservar_libro(self.estudiante, self.libro)
        cancelar_reserva(primera, self.estudiante)
        segunda = reservar_libro(self.estudiante, self.libro)
        self.assertEqual(segunda.estado, Reserva.Estado.PENDIENTE)

    def test_rn08_con_multas_no_se_reserva(self):
        with mock.patch("multas.services.tiene_multas_pendientes", return_value=True):
            with self.assertRaises(UsuarioNoElegible):
                reservar_libro(self.estudiante, self.libro)
        self.assertFalse(Reserva.objects.exists())

    def test_rn11_no_reserva_un_titulo_que_ya_tiene(self):
        Prestamo.objects.create(
            usuario=self.estudiante, ejemplar=self.ejemplar, estado=Prestamo.Estado.ACTIVO,
            fecha_vencimiento=timezone.localdate() + timedelta(days=3),
        )
        with self.assertRaises(UsuarioNoElegible):
            reservar_libro(self.estudiante, self.libro)


class PosicionEnColaTests(BaseReservaTests):
    def test_cola_fifo(self):
        primera = reservar_libro(crear_usuario("a2"), self.libro)
        segunda = reservar_libro(crear_usuario("a3"), self.libro)
        tercera = reservar_libro(crear_usuario("a4"), self.libro)
        self.assertEqual([posicion_en_cola(r) for r in (primera, segunda, tercera)], [1, 2, 3])

        cancelar_reserva(primera, primera.usuario)
        segunda.refresh_from_db()
        tercera.refresh_from_db()
        self.assertEqual(posicion_en_cola(segunda), 1)
        self.assertEqual(posicion_en_cola(tercera), 2)

    def test_reserva_no_pendiente_no_tiene_posicion(self):
        reserva = reservar_libro(self.estudiante, self.libro)
        cancelar_reserva(reserva, self.estudiante)
        reserva.refresh_from_db()
        self.assertIsNone(posicion_en_cola(reserva))


class CancelarReservaTests(BaseReservaTests):
    def test_cancelar_reserva_pendiente(self):
        reserva = reservar_libro(self.estudiante, self.libro)
        cancelar_reserva(reserva, self.estudiante)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertEqual(estado_de(self.ejemplar), "PRESTADO")

    def test_cancelar_disponible_pasa_el_ejemplar_al_siguiente(self):
        mia = reservar_libro(self.estudiante, self.libro)
        siguiente = reservar_libro(crear_usuario("a2"), self.libro)
        asignar_siguiente_reserva(self.ejemplar)  # se devolvió el ejemplar: me lo apartan a mí
        mia.refresh_from_db()

        cancelar_reserva(mia, self.estudiante)

        siguiente.refresh_from_db()
        self.assertEqual(siguiente.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(siguiente.ejemplar_asignado, self.ejemplar)
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_cancelar_disponible_sin_cola_deja_el_ejemplar_disponible(self):
        mia = reservar_libro(self.estudiante, self.libro)
        asignar_siguiente_reserva(self.ejemplar)
        cancelar_reserva(mia, self.estudiante)
        self.assertEqual(estado_de(self.ejemplar), "DISPONIBLE")

    def test_otro_usuario_no_puede_cancelar(self):
        reserva = reservar_libro(self.estudiante, self.libro)
        with self.assertRaises(OperacionNoPermitida):
            cancelar_reserva(reserva, crear_usuario("a2"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)

    def test_reserva_atendida_no_se_cancela(self):
        reserva = Reserva.objects.create(
            usuario=self.estudiante, libro=self.libro, estado=Reserva.Estado.ATENDIDA
        )
        with self.assertRaises(TransicionInvalida):
            cancelar_reserva(reserva, self.estudiante)
