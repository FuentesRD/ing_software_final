"""CU-06 solicitar_prestamo: RN-06, RN-15 y garantía mínima (si falla, no cambia nada)."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo
from prestamos.services import SinEjemplaresDisponibles, UsuarioNoElegible, solicitar_prestamo

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


@mock.patch("prestamos.services.notificar")
class SolicitarPrestamoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.libro = crear_libro()

    def test_solicitud_exitosa(self, notificar):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        antes = timezone.now()

        prestamo = solicitar_prestamo(self.estudiante, self.libro)

        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.SOLICITADO)
        self.assertEqual(prestamo.usuario, self.estudiante)
        self.assertEqual(prestamo.ejemplar, ejemplar)
        self.assertIsNone(prestamo.fecha_vencimiento)
        # RN-06: 48 horas para recoger.
        self.assertGreaterEqual(prestamo.fecha_limite_recoger, antes + timedelta(hours=48))
        self.assertLessEqual(prestamo.fecha_limite_recoger, timezone.now() + timedelta(hours=48))
        self.assertEqual(estado_de(ejemplar), "RESERVADO")
        notificar.assert_called_once()
        self.assertEqual(notificar.call_args.args[:2], (self.estudiante, "GENERAL"))
        self.assertIn("EJ-1", notificar.call_args.args[2])

    def test_rn15_no_toma_ejemplares_que_no_se_prestan(self, notificar):
        for i, estado in enumerate(["EN_REPARACION", "PERDIDO", "BAJA", "PRESTADO", "RESERVADO"]):
            crear_ejemplar(self.libro, f"EJ-{i}", estado=estado)
        with self.assertRaises(SinEjemplaresDisponibles):
            solicitar_prestamo(self.estudiante, self.libro)
        self.assertFalse(Prestamo.objects.exists())
        notificar.assert_not_called()

    def test_rn15_elige_el_ejemplar_disponible(self, notificar):
        crear_ejemplar(self.libro, "EJ-DAÑADO", estado="EN_REPARACION")
        disponible = crear_ejemplar(self.libro, "EJ-BUENO")
        prestamo = solicitar_prestamo(self.estudiante, self.libro)
        self.assertEqual(prestamo.ejemplar, disponible)

    def test_usuario_no_elegible_no_cambia_nada(self, notificar):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        with mock.patch("multas.services.tiene_multas_pendientes", return_value=True):
            with self.assertRaises(UsuarioNoElegible) as error:
                solicitar_prestamo(self.estudiante, self.libro)
        self.assertEqual(error.exception.motivos, ["Tienes multas pendientes de pago."])
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(estado_de(ejemplar), "DISPONIBLE")
        notificar.assert_not_called()

    def test_rn11_no_se_solicita_dos_veces_el_mismo_titulo(self, notificar):
        crear_ejemplar(self.libro, "EJ-1")
        segundo = crear_ejemplar(self.libro, "EJ-2")
        solicitar_prestamo(self.estudiante, self.libro)
        with self.assertRaises(UsuarioNoElegible):
            solicitar_prestamo(self.estudiante, self.libro)
        self.assertEqual(Prestamo.objects.count(), 1)
        self.assertEqual(estado_de(segundo), "DISPONIBLE")

    def test_si_falla_la_notificacion_se_revierte_todo(self, notificar):
        notificar.side_effect = RuntimeError("falló el aviso")
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        with self.assertRaises(RuntimeError):
            solicitar_prestamo(self.estudiante, self.libro)
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(estado_de(ejemplar), "DISPONIBLE")
