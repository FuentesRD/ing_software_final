"""Pruebas de los modelos de catalogo: reglas, contratos y restricciones."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from catalogo.models import Autor, Categoria, Editorial, Ejemplar, Libro, LibroAutor


class BaseCatalogoTestCase(TestCase):
    """Crea un libro con su categoría y editorial para reutilizar en las pruebas."""

    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre="Software")
        cls.editorial = Editorial.objects.create(nombre="Prentice Hall")
        cls.libro = Libro.objects.create(
            isbn="9780132350884",
            titulo="Clean Code",
            categoria=cls.categoria,
            editorial=cls.editorial,
        )


class EjemplarEsPrestableTests(BaseCatalogoTestCase):
    """RN-15: solo un ejemplar DISPONIBLE se puede prestar."""

    def test_solo_disponible_es_prestable(self):
        for estado in Ejemplar.Estado.values:
            with self.subTest(estado=estado):
                ejemplar = Ejemplar(
                    codigo_inventario=f"INV-{estado}",
                    libro=self.libro,
                    estado=estado,
                )
                esperado = estado == Ejemplar.Estado.DISPONIBLE
                self.assertEqual(ejemplar.es_prestable(), esperado)


class EjemplaresDisponiblesTests(BaseCatalogoTestCase):
    """Contrato con prestamos: devuelve un queryset solo con los DISPONIBLE."""

    def test_devuelve_queryset_solo_con_disponibles(self):
        disponible = Ejemplar.objects.create(
            codigo_inventario="INV-0001", libro=self.libro
        )
        Ejemplar.objects.create(
            codigo_inventario="INV-0002",
            libro=self.libro,
            estado=Ejemplar.Estado.PRESTADO,
        )
        Ejemplar.objects.create(
            codigo_inventario="INV-0003",
            libro=self.libro,
            estado=Ejemplar.Estado.EN_REPARACION,
        )

        disponibles = self.libro.ejemplares_disponibles()

        self.assertEqual(list(disponibles), [disponible])
        self.assertEqual(disponibles.count(), 1)

    def test_sin_ejemplares_devuelve_vacio(self):
        self.assertFalse(self.libro.ejemplares_disponibles().exists())


class EjemplarCambiarEstadoTests(BaseCatalogoTestCase):
    """Contrato con prestamos y multas: cambiar_estado valida y guarda."""

    def setUp(self):
        self.ejemplar = Ejemplar.objects.create(
            codigo_inventario="INV-0001", libro=self.libro
        )

    def test_cambia_y_guarda_el_estado(self):
        self.ejemplar.cambiar_estado(Ejemplar.Estado.RESERVADO)

        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, Ejemplar.Estado.RESERVADO)

    def test_rechaza_estado_inexistente(self):
        with self.assertRaises(ValidationError):
            self.ejemplar.cambiar_estado("ROTO")

        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, Ejemplar.Estado.DISPONIBLE)


class RestriccionesBaseDeDatosTests(BaseCatalogoTestCase):
    """Unicidad, CHECK y PROTECT definidos en el esquema."""

    def test_isbn_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Libro.objects.create(
                isbn="9780132350884",
                titulo="Otro título",
                categoria=self.categoria,
                editorial=self.editorial,
            )

    def test_codigo_inventario_unico(self):
        Ejemplar.objects.create(codigo_inventario="INV-0001", libro=self.libro)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Ejemplar.objects.create(codigo_inventario="INV-0001", libro=self.libro)

    def test_autor_no_se_repite_en_el_mismo_libro(self):
        autor = Autor.objects.create(nombre="Robert", apellidos="Martin")
        LibroAutor.objects.create(libro=self.libro, autor=autor, orden=1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LibroAutor.objects.create(libro=self.libro, autor=autor, orden=2)

    def test_check_estado_de_ejemplar(self):
        ejemplar = Ejemplar.objects.create(
            codigo_inventario="INV-0001", libro=self.libro
        )

        # update() se salta las validaciones de Django: lo detiene el CHECK de MySQL.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ejemplar.objects.filter(pk=ejemplar.pk).update(estado="ROTO")

    def test_no_se_borra_categoria_con_libros(self):
        with self.assertRaises(ProtectedError):
            self.categoria.delete()


class ValidacionIsbnTests(BaseCatalogoTestCase):
    """El ISBN acepta 10 o 13 caracteres sin guiones."""

    def test_isbn_validos(self):
        for isbn in ["9780132350884", "020161622X", "0201616220"]:
            with self.subTest(isbn=isbn):
                self.libro.isbn = isbn
                self.libro.full_clean()

    def test_isbn_invalidos(self):
        for isbn in ["978-0132350884", "12345", "97801323508845", "02016162XX"]:
            with self.subTest(isbn=isbn):
                self.libro.isbn = isbn
                with self.assertRaises(ValidationError):
                    self.libro.full_clean()
