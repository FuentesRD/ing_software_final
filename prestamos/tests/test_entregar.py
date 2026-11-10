"""CU-23 entregar_prestamo y CU-24 prestar_en_mostrador: RN-01, RN-02, RN-08 y RN-15."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo, TransicionInvalida
from prestamos.services import (
    OperacionNoPermitida,
    SinEjemplaresDisponibles,
    UsuarioNoElegible,
    entregar_prestamo,
    prestar_en_mostrador,
    solicitar_prestamo,
)

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class BaseEntregaTests(TestCase):
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


class EntregarPrestamoTests(BaseEntregaTests):
    """CU-23: atender una solicitud en línea."""

    def setUp(self):
        super().setUp()
        self.ejemplar = crear_ejemplar(self.libro, "EJ-1")
        self.solicitud = solicitar_prestamo(self.estudiante, self.libro)
        self.notificar.reset_mock()

    def test_entrega_exitosa(self):
        prestamo = entregar_prestamo(self.solicitud, self.bibliotecario)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(prestamo.entregado_por, self.bibliotecario)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=7))  # RN-01
        self.assertEqual(estado_de(self.ejemplar), "PRESTADO")
        self.notificar.assert_called_once()

    def test_solo_un_bibliotecario_entrega(self):
        with self.assertRaises(OperacionNoPermitida):
            entregar_prestamo(self.solicitud, self.profesor)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Prestamo.Estado.SOLICITADO)

    def test_plazo_para_recoger_vencido(self):
        Prestamo.objects.filter(pk=self.solicitud.pk).update(
            fecha_limite_recoger=timezone.now() - timedelta(minutes=1)
        )
        with self.assertRaises(OperacionNoPermitida):
            entregar_prestamo(self.solicitud, self.bibliotecario)
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_rn08_multa_generada_antes_de_recoger(self):
        with mock.patch("multas.services.tiene_multas_pendientes", return_value=True):
            with self.assertRaises(UsuarioNoElegible):
                entregar_prestamo(self.solicitud, self.bibliotecario)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Prestamo.Estado.SOLICITADO)
        self.assertEqual(estado_de(self.ejemplar), "RESERVADO")

    def test_la_solicitud_no_cuenta_contra_si_misma(self):
        # El estudiante tiene 2 préstamos más: con la solicitud llega a 3 (su máximo) y aun así se entrega.
        for i in range(2):
            otro = crear_libro(isbn=f"979000000000{i}", titulo=f"Otro {i}")
            Prestamo.objects.create(
                usuario=self.estudiante, ejemplar=crear_ejemplar(otro, f"OT-{i}"),
                estado=Prestamo.Estado.ACTIVO, fecha_vencimiento=timezone.localdate() + timedelta(days=3),
            )
        prestamo = entregar_prestamo(self.solicitud, self.bibliotecario)
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)

    def test_no_se_entrega_dos_veces(self):
        entregar_prestamo(self.solicitud, self.bibliotecario)
        with self.assertRaises(TransicionInvalida):
            entregar_prestamo(self.solicitud, self.bibliotecario)


class PrestarEnMostradorTests(BaseEntregaTests):
    """CU-24: préstamo directo en mostrador."""

    def test_estudiante_vence_en_7_dias(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        prestamo = prestar_en_mostrador(self.estudiante, ejemplar, self.bibliotecario)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=7))
        self.assertIsNone(prestamo.fecha_limite_recoger)
        self.assertEqual(estado_de(ejemplar), "PRESTADO")
        self.notificar.assert_called_once()

    def test_profesor_vence_en_30_dias(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        prestamo = prestar_en_mostrador(self.profesor, ejemplar, self.bibliotecario)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=30))

    def test_rn15_ejemplar_que_no_se_presta(self):
        for estado in ["EN_REPARACION", "PERDIDO", "BAJA", "PRESTADO", "RESERVADO"]:
            with self.subTest(estado=estado):
                ejemplar = crear_ejemplar(self.libro, f"EJ-{estado}", estado=estado)
                with self.assertRaises(SinEjemplaresDisponibles):
                    prestar_en_mostrador(self.estudiante, ejemplar, self.bibliotecario)
                self.assertEqual(estado_de(ejemplar), estado)
        self.assertFalse(Prestamo.objects.exists())

    def test_rn02_estudiante_en_el_maximo(self):
        for i in range(3):
            otro = crear_libro(isbn=f"979000000000{i}", titulo=f"Otro {i}")
            prestar_en_mostrador(self.estudiante, crear_ejemplar(otro, f"OT-{i}"), self.bibliotecario)
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        with self.assertRaises(UsuarioNoElegible):
            prestar_en_mostrador(self.estudiante, ejemplar, self.bibliotecario)
        self.assertEqual(estado_de(ejemplar), "DISPONIBLE")

    def test_rn11_mismo_titulo(self):
        prestar_en_mostrador(self.estudiante, crear_ejemplar(self.libro, "EJ-1"), self.bibliotecario)
        with self.assertRaises(UsuarioNoElegible):
            prestar_en_mostrador(self.estudiante, crear_ejemplar(self.libro, "EJ-2"), self.bibliotecario)

    def test_solo_un_bibliotecario_presta(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        with self.assertRaises(OperacionNoPermitida):
            prestar_en_mostrador(self.estudiante, ejemplar, self.estudiante)
        self.assertFalse(Prestamo.objects.exists())
