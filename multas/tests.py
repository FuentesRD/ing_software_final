"""Pruebas del paquete D (multas): CU-25, CU-26, CU-27, CU-28, CU-29, CU-14 y RN-07, RN-12, RN-13, RN-14."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from multas.models import Multa, Pago
from multas.services import (
    condonar_multa,
    monto_adeudado,
    registrar_devolucion,
    registrar_pago,
    registrar_perdida_o_danio,
    saldo_de,
)
from notificaciones.models import Notificacion
from prestamos.models import Prestamo, Reserva
from prestamos.tests.utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class BaseMultas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lector = crear_usuario("lector1", "ESTUDIANTE")
        cls.otro = crear_usuario("lector2", "ESTUDIANTE")
        cls.bibliotecario = crear_usuario("biblio1", "BIBLIOTECARIO")
        cls.libro = crear_libro()

    def prestamo_activo(self, dias_para_vencer=3, codigo="EJ-1", usuario=None, estado="ACTIVO"):
        """Préstamo entregado; dias_para_vencer negativo = ya vencido."""
        ejemplar = crear_ejemplar(self.libro, codigo, estado="PRESTADO")
        return Prestamo.objects.create(
            usuario=usuario or self.lector,
            ejemplar=ejemplar,
            estado=estado,
            fecha_prestamo=timezone.now() - timedelta(days=7),
            fecha_vencimiento=timezone.localdate() + timedelta(days=dias_para_vencer),
        )

    def multa(self, monto="100.00", usuario=None):
        prestamo = self.prestamo_activo(codigo=f"EJ-M{Multa.objects.count()}", usuario=usuario, estado="DEVUELTO")
        return Multa.objects.create(
            prestamo=prestamo,
            usuario=prestamo.usuario,
            motivo=Multa.Motivo.RETRASO,
            dias_retraso=5,
            monto=Decimal(monto),
        )


class DevolucionTests(BaseMultas):
    """CU-25, CU-26 y RN-07 (casos límite: 0, 1, varios días y tope)."""

    def test_devolucion_a_tiempo_no_genera_multa_y_libera_el_ejemplar(self):
        prestamo = self.prestamo_activo(dias_para_vencer=0)

        multa = registrar_devolucion(prestamo, self.bibliotecario)

        prestamo.refresh_from_db()
        self.assertIsNone(multa)
        self.assertEqual(prestamo.estado, Prestamo.Estado.DEVUELTO)
        self.assertEqual(prestamo.recibido_por, self.bibliotecario)
        self.assertEqual(estado_de(prestamo.ejemplar), "DISPONIBLE")

    def test_un_dia_de_retraso(self):
        prestamo = self.prestamo_activo(dias_para_vencer=-1, estado="VENCIDO")

        multa = registrar_devolucion(prestamo, self.bibliotecario)

        self.assertEqual(multa.dias_retraso, 1)
        self.assertEqual(multa.monto, Decimal("10.00"))
        self.assertEqual(multa.estado, Multa.Estado.PENDIENTE)
        self.assertTrue(Notificacion.objects.filter(usuario=self.lector, tipo="MULTA").exists())

    def test_varios_dias_de_retraso(self):
        multa = registrar_devolucion(self.prestamo_activo(dias_para_vencer=-4), self.bibliotecario)

        self.assertEqual(multa.monto, Decimal("40.00"))

    def test_la_multa_no_pasa_del_tope(self):
        multa = registrar_devolucion(self.prestamo_activo(dias_para_vencer=-45), self.bibliotecario)

        self.assertEqual(multa.monto, Decimal("300.00"))

    def test_rn12_el_ejemplar_devuelto_se_aparta_para_la_primera_reserva(self):
        prestamo = self.prestamo_activo()
        primera = Reserva.objects.create(usuario=self.otro, libro=self.libro)
        segunda = Reserva.objects.create(
            usuario=crear_usuario("lector4"), libro=self.libro,
            fecha_reserva=timezone.now() + timedelta(minutes=5),
        )

        registrar_devolucion(prestamo, self.bibliotecario)

        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(estado_de(prestamo.ejemplar), "RESERVADO")
        self.assertEqual(primera.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(primera.ejemplar_asignado_id, prestamo.ejemplar_id)
        self.assertEqual(segunda.estado, Reserva.Estado.PENDIENTE)
        self.assertTrue(Notificacion.objects.filter(usuario=self.otro, tipo="RESERVA_DISPONIBLE").exists())

    def test_no_se_puede_devolver_dos_veces(self):
        prestamo = self.prestamo_activo()
        registrar_devolucion(prestamo, self.bibliotecario)

        with self.assertRaises(ValidationError):
            registrar_devolucion(prestamo, self.bibliotecario)


class PerdidaDanioTests(BaseMultas):
    """CU-27 / RN-13 / RN-15."""

    def test_perdida_marca_prestamo_y_ejemplar_como_perdidos(self):
        prestamo = self.prestamo_activo()

        multa = registrar_perdida_o_danio(prestamo, Multa.Motivo.PERDIDA, "450.00", self.bibliotecario)

        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.PERDIDO)
        self.assertEqual(estado_de(prestamo.ejemplar), "PERDIDO")
        self.assertEqual(multa.monto, Decimal("450.00"))
        self.assertEqual(multa.motivo, Multa.Motivo.PERDIDA)

    def test_no_se_registra_perdida_de_un_prestamo_devuelto(self):
        prestamo = self.prestamo_activo(estado="DEVUELTO")

        with self.assertRaises(ValidationError):
            registrar_perdida_o_danio(prestamo, Multa.Motivo.PERDIDA, "450.00", self.bibliotecario)
        self.assertFalse(Multa.objects.exists())

    def test_danio_en_curso_registra_devolucion_retraso_y_reparacion(self):
        prestamo = self.prestamo_activo(dias_para_vencer=-2)
        reserva = Reserva.objects.create(usuario=self.otro, libro=self.libro)

        registrar_perdida_o_danio(prestamo, Multa.Motivo.DANIO, "200.00", self.bibliotecario)

        prestamo.refresh_from_db()
        reserva.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.DEVUELTO)
        self.assertEqual(estado_de(prestamo.ejemplar), "EN_REPARACION")
        # RN-15: un ejemplar dañado no se aparta para la reserva.
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        motivos = sorted(Multa.objects.filter(prestamo=prestamo).values_list("motivo", "monto"))
        self.assertEqual(motivos, [("DANIO", Decimal("200.00")), ("RETRASO", Decimal("20.00"))])

    def test_danio_detectado_despues_de_devolver(self):
        prestamo = self.prestamo_activo()
        registrar_devolucion(prestamo, self.bibliotecario)

        registrar_perdida_o_danio(prestamo, Multa.Motivo.DANIO, "120.00", self.bibliotecario)

        self.assertEqual(estado_de(prestamo.ejemplar), "EN_REPARACION")

    def test_costo_y_motivo_invalidos(self):
        prestamo = self.prestamo_activo()
        for motivo, costo in [(Multa.Motivo.PERDIDA, "0"), (Multa.Motivo.RETRASO, "100"), (Multa.Motivo.DANIO, "abc")]:
            with self.subTest(motivo=motivo, costo=costo), self.assertRaises(ValidationError):
                registrar_perdida_o_danio(prestamo, motivo, costo, self.bibliotecario)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)


class PagoYCondonacionTests(BaseMultas):
    """CU-28, CU-29 y RN-14."""

    def test_pago_parcial_y_luego_total(self):
        multa = self.multa("100.00")

        registrar_pago(multa, "40.00", "EFECTIVO", "F-1", self.bibliotecario)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, Multa.Estado.PENDIENTE)
        self.assertEqual(saldo_de(multa), Decimal("60.00"))
        self.assertEqual(monto_adeudado(self.lector), Decimal("60.00"))

        registrar_pago(multa, "60.00", "TARJETA", "F-2", self.bibliotecario)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, Multa.Estado.PAGADA)
        self.assertEqual(monto_adeudado(self.lector), Decimal("0.00"))

    def test_no_se_paga_mas_del_saldo(self):
        multa = self.multa("50.00")

        with self.assertRaises(ValidationError):
            registrar_pago(multa, "60.00", "EFECTIVO", "F-1", self.bibliotecario)
        self.assertFalse(Pago.objects.exists())

    def test_condonar_exige_justificacion(self):
        multa = self.multa()

        with self.assertRaises(ValidationError):
            condonar_multa(multa, "   ", self.bibliotecario)

        condonar_multa(multa, "Libro devuelto por un familiar enfermo", self.bibliotecario)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, Multa.Estado.CONDONADA)
        self.assertEqual(multa.condonada_por, self.bibliotecario)

    def test_no_se_condona_ni_paga_una_multa_ya_cerrada(self):
        multa = self.multa()
        condonar_multa(multa, "Error de captura", self.bibliotecario)

        with self.assertRaises(ValidationError):
            condonar_multa(multa, "Otra vez", self.bibliotecario)
        with self.assertRaises(ValidationError):
            registrar_pago(multa, "10.00", "EFECTIVO", "F-9", self.bibliotecario)


class VistasMultasTests(BaseMultas):
    """Pantallas de multas: permisos (RNF-02) y flujo del bibliotecario."""

    def test_mis_multas_solo_muestra_las_propias(self):
        self.multa("77.00", usuario=self.lector)
        self.multa("88.00", usuario=self.otro)
        self.client.force_login(self.lector)

        respuesta = self.client.get(reverse("multas:mis_multas"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "77.00")
        self.assertNotContains(respuesta, "88.00")

    def test_un_lector_no_entra_a_las_pantallas_del_bibliotecario(self):
        multa = self.multa()
        self.client.force_login(self.lector)
        for url in [
            reverse("multas:lista"),
            reverse("multas:registrar_devolucion"),
            reverse("multas:registrar_pago", args=[multa.pk]),
            reverse("multas:condonar_multa", args=[multa.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_pantallas_del_bibliotecario_cargan(self):
        multa = self.multa()
        prestamo = self.prestamo_activo(codigo="EJ-V")
        self.client.force_login(self.bibliotecario)
        for url in [
            reverse("multas:lista"),
            reverse("multas:lista") + "?estado=TODAS&q=lector",
            reverse("multas:registrar_devolucion") + "?q=EJ-V",
            reverse("multas:registrar_perdida_danio_prestamo", args=[prestamo.pk]),
            reverse("multas:registrar_pago", args=[multa.pk]),
            reverse("multas:condonar_multa", args=[multa.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_devolucion_desde_la_pantalla(self):
        prestamo = self.prestamo_activo(dias_para_vencer=-3)
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.post(
            reverse("multas:registrar_devolucion"), {"prestamo_id": prestamo.pk}, follow=True
        )

        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.DEVUELTO)
        self.assertContains(respuesta, "Se generó una multa de $30.00")

    def test_pago_desde_la_pantalla(self):
        multa = self.multa("100.00")
        self.client.force_login(self.bibliotecario)

        self.client.post(
            reverse("multas:registrar_pago", args=[multa.pk]),
            {"monto": "100.00", "metodo": "EFECTIVO", "folio_recibo": "R-100"},
        )

        multa.refresh_from_db()
        self.assertEqual(multa.estado, Multa.Estado.PAGADA)

    def test_perdida_desde_la_pantalla(self):
        prestamo = self.prestamo_activo()
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.post(
            reverse("multas:registrar_perdida_danio_prestamo", args=[prestamo.pk]),
            {"motivo": "PERDIDA", "costo_reposicion": "350.00"},
        )

        self.assertRedirects(respuesta, reverse("multas:lista"))
        self.assertTrue(Multa.objects.filter(prestamo=prestamo, motivo="PERDIDA", monto=Decimal("350.00")).exists())
