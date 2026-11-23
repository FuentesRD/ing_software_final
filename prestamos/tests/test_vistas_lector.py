"""Vistas del lector: permisos por rol (RNF-01, RNF-02), POST exitoso y POST rechazado."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from multas.models import Multa
from prestamos.models import Prestamo, Reserva

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


def mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class BaseVistasLectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.otro_lector = crear_usuario("a2", "ESTUDIANTE")
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        cls.libro = crear_libro()

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.client.force_login(self.estudiante)

    def prestamo_activo(self, usuario=None, num_renovaciones=0):
        return Prestamo.objects.create(
            usuario=usuario or self.estudiante,
            ejemplar=crear_ejemplar(self.libro, f"EJ-P{Prestamo.objects.count()}", "PRESTADO"),
            estado=Prestamo.Estado.ACTIVO,
            fecha_prestamo=timezone.now(),
            fecha_vencimiento=timezone.localdate() + timedelta(days=3),
            num_renovaciones=num_renovaciones,
        )

    def solicitud(self, usuario=None):
        return Prestamo.objects.create(
            usuario=usuario or self.estudiante,
            ejemplar=crear_ejemplar(self.libro, f"EJ-S{Prestamo.objects.count()}", "RESERVADO"),
            estado=Prestamo.Estado.SOLICITADO,
            fecha_limite_recoger=timezone.now() + timedelta(hours=48),
        )


class PermisosLectorTests(BaseVistasLectorTests):
    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        for nombre in ("prestamos:mis_prestamos", "prestamos:mis_reservas"):
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn(reverse("cuentas:login"), respuesta.url)

    def test_bibliotecario_no_entra_a_vistas_de_lector(self):
        self.client.force_login(self.bibliotecario)
        urls = [
            reverse("prestamos:mis_prestamos"),
            reverse("prestamos:mis_reservas"),
            reverse("prestamos:solicitar", args=[self.libro.pk]),
            reverse("prestamos:reservar", args=[self.libro.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_las_acciones_solo_aceptan_post(self):
        prestamo = self.prestamo_activo()
        respuesta = self.client.get(reverse("prestamos:renovar", args=[prestamo.pk]))
        self.assertEqual(respuesta.status_code, 405)

    def test_rnf02_solo_ve_sus_propios_prestamos(self):
        propio = self.prestamo_activo()
        ajeno = self.prestamo_activo(usuario=self.otro_lector)
        respuesta = self.client.get(reverse("prestamos:mis_prestamos"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["prestamos"]), [propio])
        self.assertNotIn(ajeno, respuesta.context["prestamos"])

    def test_rnf02_no_puede_renovar_un_prestamo_ajeno(self):
        ajeno = self.prestamo_activo(usuario=self.otro_lector)
        respuesta = self.client.post(reverse("prestamos:renovar", args=[ajeno.pk]))
        self.assertEqual(respuesta.status_code, 404)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.num_renovaciones, 0)

    def test_rnf02_no_puede_cancelar_una_reserva_ajena(self):
        ajena = Reserva.objects.create(usuario=self.otro_lector, libro=self.libro)
        respuesta = self.client.post(reverse("prestamos:cancelar_reserva", args=[ajena.pk]))
        self.assertEqual(respuesta.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, Reserva.Estado.PENDIENTE)

    def test_libro_inactivo_da_404(self):
        inactivo = crear_libro(isbn="9780000000099", titulo="Dado de baja")
        inactivo.activo = False
        inactivo.save()
        respuesta = self.client.get(reverse("prestamos:solicitar", args=[inactivo.pk]))
        self.assertEqual(respuesta.status_code, 404)


class SolicitarVistaTests(BaseVistasLectorTests):
    def test_get_muestra_el_libro(self):
        crear_ejemplar(self.libro, "EJ-1")
        respuesta = self.client.get(reverse("prestamos:solicitar", args=[self.libro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.libro.titulo)
        self.assertTrue(respuesta.context["hay_disponibles"])

    def test_post_exitoso_crea_la_solicitud(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        respuesta = self.client.post(reverse("prestamos:solicitar", args=[self.libro.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_prestamos"))
        prestamo = Prestamo.objects.get(usuario=self.estudiante)
        self.assertEqual(prestamo.estado, Prestamo.Estado.SOLICITADO)
        self.assertEqual(estado_de(ejemplar), "RESERVADO")
        self.assertIn("Solicitaste", mensajes(respuesta)[0])

    def test_post_rechazado_por_multa_pendiente_muestra_el_monto(self):
        """RN-08 / CU-06 4a con una Multa real: el motivo llega a messages."""
        anterior = Prestamo.objects.create(
            usuario=self.estudiante,
            ejemplar=crear_ejemplar(self.libro, "EJ-ANT"),
            estado=Prestamo.Estado.DEVUELTO,
            fecha_vencimiento=timezone.localdate() - timedelta(days=10),
        )
        Multa.objects.create(
            prestamo=anterior, usuario=self.estudiante, motivo=Multa.Motivo.RETRASO,
            dias_retraso=3, monto=Decimal("30.00"),
        )
        ejemplar = crear_ejemplar(self.libro, "EJ-1")

        respuesta = self.client.post(reverse("prestamos:solicitar", args=[self.libro.pk]))

        self.assertRedirects(respuesta, reverse("prestamos:solicitar", args=[self.libro.pk]))
        self.assertEqual(
            mensajes(respuesta), ["Tienes multas pendientes de pago. Monto adeudado: $30.00."]
        )
        self.assertFalse(Prestamo.objects.filter(estado=Prestamo.Estado.SOLICITADO).exists())
        self.assertEqual(estado_de(ejemplar), "DISPONIBLE")

    def test_sin_ejemplares_ofrece_reservar(self):
        respuesta = self.client.post(reverse("prestamos:solicitar", args=[self.libro.pk]), follow=True)
        self.assertFalse(Prestamo.objects.exists())
        self.assertContains(respuesta, "Puedes reservarlo")
        self.assertContains(respuesta, reverse("prestamos:reservar", args=[self.libro.pk]))


class ReservarVistaTests(BaseVistasLectorTests):
    def test_post_exitoso_crea_la_reserva(self):
        respuesta = self.client.post(reverse("prestamos:reservar", args=[self.libro.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_reservas"))
        reserva = Reserva.objects.get(usuario=self.estudiante)
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        self.assertIn("Tu lugar en la fila es el 1", mensajes(respuesta)[0])

    def test_post_rechazado_si_hay_ejemplares_disponibles(self):
        crear_ejemplar(self.libro, "EJ-1")
        respuesta = self.client.post(reverse("prestamos:reservar", args=[self.libro.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:reservar", args=[self.libro.pk]))
        self.assertFalse(Reserva.objects.exists())
        self.assertIn("solicita el préstamo", mensajes(respuesta)[0])

    def test_mis_reservas_muestra_el_lugar_en_la_fila(self):
        Reserva.objects.create(
            usuario=self.otro_lector, libro=self.libro, fecha_reserva=timezone.now() - timedelta(hours=1)
        )
        Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        respuesta = self.client.get(reverse("prestamos:mis_reservas"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([r.posicion for r in respuesta.context["reservas"]], [2])


class RenovarVistaTests(BaseVistasLectorTests):
    def test_post_exitoso_renueva(self):
        prestamo = self.prestamo_activo()
        respuesta = self.client.post(reverse("prestamos:renovar", args=[prestamo.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_prestamos"))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.num_renovaciones, 1)
        self.assertIn("Renovaste", mensajes(respuesta)[0])

    def test_post_rechazado_sin_renovaciones_restantes(self):
        """RN-03: el estudiante solo tiene 1 renovación y ya la usó."""
        prestamo = self.prestamo_activo(num_renovaciones=1)
        vencimiento = prestamo.fecha_vencimiento
        respuesta = self.client.post(reverse("prestamos:renovar", args=[prestamo.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_prestamos"))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.fecha_vencimiento, vencimiento)
        self.assertEqual(mensajes(respuesta), ["Ya usaste todas las renovaciones de este préstamo."])


class CancelarVistasTests(BaseVistasLectorTests):
    def test_post_exitoso_cancela_la_solicitud(self):
        prestamo = self.solicitud()
        respuesta = self.client.post(reverse("prestamos:cancelar_solicitud", args=[prestamo.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_prestamos"))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.CANCELADO)
        self.assertEqual(estado_de(prestamo.ejemplar), "DISPONIBLE")

    def test_post_rechazado_si_el_prestamo_ya_esta_activo(self):
        prestamo = self.prestamo_activo()
        respuesta = self.client.post(reverse("prestamos:cancelar_solicitud", args=[prestamo.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_prestamos"))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(len(mensajes(respuesta)), 1)

    def test_post_exitoso_cancela_la_reserva(self):
        reserva = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        respuesta = self.client.post(reverse("prestamos:cancelar_reserva", args=[reserva.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)

    def test_post_rechazado_si_la_reserva_ya_fue_atendida(self):
        reserva = Reserva.objects.create(
            usuario=self.estudiante, libro=self.libro, estado=Reserva.Estado.ATENDIDA
        )
        respuesta = self.client.post(reverse("prestamos:cancelar_reserva", args=[reserva.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:mis_reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ATENDIDA)
        self.assertEqual(len(mensajes(respuesta)), 1)
