from django.test import TestCase
from django.urls import reverse

from .models import Usuario


class ListaUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = Usuario.objects.create_user(
            username="bibliotecario",
            email="bibliotecario@example.com",
            tipo_usuario="BIBLIOTECARIO",
        )
        cls.estudiante = Usuario.objects.create_user(
            username="estudiante",
            email="estudiante@example.com",
            tipo_usuario="ESTUDIANTE",
        )
        cls.profesor = Usuario.objects.create_user(
            username="profesor",
            email="profesor@example.com",
            tipo_usuario="PROFESOR",
        )

    def test_sin_sesion_redirige_al_login(self):
        respuesta = self.client.get(reverse("cuentas:usuarios_lista"))
        self.assertRedirects(
            respuesta,
            reverse("cuentas:login") + "?next=/usuarios/",
        )

    def test_bibliotecario_puede_ver_usuarios(self):
        self.client.force_login(self.bibliotecario)
        respuesta = self.client.get(reverse("cuentas:usuarios_lista"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.estudiante.email)

    def test_lectores_no_pueden_ver_usuarios(self):
        for usuario in (self.estudiante, self.profesor):
            with self.subTest(rol=usuario.tipo_usuario):
                self.client.force_login(usuario)
                respuesta = self.client.get(
                    reverse("cuentas:usuarios_lista")
                )
                self.assertEqual(respuesta.status_code, 403)
                self.assertNotContains(
                    respuesta,
                    self.estudiante.email,
                    status_code=403,
                )