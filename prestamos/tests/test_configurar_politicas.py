"""CU-31 actualizar_politica: solo el bibliotecario, con los CHECK y validaciones del modelo."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from prestamos.models import PoliticaPrestamo, Prestamo
from prestamos.services import OperacionNoPermitida, actualizar_politica, prestar_en_mostrador

from .utilidades import crear_ejemplar, crear_libro, crear_usuario


class BasePoliticaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")

    def setUp(self):
        self.politica = PoliticaPrestamo.objects.get(tipo_usuario="ESTUDIANTE")

    def valores_en_la_base(self):
        return PoliticaPrestamo.objects.values().get(pk=self.politica.pk)


class ActualizacionExitosaTests(BasePoliticaTests):
    def test_guarda_los_cambios(self):
        antes = self.politica.actualizado_en
        politica = actualizar_politica(
            self.politica, self.bibliotecario,
            dias_prestamo=10, max_libros=4, max_renovaciones=0,
            multa_por_dia=Decimal("12.50"), multa_maxima=Decimal("250.00"), horas_para_recoger=24,
        )
        politica.refresh_from_db()
        self.assertEqual(
            (politica.dias_prestamo, politica.max_libros, politica.max_renovaciones,
             politica.multa_por_dia, politica.multa_maxima, politica.horas_para_recoger),
            (10, 4, 0, Decimal("12.50"), Decimal("250.00"), 24),
        )
        self.assertGreater(politica.actualizado_en, antes)

    def test_no_cambia_la_otra_politica(self):
        profesor_antes = PoliticaPrestamo.objects.values().get(tipo_usuario="PROFESOR")
        actualizar_politica(self.politica, self.bibliotecario, dias_prestamo=14)
        self.assertEqual(PoliticaPrestamo.objects.values().get(tipo_usuario="PROFESOR"), profesor_antes)

    @mock.patch("prestamos.services.notificar")
    def test_rn01_los_prestamos_nuevos_usan_los_dias_nuevos(self, _notificar):
        actualizar_politica(self.politica, self.bibliotecario, dias_prestamo=10)
        ejemplar = crear_ejemplar(crear_libro(), "EJ-1")
        prestamo = prestar_en_mostrador(crear_usuario("a1"), ejemplar, self.bibliotecario)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=10))

    def test_rn03_las_renovaciones_restantes_usan_la_politica_vigente(self):
        prestamo = Prestamo.objects.create(
            usuario=crear_usuario("a1"), ejemplar=crear_ejemplar(crear_libro(), "EJ-1"),
            estado=Prestamo.Estado.ACTIVO, fecha_vencimiento=timezone.localdate() + timedelta(days=3),
        )
        self.assertEqual(prestamo.renovaciones_restantes(), 1)
        actualizar_politica(self.politica, self.bibliotecario, max_renovaciones=3)
        self.assertEqual(prestamo.renovaciones_restantes(), 3)


class PermisosYCamposTests(BasePoliticaTests):
    def test_solo_un_bibliotecario(self):
        for tipo in ["ESTUDIANTE", "PROFESOR"]:
            with self.subTest(tipo=tipo):
                with self.assertRaises(OperacionNoPermitida):
                    actualizar_politica(self.politica, crear_usuario(f"x-{tipo}", tipo), dias_prestamo=99)
        self.assertEqual(self.valores_en_la_base()["dias_prestamo"], 7)

    def test_no_se_cambia_el_tipo_de_usuario(self):
        with self.assertRaises(OperacionNoPermitida):
            actualizar_politica(self.politica, self.bibliotecario, tipo_usuario="PROFESOR")

    def test_campo_desconocido(self):
        with self.assertRaises(OperacionNoPermitida):
            actualizar_politica(self.politica, self.bibliotecario, dias=10)

    def test_sin_cambios(self):
        with self.assertRaises(OperacionNoPermitida):
            actualizar_politica(self.politica, self.bibliotecario)


class ValidacionesTests(BasePoliticaTests):
    """Si un valor no es válido se lanza ValidationError y la base no cambia."""

    def assert_rechaza(self, campo_con_error, mensaje, **cambios):
        antes = self.valores_en_la_base()
        with self.assertRaises(ValidationError) as error:
            actualizar_politica(self.politica, self.bibliotecario, **cambios)
        self.assertIn(mensaje, error.exception.message_dict[campo_con_error])
        self.assertEqual(self.valores_en_la_base(), antes)

    def test_check_multa_negativa(self):
        self.assert_rechaza("__all__", "Las multas no pueden ser negativas.", multa_por_dia=Decimal("-1.00"))

    def test_minimo_1_en_dias_libros_y_horas(self):
        for campo in ["dias_prestamo", "max_libros", "horas_para_recoger"]:
            with self.subTest(campo=campo):
                self.assert_rechaza(campo, "Debe ser al menos 1.", **{campo: 0})

    def test_cero_renovaciones_si_se_permite(self):
        politica = actualizar_politica(self.politica, self.bibliotecario, max_renovaciones=0)
        self.assertEqual(politica.max_renovaciones, 0)

    def test_multa_maxima_menor_que_la_diaria(self):
        self.assert_rechaza(
            "multa_maxima", "No puede ser menor que la multa por día.", multa_maxima=Decimal("5.00")
        )

    def test_demasiados_decimales(self):
        antes = self.valores_en_la_base()
        with self.assertRaises(ValidationError) as error:
            actualizar_politica(self.politica, self.bibliotecario, multa_por_dia=Decimal("10.555"))
        self.assertIn("multa_por_dia", error.exception.message_dict)
        self.assertEqual(self.valores_en_la_base(), antes)

    def test_entero_negativo(self):
        antes = self.valores_en_la_base()
        with self.assertRaises(ValidationError) as error:
            actualizar_politica(self.politica, self.bibliotecario, max_renovaciones=-1)
        self.assertIn("max_renovaciones", error.exception.message_dict)
        self.assertEqual(self.valores_en_la_base(), antes)
