from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Usuario
from .services import cambiar_bloqueo_cuenta


class BloqueoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = Usuario.objects.create_user(
            username="responsable_bloqueo",
            email="responsable.bloqueo@example.com",
            tipo_usuario="BIBLIOTECARIO",
        )
        cls.lector = Usuario.objects.create_user(
            username="lector_bloqueo",
            email="lector.bloqueo@example.com",
            tipo_usuario="ESTUDIANTE",
        )

    def test_bloquear_exige_motivo(self):
        with self.assertRaises(ValidationError):
            cambiar_bloqueo_cuenta(
                responsable=self.bibliotecario,
                usuario_id=self.lector.pk,
                bloquear=True,
                motivo="   ",
            )

        self.lector.refresh_from_db()
        self.assertFalse(self.lector.bloqueado)

    def test_bloquea_y_desbloquea_sin_desactivar(self):
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.post(
            reverse("cuentas:usuario_bloquear", args=[self.lector.pk]),
            {"motivo": "Incumplimiento de las reglas"},
        )
        self.assertRedirects(
            respuesta,
            reverse("cuentas:usuarios_lista"),
        )
        self.lector.refresh_from_db()
        self.assertTrue(self.lector.bloqueado)
        self.assertTrue(self.lector.is_active)
        self.assertEqual(
            self.lector.motivo_bloqueo,
            "Incumplimiento de las reglas",
        )

        respuesta = self.client.post(
            reverse("cuentas:usuario_desbloquear", args=[self.lector.pk])
        )
        self.assertRedirects(
            respuesta,
            reverse("cuentas:usuarios_lista"),
        )
        self.lector.refresh_from_db()
        self.assertFalse(self.lector.bloqueado)
        self.assertIsNone(self.lector.motivo_bloqueo)
        self.assertTrue(self.lector.is_active)

    def test_lector_no_puede_cambiar_bloqueos(self):
        self.client.force_login(self.lector)

        for nombre in (
            "cuentas:usuario_bloquear",
            "cuentas:usuario_desbloquear",
        ):
            with self.subTest(ruta=nombre):
                respuesta = self.client.post(
                    reverse(nombre, args=[self.bibliotecario.pk]),
                    {"motivo": "Intento sin permiso"},
                )
                self.assertEqual(respuesta.status_code, 403)

        self.bibliotecario.refresh_from_db()
        self.assertFalse(self.bibliotecario.bloqueado)

    def test_abrir_confirmacion_no_desbloquea(self):
        cambiar_bloqueo_cuenta(
            responsable=self.bibliotecario,
            usuario_id=self.lector.pk,
            bloquear=True,
            motivo="Motivo de prueba",
        )
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.get(
            reverse("cuentas:usuario_desbloquear", args=[self.lector.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.lector.refresh_from_db()
        self.assertTrue(self.lector.bloqueado)