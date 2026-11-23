"""Reserva: cola FIFO (RN-12), plazo para recoger (RN-06) y transiciones de estado."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from prestamos.models import Reserva, TransicionInvalida

from .utilidades import crear_ejemplar, crear_libro, crear_usuario


class ReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.libro = crear_libro()
        cls.ejemplar = crear_ejemplar(cls.libro, "EJ-1")

    def crear_reserva(self, **campos):
        campos.setdefault("usuario", self.estudiante)
        return Reserva.objects.create(libro=self.libro, **campos)

    def test_nace_pendiente(self):
        self.assertEqual(self.crear_reserva().estado, Reserva.Estado.PENDIENTE)

    def test_cola_fifo_por_fecha_de_reserva(self):
        ahora = timezone.now()
        tercera = self.crear_reserva(usuario=crear_usuario("a3"), fecha_reserva=ahora)
        primera = self.crear_reserva(usuario=crear_usuario("a4"), fecha_reserva=ahora - timedelta(hours=2))
        segunda = self.crear_reserva(usuario=crear_usuario("a5"), fecha_reserva=ahora - timedelta(hours=1))
        self.assertEqual(list(Reserva.objects.filter(libro=self.libro)), [primera, segunda, tercera])

    def test_marcar_disponible_aparta_el_ejemplar_por_48_horas(self):
        reserva = self.crear_reserva()
        antes = timezone.now()
        reserva.marcar_disponible(self.ejemplar)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(reserva.ejemplar_asignado, self.ejemplar)
        self.assertGreaterEqual(reserva.fecha_expiracion, antes + timedelta(hours=48))
        self.assertLessEqual(reserva.fecha_expiracion, timezone.now() + timedelta(hours=48))

    def test_transiciones_validas(self):
        casos = [
            (Reserva.Estado.DISPONIBLE, "atender", Reserva.Estado.ATENDIDA),
            (Reserva.Estado.PENDIENTE, "cancelar", Reserva.Estado.CANCELADA),
            (Reserva.Estado.DISPONIBLE, "cancelar", Reserva.Estado.CANCELADA),
            (Reserva.Estado.DISPONIBLE, "expirar", Reserva.Estado.EXPIRADA),
        ]
        for origen, metodo, destino in casos:
            with self.subTest(origen=origen, metodo=metodo):
                reserva = self.crear_reserva(estado=origen)
                getattr(reserva, metodo)()
                reserva.refresh_from_db()
                self.assertEqual(reserva.estado, destino)

    def test_transiciones_invalidas(self):
        casos = [
            (Reserva.Estado.PENDIENTE, "atender"),
            (Reserva.Estado.PENDIENTE, "expirar"),
            (Reserva.Estado.ATENDIDA, "cancelar"),
            (Reserva.Estado.EXPIRADA, "atender"),
        ]
        for origen, metodo in casos:
            with self.subTest(origen=origen, metodo=metodo):
                reserva = self.crear_reserva(estado=origen)
                with self.assertRaises(TransicionInvalida):
                    getattr(reserva, metodo)()

    def test_no_se_aparta_dos_veces(self):
        reserva = self.crear_reserva(estado=Reserva.Estado.DISPONIBLE)
        with self.assertRaises(TransicionInvalida):
            reserva.marcar_disponible(self.ejemplar)

    def test_estado_invalido_lo_rechaza_la_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_reserva(estado="ACTIVA")
