"""Pruebas de notificaciones (CU-15)."""

from django.test import TestCase
from django.urls import reverse

from notificaciones.models import Notificacion
from notificaciones.services import marcar_todas_leidas, notificaciones_sin_leer, notificar
from prestamos.tests.utilidades import crear_usuario


class NotificacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lector = crear_usuario("lector1")
        cls.otro = crear_usuario("lector2")

    def test_notificar_recorta_el_mensaje_a_500_caracteres(self):
        notificacion = notificar(self.lector, "GENERAL", "x" * 600)

        self.assertEqual(len(notificacion.mensaje), 500)
        self.assertFalse(notificacion.leida)

    def test_marcar_todas_leidas_solo_afecta_al_usuario(self):
        notificar(self.lector, "GENERAL", "uno")
        notificar(self.lector, "MULTA", "dos")
        notificar(self.otro, "GENERAL", "ajena")

        self.assertEqual(marcar_todas_leidas(self.lector), 2)
        self.assertEqual(notificaciones_sin_leer(self.lector), 0)
        self.assertEqual(notificaciones_sin_leer(self.otro), 1)

    def test_la_pantalla_muestra_solo_las_propias(self):
        notificar(self.lector, "VENCE_PRONTO", "Tu préstamo vence mañana")
        notificar(self.otro, "GENERAL", "Mensaje de otra persona")
        self.client.force_login(self.lector)

        respuesta = self.client.get(reverse("notificaciones:mis_notificaciones"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Tu préstamo vence mañana")
        self.assertNotContains(respuesta, "Mensaje de otra persona")

    def test_marcar_leidas_desde_la_pantalla(self):
        notificar(self.lector, "GENERAL", "uno")
        self.client.force_login(self.lector)

        respuesta = self.client.post(reverse("notificaciones:marcar_leidas"))

        self.assertRedirects(respuesta, reverse("notificaciones:mis_notificaciones"))
        self.assertFalse(Notificacion.objects.filter(usuario=self.lector, leida=False).exists())

    def test_requiere_sesion(self):
        respuesta = self.client.get(reverse("notificaciones:mis_notificaciones"))

        self.assertEqual(respuesta.status_code, 302)
