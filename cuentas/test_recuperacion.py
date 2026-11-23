import re

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Usuario


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class RecuperacionTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="lector",
            email="lector@example.com",
            password="AnteriorParaPruebas927!",
            tipo_usuario="ESTUDIANTE",
        )

    def test_recuperacion_completa(self):
        respuesta = self.client.post(
            reverse("cuentas:recuperar"),
            {"email": self.usuario.email},
        )
        self.assertRedirects(
            respuesta,
            reverse("cuentas:recuperar_enviado"),
        )
        self.assertEqual(len(mail.outbox), 1)

        enlace = re.search(
            r"http://testserver(/\S+)",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(enlace)
        ruta = enlace.group(1)

        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 302)
        formulario = respuesta.url

        nueva = "NuevaParaPruebas748!Luna"
        respuesta = self.client.post(
            formulario,
            {
                "new_password1": nueva,
                "new_password2": nueva,
            },
        )
        self.assertRedirects(
            respuesta,
            reverse("cuentas:restablecer_completo"),
        )

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(nueva))
        self.assertFalse(
            self.usuario.check_password("AnteriorParaPruebas927!")
        )
        self.assertTrue(
            self.client.login(username="lector", password=nueva)
        )

        respuesta = self.client.get(ruta)
        self.assertFalse(respuesta.context["validlink"])

    def test_correo_desconocido_no_revela_cuentas(self):
        respuesta = self.client.post(
            reverse("cuentas:recuperar"),
            {"email": "desconocido@example.com"},
        )
        self.assertRedirects(
            respuesta,
            reverse("cuentas:recuperar_enviado"),
        )
        self.assertEqual(len(mail.outbox), 0)