"""Vistas del bibliotecario: permisos por rol (RNF-01), POST exitoso y POST rechazado."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from prestamos.models import PoliticaPrestamo, Prestamo, Reserva

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


def mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class BaseVistasBibliotecarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = crear_usuario("b1", "BIBLIOTECARIO")
        cls.estudiante = crear_usuario("a1", "ESTUDIANTE")
        cls.libro = crear_libro()
        cls.politica = PoliticaPrestamo.objects.get(tipo_usuario="ESTUDIANTE")

    def setUp(self):
        parche = mock.patch("prestamos.services.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.client.force_login(self.bibliotecario)

    def solicitud(self, horas_para_recoger=48):
        return Prestamo.objects.create(
            usuario=self.estudiante,
            ejemplar=crear_ejemplar(self.libro, f"EJ-S{Prestamo.objects.count()}", "RESERVADO"),
            estado=Prestamo.Estado.SOLICITADO,
            fecha_limite_recoger=timezone.now() + timedelta(hours=horas_para_recoger),
        )

    def reserva_disponible(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-R", "RESERVADO")
        return Reserva.objects.create(
            usuario=self.estudiante,
            libro=self.libro,
            estado=Reserva.Estado.DISPONIBLE,
            ejemplar_asignado=ejemplar,
            fecha_expiracion=timezone.now() + timedelta(hours=48),
        )


class PermisosBibliotecarioTests(BaseVistasBibliotecarioTests):
    NOMBRES = (
        "prestamos:solicitudes",
        "prestamos:mostrador",
        "prestamos:reservas",
        "prestamos:politicas",
    )

    def test_bibliotecario_entra_a_sus_pantallas(self):
        for nombre in self.NOMBRES:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
        url = reverse("prestamos:politica_editar", args=[self.politica.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_lector_recibe_403(self):
        self.client.force_login(self.estudiante)
        for nombre in self.NOMBRES:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        for nombre in self.NOMBRES:
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 302, nombre)
            self.assertIn(reverse("cuentas:login"), respuesta.url)

    def test_lector_no_puede_entregar(self):
        prestamo = self.solicitud()
        self.client.force_login(self.estudiante)
        respuesta = self.client.post(reverse("prestamos:entregar", args=[prestamo.pk]))
        self.assertEqual(respuesta.status_code, 403)
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.SOLICITADO)

    def test_entregar_solo_acepta_post(self):
        prestamo = self.solicitud()
        respuesta = self.client.get(reverse("prestamos:entregar", args=[prestamo.pk]))
        self.assertEqual(respuesta.status_code, 405)


class EntregarVistaTests(BaseVistasBibliotecarioTests):
    def test_lista_solo_solicitudes_pendientes(self):
        pendiente = self.solicitud()
        Prestamo.objects.create(
            usuario=self.estudiante,
            ejemplar=crear_ejemplar(self.libro, "EJ-X"),
            estado=Prestamo.Estado.CANCELADO,
        )
        respuesta = self.client.get(reverse("prestamos:solicitudes"))
        self.assertEqual(list(respuesta.context["solicitudes"]), [pendiente])

    def test_post_exitoso_entrega(self):
        prestamo = self.solicitud()
        respuesta = self.client.post(reverse("prestamos:entregar", args=[prestamo.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:solicitudes"))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(prestamo.entregado_por, self.bibliotecario)
        self.assertEqual(estado_de(prestamo.ejemplar), "PRESTADO")
        self.assertIn("Entregaste", mensajes(respuesta)[0])

    def test_post_rechazado_si_vencio_el_plazo_para_recoger(self):
        prestamo = self.solicitud(horas_para_recoger=-1)
        respuesta = self.client.post(reverse("prestamos:entregar", args=[prestamo.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:solicitudes"))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, Prestamo.Estado.SOLICITADO)
        self.assertIn("El plazo para recoger venció", mensajes(respuesta)[0])


class MostradorVistaTests(BaseVistasBibliotecarioTests):
    def test_post_exitoso_presta(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-1")
        respuesta = self.client.post(
            reverse("prestamos:mostrador"),
            {"username": "a1", "codigo_inventario": "EJ-1"},
        )
        self.assertRedirects(respuesta, reverse("prestamos:mostrador"))
        prestamo = Prestamo.objects.get(ejemplar=ejemplar)
        self.assertEqual(prestamo.estado, Prestamo.Estado.ACTIVO)
        self.assertEqual(estado_de(ejemplar), "PRESTADO")

    def test_post_rechazado_ejemplar_en_reparacion(self):
        """RN-15: el servicio rechaza y la vista lo muestra en messages sin crear nada."""
        ejemplar = crear_ejemplar(self.libro, "EJ-1", "EN_REPARACION")
        respuesta = self.client.post(
            reverse("prestamos:mostrador"),
            {"username": "a1", "codigo_inventario": "EJ-1"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(estado_de(ejemplar), "EN_REPARACION")
        self.assertIn("no está disponible", mensajes(respuesta)[0])

    def test_post_rechazado_codigo_inexistente(self):
        respuesta = self.client.post(
            reverse("prestamos:mostrador"),
            {"username": "a1", "codigo_inventario": "NO-EXISTE"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(
            respuesta.context["form"], "codigo_inventario",
            "No existe un ejemplar con ese código de inventario.",
        )
        self.assertFalse(Prestamo.objects.exists())


class ReservasVistaTests(BaseVistasBibliotecarioTests):
    def test_filtra_por_estado(self):
        pendiente = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        Reserva.objects.create(
            usuario=self.estudiante, libro=self.libro, estado=Reserva.Estado.CANCELADA
        )
        respuesta = self.client.get(reverse("prestamos:reservas"), {"estado": "PENDIENTE"})
        self.assertEqual(list(respuesta.context["reservas"]), [pendiente])

    def test_post_exitoso_entrega_la_reserva_disponible(self):
        reserva = self.reserva_disponible()
        respuesta = self.client.post(reverse("prestamos:recoger_reserva", args=[reserva.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ATENDIDA)
        self.assertEqual(estado_de(reserva.ejemplar_asignado), "PRESTADO")

    def test_post_rechazado_recoger_una_reserva_pendiente(self):
        reserva = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        respuesta = self.client.post(reverse("prestamos:recoger_reserva", args=[reserva.pk]))
        self.assertRedirects(respuesta, reverse("prestamos:reservas"))
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(len(mensajes(respuesta)), 1)

    def test_post_exitoso_cancela_con_motivo(self):
        reserva = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        respuesta = self.client.post(
            reverse("prestamos:cancelar_reserva_bibliotecario", args=[reserva.pk]),
            {"motivo": "Libro retirado de circulación"},
        )
        self.assertRedirects(respuesta, reverse("prestamos:reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)

    def test_post_rechazado_cancelar_sin_motivo(self):
        reserva = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        respuesta = self.client.post(
            reverse("prestamos:cancelar_reserva_bibliotecario", args=[reserva.pk]),
            {"motivo": "   "},
        )
        self.assertRedirects(respuesta, reverse("prestamos:reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE)
        self.assertEqual(mensajes(respuesta), ["Indica el motivo de la cancelación."])


class PoliticasVistaTests(BaseVistasBibliotecarioTests):
    def datos(self, **cambios):
        datos = {
            "dias_prestamo": self.politica.dias_prestamo,
            "max_libros": self.politica.max_libros,
            "max_renovaciones": self.politica.max_renovaciones,
            "multa_por_dia": self.politica.multa_por_dia,
            "multa_maxima": self.politica.multa_maxima,
            "horas_para_recoger": self.politica.horas_para_recoger,
        }
        datos.update(cambios)
        return datos

    def test_post_exitoso_guarda_los_cambios(self):
        url = reverse("prestamos:politica_editar", args=[self.politica.pk])
        respuesta = self.client.post(url, self.datos(dias_prestamo=10))
        self.assertRedirects(respuesta, reverse("prestamos:politicas"))
        self.politica.refresh_from_db()
        self.assertEqual(self.politica.dias_prestamo, 10)

    def test_post_rechazado_multa_maxima_menor_que_la_diaria(self):
        url = reverse("prestamos:politica_editar", args=[self.politica.pk])
        respuesta = self.client.post(url, self.datos(multa_maxima="5.00"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors)
        self.politica.refresh_from_db()
        self.assertEqual(self.politica.multa_maxima, Decimal("300.00"))

    def test_sin_cambios_no_guarda(self):
        url = reverse("prestamos:politica_editar", args=[self.politica.pk])
        respuesta = self.client.post(url, self.datos())
        self.assertRedirects(respuesta, reverse("prestamos:politicas"))
        self.assertEqual(mensajes(respuesta), ["No hiciste cambios."])

    def test_lector_no_puede_editar_politicas(self):
        self.client.force_login(self.estudiante)
        url = reverse("prestamos:politica_editar", args=[self.politica.pk])
        respuesta = self.client.post(url, self.datos(dias_prestamo=99))
        self.assertEqual(respuesta.status_code, 403)
        self.politica.refresh_from_db()
        self.assertNotEqual(self.politica.dias_prestamo, 99)
