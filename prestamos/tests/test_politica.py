"""PoliticaPrestamo: valores iniciales (RN-01 a RN-06), PoliticaPrestamo.para() y restricciones CHECK."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from prestamos.models import PoliticaPrestamo

from .utilidades import crear_usuario


class PoliticasInicialesTests(TestCase):
    """La migración de datos carga las dos políticas predeterminadas."""

    def test_politica_de_estudiante(self):
        politica = PoliticaPrestamo.objects.get(tipo_usuario="ESTUDIANTE")
        self.assertEqual(politica.dias_prestamo, 7)        # RN-01
        self.assertEqual(politica.max_libros, 3)           # RN-02
        self.assertEqual(politica.max_renovaciones, 1)     # RN-03
        self.assertEqual(politica.multa_por_dia, Decimal("10.00"))   # RN-04
        self.assertEqual(politica.multa_maxima, Decimal("300.00"))   # RN-05
        self.assertEqual(politica.horas_para_recoger, 48)  # RN-06

    def test_politica_de_profesor(self):
        politica = PoliticaPrestamo.objects.get(tipo_usuario="PROFESOR")
        self.assertEqual(politica.dias_prestamo, 30)
        self.assertEqual(politica.max_libros, 10)
        self.assertEqual(politica.max_renovaciones, 2)
        self.assertEqual(politica.multa_por_dia, Decimal("10.00"))
        self.assertEqual(politica.multa_maxima, Decimal("300.00"))
        self.assertEqual(politica.horas_para_recoger, 48)

    def test_solo_hay_dos_politicas(self):
        self.assertEqual(PoliticaPrestamo.objects.count(), 2)


class ParaUsuarioTests(TestCase):
    def test_devuelve_la_politica_segun_el_tipo(self):
        estudiante = crear_usuario("a1", "ESTUDIANTE")
        profesor = crear_usuario("p1", "PROFESOR")
        self.assertEqual(PoliticaPrestamo.para(estudiante).tipo_usuario, "ESTUDIANTE")
        self.assertEqual(PoliticaPrestamo.para(profesor).tipo_usuario, "PROFESOR")

    def test_bibliotecario_no_tiene_politica(self):
        bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        with self.assertRaises(ValueError):
            PoliticaPrestamo.para(bibliotecario)


class RestriccionesTests(TestCase):
    def test_multa_negativa_la_rechaza_la_base(self):
        politica = PoliticaPrestamo.objects.get(tipo_usuario="ESTUDIANTE")
        politica.multa_por_dia = Decimal("-1.00")
        with self.assertRaises(IntegrityError), transaction.atomic():
            politica.save()

    def test_tipo_bibliotecario_lo_rechaza_la_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PoliticaPrestamo.objects.create(
                tipo_usuario="BIBLIOTECARIO", dias_prestamo=1, max_libros=1, max_renovaciones=0,
                multa_por_dia=Decimal("0"), multa_maxima=Decimal("0"), horas_para_recoger=1,
            )
