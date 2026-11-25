"""Pruebas de búsqueda, detalle, gestión del acervo y sugerencias."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogo.models import (
    Autor,
    Categoria,
    Editorial,
    Ejemplar,
    Libro,
    LibroAutor,
    SugerenciaAdquisicion,
)
from cuentas.models import Departamento, Profesor


def crear_usuario(username, tipo):
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@escuela.mx",
        password="clave-de-prueba",
        tipo_usuario=tipo,
    )


class CatalogoBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lector = crear_usuario("lector", "ESTUDIANTE")
        cls.bibliotecario = crear_usuario("biblio", "BIBLIOTECARIO")

        software = Categoria.objects.create(nombre="Software")
        novela = Categoria.objects.create(nombre="Novela")
        cls.prentice = Editorial.objects.create(nombre="Prentice Hall")
        fce = Editorial.objects.create(nombre="FCE")
        martin = Autor.objects.create(nombre="Robert", apellidos="Martin")
        rulfo = Autor.objects.create(nombre="Juan", apellidos="Rulfo")

        cls.clean_code = Libro.objects.create(
            isbn="9780132350884",
            titulo="Clean Code",
            categoria=software,
            editorial=cls.prentice,
        )
        cls.pedro = Libro.objects.create(
            isbn="9786071605070",
            titulo="Pedro Páramo",
            categoria=novela,
            editorial=fce,
        )
        LibroAutor.objects.create(libro=cls.clean_code, autor=martin)
        LibroAutor.objects.create(libro=cls.pedro, autor=rulfo)
        Ejemplar.objects.create(codigo_inventario="E-1", libro=cls.clean_code)
        Ejemplar.objects.create(
            codigo_inventario="E-2",
            libro=cls.clean_code,
            estado=Ejemplar.Estado.PRESTADO,
        )
        Ejemplar.objects.create(
            codigo_inventario="E-3",
            libro=cls.pedro,
            estado=Ejemplar.Estado.PRESTADO,
        )

    def buscar(self, **parametros):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse("catalogo:buscar"), parametros)
        self.assertEqual(respuesta.status_code, 200)
        return list(respuesta.context["libros"])


class BusquedaTests(CatalogoBaseTestCase):
    """RF-02: búsqueda por cada criterio, con disponibilidad."""

    def test_por_titulo(self):
        self.assertEqual(self.buscar(q="clean", criterio="titulo"), [self.clean_code])

    def test_por_autor(self):
        self.assertEqual(self.buscar(q="rulfo", criterio="autor"), [self.pedro])

    def test_por_isbn(self):
        self.assertEqual(self.buscar(q="978-0132", criterio="isbn"), [self.clean_code])

    def test_por_categoria(self):
        categoria = self.pedro.categoria_id
        self.assertEqual(self.buscar(categoria=categoria), [self.pedro])

    def test_por_editorial(self):
        self.assertEqual(self.buscar(editorial=self.prentice.pk), [self.clean_code])

    def test_texto_libre_busca_en_todo(self):
        self.assertEqual(self.buscar(q="martin"), [self.clean_code])

    def test_muestra_disponibles(self):
        libros = {libro.titulo: libro for libro in self.buscar()}
        self.assertEqual(libros["Clean Code"].disponibles, 1)
        self.assertEqual(libros["Clean Code"].total_ejemplares, 2)
        self.assertEqual(libros["Pedro Páramo"].disponibles, 0)

    def test_solo_disponibles(self):
        self.assertEqual(self.buscar(solo_disponibles="on"), [self.clean_code])

    def test_lector_no_ve_libros_de_baja(self):
        Libro.objects.filter(pk=self.pedro.pk).update(activo=False)
        self.assertEqual(self.buscar(), [self.clean_code])

    def test_requiere_sesion(self):
        respuesta = self.client.get(reverse("catalogo:buscar"))
        self.assertEqual(respuesta.status_code, 302)


class DetalleTests(CatalogoBaseTestCase):
    def test_detalle_muestra_disponibles(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(
            reverse("catalogo:detalle", args=[self.clean_code.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["disponibles"], 1)


class GestionAcervoTests(CatalogoBaseTestCase):
    """CU-17 / CU-18: solo el bibliotecario gestiona el acervo."""

    def test_lector_no_puede_crear_libros(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse("catalogo:libro_crear"))
        self.assertEqual(respuesta.status_code, 403)

    def test_bibliotecario_crea_libro_con_autores(self):
        self.client.force_login(self.bibliotecario)
        autor = Autor.objects.get(apellidos="Martin")
        respuesta = self.client.post(
            reverse("catalogo:libro_crear"),
            {
                "isbn": "9780134494166",
                "titulo": "Clean Architecture",
                "autores": [autor.pk],
                "categoria": self.clean_code.categoria_id,
                "editorial": self.prentice.pk,
                "idioma": "Inglés",
                "costo_reposicion": "950.00",
            },
        )
        libro = Libro.objects.get(isbn="9780134494166")
        self.assertRedirects(respuesta, reverse("catalogo:detalle", args=[libro.pk]))
        self.assertEqual(list(libro.autores.all()), [autor])

    def test_baja_logica_no_borra(self):
        self.client.force_login(self.bibliotecario)
        libro = Libro.objects.create(
            isbn="9780000000002",
            titulo="Libro sin préstamos",
            categoria=self.clean_code.categoria,
            editorial=self.prentice,
        )
        ejemplar = Ejemplar.objects.create(codigo_inventario="E-9", libro=libro)

        self.client.post(reverse("catalogo:libro_baja", args=[libro.pk]))

        libro.refresh_from_db()
        ejemplar.refresh_from_db()
        self.assertFalse(libro.activo)
        self.assertEqual(ejemplar.estado, Ejemplar.Estado.BAJA)

    def test_no_se_da_de_baja_con_ejemplares_prestados(self):
        self.client.force_login(self.bibliotecario)
        self.client.post(reverse("catalogo:libro_baja", args=[self.clean_code.pk]))
        self.clean_code.refresh_from_db()
        self.assertTrue(self.clean_code.activo)

    def test_ejemplar_prestado_no_cambia_de_estado(self):
        self.client.force_login(self.bibliotecario)
        prestado = Ejemplar.objects.get(codigo_inventario="E-2")
        self.client.post(
            reverse("catalogo:ejemplar_editar", args=[prestado.pk]),
            {"codigo_inventario": "E-2", "estado": "DISPONIBLE"},
        )
        prestado.refresh_from_db()
        self.assertEqual(prestado.estado, Ejemplar.Estado.PRESTADO)


class SugerenciasTests(CatalogoBaseTestCase):
    """CU-16 / CU-33."""

    def setUp(self):
        self.usuario_profesor = crear_usuario("profe", "PROFESOR")
        departamento = Departamento.objects.create(nombre="Ingeniería")
        self.profesor = Profesor.objects.create(
            usuario=self.usuario_profesor,
            num_empleado="EMP-1",
            departamento=departamento,
        )

    def test_profesor_sugiere_libro(self):
        self.client.force_login(self.usuario_profesor)
        self.client.post(
            reverse("catalogo:sugerir"),
            {
                "titulo": "Two Scoops of Django",
                "autores": "Feldroy",
                "justificacion": "Para la materia.",
            },
        )
        sugerencia = SugerenciaAdquisicion.objects.get()
        self.assertEqual(sugerencia.profesor, self.profesor)
        self.assertEqual(sugerencia.estado, SugerenciaAdquisicion.Estado.PENDIENTE)

    def test_estudiante_no_puede_sugerir(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse("catalogo:sugerir"))
        self.assertEqual(respuesta.status_code, 403)

    def test_bibliotecario_responde(self):
        sugerencia = SugerenciaAdquisicion.objects.create(
            titulo="Libro X",
            autores="Autor X",
            justificacion="Motivo",
            profesor=self.profesor,
        )
        self.client.force_login(self.bibliotecario)
        self.client.post(
            reverse("catalogo:sugerencia_responder", args=[sugerencia.pk]),
            {"estado": "APROBADA", "respuesta": "Se compra."},
        )
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaAdquisicion.Estado.APROBADA)
        self.assertEqual(sugerencia.respuesta, "Se compra.")