"""prestamos/datos_prueba.py: cantidades, estados, reglas de la política e idempotencia."""

from django.db.models import Count
from django.test import TestCase
from django.utils import timezone

from catalogo.models import Ejemplar
from multas.models import Multa
from prestamos import datos_prueba
from prestamos.models import PoliticaPrestamo, Prestamo, Reserva

from .utilidades import crear_ejemplar, crear_libro, crear_usuario

ESPERADO = {
    "solicitudes": datos_prueba.SOLICITUDES,
    "activos": datos_prueba.ACTIVOS,
    "vencidos": datos_prueba.VENCIDOS,
    "devueltos": datos_prueba.DEVUELTOS,
    "reservas": datos_prueba.RESERVAS,
}


def crear_catalogo(libros, ejemplares_por_libro=1):
    for i in range(1, libros + 1):
        libro = crear_libro(isbn=f"978000000{i:04d}", titulo=f"Libro {i:02d}")
        for copia in range(1, ejemplares_por_libro + 1):
            crear_ejemplar(libro, f"DP-{i:03d}-{copia}")


def crear_lectores(estudiantes=10, profesores=2):
    for i in range(1, estudiantes + 1):
        crear_usuario(f"est{i:02d}", "ESTUDIANTE")
    for i in range(1, profesores + 1):
        crear_usuario(f"prof{i}", "PROFESOR")


class CargaCompletaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        crear_usuario("biblio1", "BIBLIOTECARIO")
        crear_lectores()
        crear_catalogo(40)
        cls.creados = datos_prueba.cargar()

    def contar(self, estado):
        return Prestamo.objects.filter(estado=estado).count()

    def test_devuelve_las_cantidades_creadas(self):
        self.assertEqual(self.creados, ESPERADO)

    def test_cantidades_por_estado_en_la_base(self):
        self.assertEqual(self.contar(Prestamo.Estado.SOLICITADO), datos_prueba.SOLICITUDES)
        self.assertEqual(self.contar(Prestamo.Estado.ACTIVO), datos_prueba.ACTIVOS)
        self.assertEqual(self.contar(Prestamo.Estado.VENCIDO), datos_prueba.VENCIDOS)
        self.assertEqual(self.contar(Prestamo.Estado.DEVUELTO), datos_prueba.DEVUELTOS)
        self.assertEqual(Prestamo.objects.count(), sum(ESPERADO.values()) - datos_prueba.RESERVAS)
        self.assertEqual(
            Reserva.objects.filter(estado=Reserva.Estado.PENDIENTE).count(), datos_prueba.RESERVAS
        )

    def test_estado_de_los_ejemplares(self):
        esperado = {
            Prestamo.Estado.SOLICITADO: Ejemplar.Estado.RESERVADO,
            Prestamo.Estado.ACTIVO: Ejemplar.Estado.PRESTADO,
            Prestamo.Estado.VENCIDO: Ejemplar.Estado.PRESTADO,
        }
        for prestamo in Prestamo.objects.exclude(estado=Prestamo.Estado.DEVUELTO):
            with self.subTest(prestamo=prestamo):
                self.assertEqual(prestamo.ejemplar.estado, esperado[prestamo.estado])
        # Un ejemplar devuelto queda libre, salvo que otro préstamo lo haya tomado después.
        for prestamo in Prestamo.objects.filter(estado=Prestamo.Estado.DEVUELTO):
            vigente = Prestamo.objects.filter(
                ejemplar=prestamo.ejemplar, estado__in=Prestamo.ESTADOS_VIGENTES
            ).exists()
            if not vigente:
                self.assertEqual(prestamo.ejemplar.estado, Ejemplar.Estado.DISPONIBLE)

    def test_vencidos_en_el_pasado_y_activos_sin_vencer(self):
        hoy = timezone.localdate()
        for prestamo in Prestamo.objects.filter(estado=Prestamo.Estado.VENCIDO):
            self.assertLess(prestamo.fecha_vencimiento, hoy)
            self.assertLess(prestamo.fecha_prestamo, timezone.now())
        for prestamo in Prestamo.objects.filter(estado=Prestamo.Estado.ACTIVO):
            self.assertGreaterEqual(prestamo.fecha_vencimiento, hoy)
            self.assertLessEqual(prestamo.fecha_prestamo, timezone.now())

    def test_devueltos_en_el_pasado_y_sin_retraso(self):
        ahora = timezone.now()
        for prestamo in Prestamo.objects.filter(estado=Prestamo.Estado.DEVUELTO):
            with self.subTest(prestamo=prestamo):
                self.assertLess(prestamo.fecha_devolucion, ahora)
                self.assertLess(prestamo.fecha_vencimiento, timezone.localdate())
                self.assertLess(prestamo.fecha_prestamo, prestamo.fecha_devolucion)
                self.assertEqual(prestamo.dias_retraso(), 0)
                self.assertIsNotNone(prestamo.recibido_por)
        self.assertFalse(Multa.objects.exists())

    def test_solicitudes_con_plazo_para_recoger_vigente(self):
        for prestamo in Prestamo.objects.filter(estado=Prestamo.Estado.SOLICITADO):
            self.assertGreater(prestamo.fecha_limite_recoger, timezone.now())

    def test_respeta_el_maximo_de_libros(self):
        vigentes = (
            Prestamo.objects.filter(estado__in=Prestamo.ESTADOS_VIGENTES)
            .values("usuario__tipo_usuario", "usuario")
            .annotate(n=Count("pk"))
        )
        for fila in vigentes:
            maximo = PoliticaPrestamo.objects.get(
                tipo_usuario=fila["usuario__tipo_usuario"]
            ).max_libros
            self.assertLessEqual(fila["n"], maximo)

    def test_sin_dos_prestamos_vigentes_del_mismo_libro(self):
        repetidos = (
            Prestamo.objects.filter(estado__in=Prestamo.ESTADOS_VIGENTES)
            .values("usuario", "ejemplar__libro")
            .annotate(n=Count("pk"))
            .filter(n__gt=1)
        )
        self.assertFalse(repetidos.exists())

    def test_reservas_sobre_libros_sin_ejemplares_disponibles(self):
        reservas = Reserva.objects.filter(estado=Reserva.Estado.PENDIENTE)
        for reserva in reservas:
            with self.subTest(reserva=reserva):
                self.assertFalse(reserva.libro.ejemplares_disponibles().exists())
                self.assertFalse(
                    Prestamo.objects.filter(
                        usuario=reserva.usuario,
                        ejemplar__libro=reserva.libro,
                        estado__in=Prestamo.ESTADOS_VIGENTES,
                    ).exists()
                )
        # Un libro tiene dos reservas en fila (RN-12).
        por_libro = reservas.values("libro").annotate(n=Count("pk"))
        self.assertEqual(max(fila["n"] for fila in por_libro), 2)

    def test_segunda_corrida_no_duplica(self):
        antes = (Prestamo.objects.count(), Reserva.objects.count())
        self.assertEqual(datos_prueba.cargar(), {nombre: 0 for nombre in ESPERADO})
        self.assertEqual((Prestamo.objects.count(), Reserva.objects.count()), antes)


class DatosInsuficientesTests(TestCase):
    """Sin datos suficientes no lanza excepción: avisa y devuelve ceros."""

    CEROS = {nombre: 0 for nombre in ESPERADO}

    def cargar_sin_datos(self, texto_aviso):
        with self.assertLogs("prestamos.datos_prueba", level="WARNING") as aviso:
            creados = datos_prueba.cargar()
        self.assertEqual(creados, self.CEROS)
        self.assertIn(texto_aviso, aviso.output[0])
        self.assertFalse(Prestamo.objects.exists())
        self.assertFalse(Reserva.objects.exists())

    def test_sin_bibliotecario(self):
        crear_lectores()
        crear_catalogo(40)
        self.cargar_sin_datos("biblio1")

    def test_pocos_lectores(self):
        crear_usuario("biblio1", "BIBLIOTECARIO")
        crear_lectores(estudiantes=3, profesores=1)
        crear_catalogo(40)
        self.cargar_sin_datos("lectores")

    def test_pocos_ejemplares(self):
        crear_usuario("biblio1", "BIBLIOTECARIO")
        crear_lectores()
        crear_catalogo(5)
        self.cargar_sin_datos("ejemplares")
