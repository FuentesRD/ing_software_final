"""CU-30 gestionar reservas: listar, ver la cola de un libro y cancelar con motivo."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Reserva, TransicionInvalida
from prestamos.services import (
    MAX_LONGITUD_MOTIVO,
    OperacionNoPermitida,
    asignar_siguiente_reserva,
    cancelar_reserva_por_bibliotecario,
    cola_de_reservas,
    listar_reservas,
)

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class BaseGestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        cls.libro = crear_libro()
        cls.otro_libro = crear_libro(isbn="9780000000002", titulo="Otro libro")

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.ahora = timezone.now()

    def reservar(self, username, horas_atras, libro=None, estado=Reserva.Estado.PENDIENTE):
        return Reserva.objects.create(
            usuario=crear_usuario(username),
            libro=libro or self.libro,
            estado=estado,
            fecha_reserva=self.ahora - timedelta(hours=horas_atras),
        )


class ListarReservasTests(BaseGestionTests):
    def setUp(self):
        super().setUp()
        self.r1 = self.reservar("a1", 5)
        self.r2 = self.reservar("a2", 4, estado=Reserva.Estado.CANCELADA)
        self.r3 = self.reservar("a3", 3, libro=self.otro_libro)
        self.r4 = self.reservar("a4", 6, libro=self.otro_libro, estado=Reserva.Estado.ATENDIDA)

    def test_sin_filtros_todas_en_orden_de_llegada(self):
        self.assertEqual(list(listar_reservas()), [self.r4, self.r1, self.r2, self.r3])

    def test_por_libro(self):
        self.assertEqual(list(listar_reservas(libro=self.libro)), [self.r1, self.r2])

    def test_por_estado(self):
        self.assertEqual(list(listar_reservas(estado=Reserva.Estado.PENDIENTE)), [self.r1, self.r3])

    def test_por_libro_y_estado(self):
        self.assertEqual(
            list(listar_reservas(libro=self.otro_libro, estado=Reserva.Estado.ATENDIDA)), [self.r4]
        )

    def test_estado_desconocido(self):
        with self.assertRaises(ValueError):
            listar_reservas(estado="ACTIVA")

    def test_no_hace_una_consulta_por_fila(self):
        with self.assertNumQueries(1):
            for reserva in listar_reservas():
                str(reserva.usuario), str(reserva.libro), reserva.ejemplar_asignado


class ColaDeReservasTests(BaseGestionTests):
    def test_orden_fifo_solo_pendientes_del_libro(self):
        tercera = self.reservar("a1", 1)
        primera = self.reservar("a2", 9)
        segunda = self.reservar("a3", 5)
        self.reservar("a4", 20, estado=Reserva.Estado.CANCELADA)
        self.reservar("a5", 20, estado=Reserva.Estado.DISPONIBLE)
        self.reservar("a6", 30, libro=self.otro_libro)
        self.assertEqual(list(cola_de_reservas(self.libro)), [primera, segunda, tercera])

    def test_libro_sin_reservas(self):
        self.assertEqual(list(cola_de_reservas(self.libro)), [])


class CancelarPorBibliotecarioTests(BaseGestionTests):
    def test_cancelar_pendiente_avisa_con_el_motivo(self):
        reserva = self.reservar("a1", 2)
        cancelar_reserva_por_bibliotecario(reserva, self.bibliotecario, "  Libro retirado del acervo  ")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.notificar.assert_called_once()
        usuario, tipo, mensaje = self.notificar.call_args.args
        self.assertEqual((usuario, tipo), (reserva.usuario, "GENERAL"))
        self.assertIn("Motivo: Libro retirado del acervo", mensaje)

    def test_cancelar_disponible_pasa_el_ejemplar_al_siguiente(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1", estado="PRESTADO")
        primera = self.reservar("a1", 5)
        segunda = self.reservar("a2", 1)
        asignar_siguiente_reserva(ejemplar)
        primera.refresh_from_db()

        cancelar_reserva_por_bibliotecario(primera, self.bibliotecario, "No se presentó")

        segunda.refresh_from_db()
        self.assertEqual(segunda.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(segunda.ejemplar_asignado, ejemplar)
        self.assertEqual(estado_de(ejemplar), "RESERVADO")

    def test_cancelar_disponible_sin_cola_deja_el_ejemplar_disponible(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1", estado="PRESTADO")
        reserva = self.reservar("a1", 5)
        asignar_siguiente_reserva(ejemplar)
        cancelar_reserva_por_bibliotecario(reserva, self.bibliotecario, "No se presentó")
        self.assertEqual(estado_de(ejemplar), "DISPONIBLE")

    def test_motivo_obligatorio(self):
        reserva = self.reservar("a1", 2)
        for motivo in ["", "   ", None]:
            with self.subTest(motivo=motivo):
                with self.assertRaises(OperacionNoPermitida):
                    cancelar_reserva_por_bibliotecario(reserva, self.bibliotecario, motivo)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        self.notificar.assert_not_called()

    def test_motivo_demasiado_largo(self):
        reserva = self.reservar("a1", 2)
        with self.assertRaises(OperacionNoPermitida):
            cancelar_reserva_por_bibliotecario(reserva, self.bibliotecario, "x" * (MAX_LONGITUD_MOTIVO + 1))
        cancelar_reserva_por_bibliotecario(reserva, self.bibliotecario, "x" * MAX_LONGITUD_MOTIVO)

    def test_solo_un_bibliotecario(self):
        reserva = self.reservar("a1", 2)
        for tipo in ["ESTUDIANTE", "PROFESOR"]:
            with self.subTest(tipo=tipo):
                with self.assertRaises(OperacionNoPermitida):
                    cancelar_reserva_por_bibliotecario(reserva, crear_usuario(f"x-{tipo}", tipo), "motivo")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)

    def test_reserva_atendida_no_se_cancela(self):
        reserva = self.reservar("a1", 2, estado=Reserva.Estado.ATENDIDA)
        with self.assertRaises(TransicionInvalida):
            cancelar_reserva_por_bibliotecario(reserva, self.bibliotecario, "motivo")
        self.notificar.assert_not_called()
