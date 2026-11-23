"""CU-10 renovar_prestamo: RN-03, RN-08, RN-09 y RN-10."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo, Reserva, TransicionInvalida
from prestamos.services import OperacionNoPermitida, UsuarioNoElegible, renovar_prestamo

from .utilidades import crear_ejemplar, crear_libro, crear_usuario


class BaseRenovarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.profesor = crear_usuario("p1", "PROFESOR")
        cls.libro = crear_libro()

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.hoy = timezone.localdate()

    def prestamo_activo(self, usuario=None, dias_para_vencer=2, codigo="EJ-1", libro=None, **campos):
        campos.setdefault("estado", Prestamo.Estado.ACTIVO)
        return Prestamo.objects.create(
            usuario=usuario or self.estudiante,
            ejemplar=crear_ejemplar(libro or self.libro, codigo, estado="PRESTADO"),
            fecha_vencimiento=self.hoy + timedelta(days=dias_para_vencer),
            **campos,
        )


class RenovacionExitosaTests(BaseRenovarTests):
    def test_rn10_estudiante_nueva_fecha_desde_hoy(self):
        prestamo = self.prestamo_activo(dias_para_vencer=2)
        renovar_prestamo(prestamo, self.estudiante)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.fecha_vencimiento, self.hoy + timedelta(days=7))
        self.assertEqual(prestamo.num_renovaciones, 1)
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.notificar.assert_called_once()

    def test_rn10_profesor_nueva_fecha_desde_hoy(self):
        prestamo = self.prestamo_activo(self.profesor, dias_para_vencer=10)
        renovar_prestamo(prestamo, self.profesor)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.fecha_vencimiento, self.hoy + timedelta(days=30))

    def test_vence_hoy_todavia_se_renueva(self):
        prestamo = self.prestamo_activo(dias_para_vencer=0)
        renovar_prestamo(prestamo, self.estudiante)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 1)

    def test_rn02_con_el_maximo_de_libros_si_renueva(self):
        prestamo = self.prestamo_activo()
        for i in range(2):
            otro = crear_libro(isbn=f"979000000000{i}", titulo=f"Otro {i}")
            self.prestamo_activo(codigo=f"OT-{i}", libro=otro)
        renovar_prestamo(prestamo, self.estudiante)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 1)


class RN03Tests(BaseRenovarTests):
    """RN-03: estudiante 1 renovación, profesor 2."""

    def test_estudiante_solo_una_vez(self):
        prestamo = self.prestamo_activo()
        renovar_prestamo(prestamo, self.estudiante)
        with self.assertRaises(UsuarioNoElegible) as error:
            renovar_prestamo(prestamo, self.estudiante)
        self.assertIn("Ya usaste todas las renovaciones de este préstamo.", error.exception.motivos)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 1)

    def test_profesor_dos_veces(self):
        prestamo = self.prestamo_activo(self.profesor)
        renovar_prestamo(prestamo, self.profesor)
        renovar_prestamo(prestamo, self.profesor)
        with self.assertRaises(UsuarioNoElegible):
            renovar_prestamo(prestamo, self.profesor)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 2)


class RN09Tests(BaseRenovarTests):
    """RN-09: no se renueva un préstamo vencido ni un título con reservas pendientes de otros."""

    def test_prestamo_en_estado_vencido(self):
        prestamo = self.prestamo_activo(dias_para_vencer=-3, estado=Prestamo.Estado.VENCIDO)
        with self.assertRaises(UsuarioNoElegible) as error:
            renovar_prestamo(prestamo, self.estudiante)
        self.assertEqual(error.exception.motivos, ["El préstamo está vencido: devuélvelo en la biblioteca."])

    def test_activo_con_fecha_pasada(self):
        prestamo = self.prestamo_activo(dias_para_vencer=-1)
        with self.assertRaises(UsuarioNoElegible) as error:
            renovar_prestamo(prestamo, self.estudiante)
        self.assertEqual(error.exception.motivos, ["El préstamo está vencido: devuélvelo en la biblioteca."])
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 0)

    def test_reserva_pendiente_de_otro_usuario(self):
        prestamo = self.prestamo_activo()
        Reserva.objects.create(usuario=crear_usuario("a2"), libro=self.libro)
        with self.assertRaises(UsuarioNoElegible) as error:
            renovar_prestamo(prestamo, self.estudiante)
        self.assertEqual(error.exception.motivos, ["Otro usuario reservó «Libro de prueba»; no se puede renovar."])

    def test_reservas_que_no_bloquean(self):
        prestamo = self.prestamo_activo()
        otro = crear_usuario("a2")
        for estado in [Reserva.Estado.CANCELADA, Reserva.Estado.ATENDIDA, Reserva.Estado.EXPIRADA]:
            Reserva.objects.create(usuario=otro, libro=self.libro, estado=estado)
        Reserva.objects.create(usuario=crear_usuario("a3"), libro=crear_libro(isbn="9790000000009"))
        renovar_prestamo(prestamo, self.estudiante)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 1)


class RN08Tests(BaseRenovarTests):
    def test_con_multas_pendientes_no_se_renueva(self):
        prestamo = self.prestamo_activo()
        with (
            mock.patch("multas.services.tiene_multas_pendientes", return_value=True),
            mock.patch("multas.services.monto_adeudado", return_value=Decimal("20")),
        ):
            with self.assertRaises(UsuarioNoElegible) as error:
                renovar_prestamo(prestamo, self.estudiante)
        self.assertEqual(
            error.exception.motivos, ["Tienes multas pendientes de pago. Monto adeudado: $20.00."]
        )

    def test_con_otro_prestamo_vencido_no_se_renueva(self):
        prestamo = self.prestamo_activo()
        otro = crear_libro(isbn="9790000000001", titulo="Otro")
        self.prestamo_activo(codigo="OT-1", libro=otro, dias_para_vencer=-2, estado=Prestamo.Estado.VENCIDO)
        with self.assertRaises(UsuarioNoElegible) as error:
            renovar_prestamo(prestamo, self.estudiante)
        self.assertEqual(error.exception.motivos, ["Tienes préstamos vencidos sin devolver."])


class OtrasValidacionesTests(BaseRenovarTests):
    def test_otro_usuario_no_puede_renovar(self):
        prestamo = self.prestamo_activo()
        with self.assertRaises(OperacionNoPermitida):
            renovar_prestamo(prestamo, self.profesor)

    def test_se_juntan_todos_los_motivos(self):
        prestamo = self.prestamo_activo(num_renovaciones=1)
        Reserva.objects.create(usuario=crear_usuario("a2"), libro=self.libro)
        with mock.patch("multas.services.tiene_multas_pendientes", return_value=True):
            with self.assertRaises(UsuarioNoElegible) as error:
                renovar_prestamo(prestamo, self.estudiante)
        self.assertEqual(len(error.exception.motivos), 3)

    def test_una_solicitud_no_se_renueva(self):
        prestamo = self.prestamo_activo(estado=Prestamo.Estado.SOLICITADO, fecha_limite_recoger=timezone.now())
        with self.assertRaises(UsuarioNoElegible):
            renovar_prestamo(prestamo, self.estudiante)

    def test_metodo_del_modelo_valida_el_estado(self):
        prestamo = self.prestamo_activo(estado=Prestamo.Estado.DEVUELTO)
        with self.assertRaises(TransicionInvalida):
            prestamo.renovar()
