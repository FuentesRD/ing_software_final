"""CU-07 verificar_elegibilidad: cuenta, RN-02, RN-08 y RN-11."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from prestamos.models import Prestamo
from prestamos.services import verificar_elegibilidad

from .utilidades import crear_ejemplar, crear_libro, crear_usuario


class BaseElegibilidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.profesor = crear_usuario("p1", "PROFESOR")
        cls.libros = [crear_libro(isbn=f"978000000000{i}", titulo=f"Libro {i}") for i in range(5)]
        cls.ejemplares = [crear_ejemplar(libro, f"EJ-{i}") for i, libro in enumerate(cls.libros)]

    def prestar(self, usuario, indice, estado=Prestamo.Estado.ACTIVO, dias_para_vencer=7):
        return Prestamo.objects.create(
            usuario=usuario,
            ejemplar=self.ejemplares[indice],
            estado=estado,
            fecha_vencimiento=timezone.localdate() + timedelta(days=dias_para_vencer),
        )


class CuentaTests(BaseElegibilidadTests):
    def test_usuario_sin_problemas_es_elegible(self):
        self.assertEqual(verificar_elegibilidad(self.estudiante, self.libros[0]), [])

    def test_cuenta_bloqueada_muestra_el_motivo(self):
        self.estudiante.bloqueado = True
        self.estudiante.motivo_bloqueo = "Daño reiterado de libros"
        motivos = verificar_elegibilidad(self.estudiante)
        self.assertEqual(len(motivos), 1)
        self.assertIn("Daño reiterado de libros", motivos[0])

    def test_cuenta_inactiva(self):
        self.estudiante.is_active = False
        self.assertEqual(len(verificar_elegibilidad(self.estudiante)), 1)

    def test_bibliotecario_no_es_lector(self):
        bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        self.assertEqual(len(verificar_elegibilidad(bibliotecario)), 1)


class RN08Tests(BaseElegibilidadTests):
    """RN-08: multas pendientes o préstamos vencidos impiden pedir libros."""

    def test_multas_pendientes(self):
        with mock.patch("multas.services.tiene_multas_pendientes", return_value=True) as consulta:
            motivos = verificar_elegibilidad(self.estudiante)
        consulta.assert_called_once_with(self.estudiante)
        self.assertEqual(motivos, ["Tienes multas pendientes de pago."])

    def test_prestamo_vencido(self):
        self.prestar(self.estudiante, 0, estado=Prestamo.Estado.VENCIDO, dias_para_vencer=-2)
        self.assertIn("Tienes préstamos vencidos sin devolver.", verificar_elegibilidad(self.estudiante))

    def test_prestamo_activo_con_fecha_pasada(self):
        self.prestar(self.estudiante, 0, dias_para_vencer=-1)
        self.assertIn("Tienes préstamos vencidos sin devolver.", verificar_elegibilidad(self.estudiante))


class RN02Tests(BaseElegibilidadTests):
    """RN-02: máximo de préstamos vigentes (SOLICITADO, ACTIVO y VENCIDO) por tipo de usuario."""

    def test_estudiante_con_2_puede_pedir_otro(self):
        self.prestar(self.estudiante, 0)
        self.prestar(self.estudiante, 1, estado=Prestamo.Estado.SOLICITADO)
        self.assertEqual(verificar_elegibilidad(self.estudiante), [])

    def test_estudiante_con_3_llega_al_maximo(self):
        self.prestar(self.estudiante, 0)
        self.prestar(self.estudiante, 1)
        self.prestar(self.estudiante, 2, estado=Prestamo.Estado.SOLICITADO)
        motivos = verificar_elegibilidad(self.estudiante)
        self.assertEqual(len(motivos), 1)
        self.assertIn("el máximo para tu tipo de usuario es 3", motivos[0])

    def test_profesor_con_3_puede_pedir_otro(self):
        for indice in range(3):
            self.prestar(self.profesor, indice)
        self.assertEqual(verificar_elegibilidad(self.profesor), [])

    def test_devueltos_y_cancelados_no_cuentan(self):
        self.prestar(self.estudiante, 0, estado=Prestamo.Estado.DEVUELTO)
        self.prestar(self.estudiante, 1, estado=Prestamo.Estado.CANCELADO)
        self.prestar(self.estudiante, 2, estado=Prestamo.Estado.EXPIRADO)
        self.prestar(self.estudiante, 3, estado=Prestamo.Estado.PERDIDO)
        self.assertEqual(verificar_elegibilidad(self.estudiante), [])

    def test_excluir_no_cuenta_el_prestamo_indicado(self):
        self.prestar(self.estudiante, 0)
        self.prestar(self.estudiante, 1)
        solicitud = self.prestar(self.estudiante, 2, estado=Prestamo.Estado.SOLICITADO)
        self.assertEqual(verificar_elegibilidad(self.estudiante, excluir=solicitud), [])


class RN11Tests(BaseElegibilidadTests):
    """RN-11: no dos préstamos vigentes del mismo título."""

    def test_mismo_titulo_vigente(self):
        self.prestar(self.estudiante, 0)
        motivos = verificar_elegibilidad(self.estudiante, self.libros[0])
        self.assertEqual(motivos, ["Ya tienes un préstamo vigente de «Libro 0»."])

    def test_otro_ejemplar_del_mismo_titulo_tambien_cuenta(self):
        otra_copia = crear_ejemplar(self.libros[0], "EJ-0-B")
        Prestamo.objects.create(usuario=self.estudiante, ejemplar=otra_copia, estado=Prestamo.Estado.SOLICITADO)
        self.assertEqual(len(verificar_elegibilidad(self.estudiante, self.libros[0])), 1)

    def test_mismo_titulo_ya_devuelto_si_se_puede(self):
        self.prestar(self.estudiante, 0, estado=Prestamo.Estado.DEVUELTO)
        self.assertEqual(verificar_elegibilidad(self.estudiante, self.libros[0]), [])

    def test_otro_titulo_si_se_puede(self):
        self.prestar(self.estudiante, 0)
        self.assertEqual(verificar_elegibilidad(self.estudiante, self.libros[1]), [])

    def test_excluir_la_propia_solicitud(self):
        solicitud = self.prestar(self.estudiante, 0, estado=Prestamo.Estado.SOLICITADO)
        self.assertEqual(verificar_elegibilidad(self.estudiante, self.libros[0], excluir=solicitud), [])
