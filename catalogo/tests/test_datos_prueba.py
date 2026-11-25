"""El comando cargar_datos_prueba cumple los mínimos y no duplica datos."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from catalogo.models import Ejemplar, Libro, SugerenciaAdquisicion
from cuentas.models import Estudiante, Profesor, Usuario


class CargarDatosPruebaTests(TestCase):
    def cargar(self, *argumentos):
        call_command("cargar_datos_prueba", *argumentos, stdout=StringIO())

    def test_cumple_los_minimos_del_proyecto(self):
        self.cargar()

        self.assertGreaterEqual(Libro.objects.count(), 50)
        self.assertGreaterEqual(Ejemplar.objects.count(), 100)
        self.assertGreaterEqual(Estudiante.objects.count(), 20)
        self.assertGreaterEqual(Profesor.objects.count(), 5)
        bibliotecarios = Usuario.objects.filter(tipo_usuario="BIBLIOTECARIO")
        self.assertGreaterEqual(bibliotecarios.count(), 2)
        self.assertEqual(SugerenciaAdquisicion.objects.count(), 3)

    def test_correr_dos_veces_no_duplica(self):
        self.cargar()
        totales = (Libro.objects.count(), Ejemplar.objects.count())

        self.cargar()

        self.assertEqual((Libro.objects.count(), Ejemplar.objects.count()), totales)

    def test_carga_masiva(self):
        self.cargar("--libros", "30")
        self.assertEqual(
            Libro.objects.filter(titulo__startswith="Libro de carga ").count(), 30
        )