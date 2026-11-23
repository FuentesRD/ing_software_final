from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Usuario
from .services import cambiar_estado_cuenta


class EstadoCuentaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = Usuario.objects.create_user(
            username="responsable",
            email="responsable@example.com",
            tipo_usuario="BIBLIOTECARIO",
        )
        cls.lector = Usuario.objects.create_user(
            username="lector_estado",
            email="lector.estado@example.com",
            password="ClaveTemporalPruebas947!",
            tipo_usuario="ESTUDIANTE",
        )

    def test_desactivar_y_reactivar_conserva_la_cuenta(self):
        self.client.force_login(self.bibliotecario)

        for activar, nombre_ruta in (
            (False, "cuentas:usuario_desactivar"),
            (True, "cuentas:usuario_reactivar"),
        ):
            with self.subTest(activar=activar):
                respuesta = self.client.post(
                    reverse(nombre_ruta, args=[self.lector.pk])
                )
                self.assertRedirects(
                    respuesta,
                    reverse("cuentas:usuarios_lista"),
                )
                self.lector.refresh_from_db()
                self.assertEqual(self.lector.is_active, activar)

    def test_get_solo_muestra_confirmacion(self):
        self.client.force_login(self.bibliotecario)
        respuesta = self.client.get(
            reverse("cuentas:usuario_desactivar", args=[self.lector.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.lector.refresh_from_db()
        self.assertTrue(self.lector.is_active)

    def test_cuenta_desactivada_no_puede_iniciar_sesion(self):
        cambiar_estado_cuenta(
            responsable=self.bibliotecario,
            usuario_id=self.lector.pk,
            activar=False,
        )

        acceso = self.client.login(
            username=self.lector.username,
            password="ClaveTemporalPruebas947!",
        )
        self.assertFalse(acceso)

    def test_bibliotecario_no_puede_desactivarse(self):
        with self.assertRaises(ValidationError):
            cambiar_estado_cuenta(
                responsable=self.bibliotecario,
                usuario_id=self.bibliotecario.pk,
                activar=False,
            )

        self.bibliotecario.refresh_from_db()
        self.assertTrue(self.bibliotecario.is_active)

    def test_lector_no_puede_cambiar_estados(self):
        self.client.force_login(self.lector)

        for nombre_ruta in (
            "cuentas:usuario_desactivar",
            "cuentas:usuario_reactivar",
        ):
            with self.subTest(ruta=nombre_ruta):
                respuesta = self.client.post(
                    reverse(nombre_ruta, args=[self.bibliotecario.pk])
                )
                self.assertEqual(respuesta.status_code, 403)

        self.bibliotecario.refresh_from_db()
        self.assertTrue(self.bibliotecario.is_active)