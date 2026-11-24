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


class EditarUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = Usuario.objects.create_user(
            username="bibliotecario_edicion",
            email="bibliotecario.edicion@example.com",
            tipo_usuario="BIBLIOTECARIO",
        )
        cls.estudiante = Usuario.objects.create_user(
            username="estudiante_edicion",
            email="estudiante.edicion@example.com",
            tipo_usuario="ESTUDIANTE",
        )
        cls.profesor = Usuario.objects.create_user(
            username="profesor_edicion",
            email="profesor.edicion@example.com",
            tipo_usuario="PROFESOR",
        )

    def datos_edicion(self):
        return {
            "first_name": "Nombre actualizado",
            "last_name": "Prueba",
            "email": self.estudiante.email,
            "telefono": "5551234567",
        }

    def test_bibliotecario_puede_editar(self):
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.post(
            reverse("cuentas:usuario_editar", args=[self.estudiante.pk]),
            self.datos_edicion(),
        )

        self.assertRedirects(
            respuesta,
            reverse("cuentas:usuarios_lista"),
        )
        self.estudiante.refresh_from_db()
        self.assertEqual(self.estudiante.first_name, "Nombre actualizado")
        self.assertEqual(self.estudiante.telefono, "5551234567")

    def test_lectores_no_pueden_editar(self):
        ruta = reverse(
            "cuentas:usuario_editar",
            args=[self.estudiante.pk],
        )

        for usuario in (self.estudiante, self.profesor):
            for metodo in ("get", "post"):
                with self.subTest(rol=usuario.tipo_usuario, metodo=metodo):
                    self.client.force_login(usuario)
                    respuesta = getattr(self.client, metodo)(
                        ruta,
                        self.datos_edicion() if metodo == "post" else {},
                    )
                    self.assertEqual(respuesta.status_code, 403)

        self.estudiante.refresh_from_db()
        self.assertEqual(self.estudiante.first_name, "")

    def test_no_permite_correo_duplicado(self):
        self.client.force_login(self.bibliotecario)
        datos = self.datos_edicion()
        datos["email"] = self.bibliotecario.email

        respuesta = self.client.post(
            reverse("cuentas:usuario_editar", args=[self.estudiante.pk]),
            datos,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("email", respuesta.context["form"].errors)
        self.estudiante.refresh_from_db()
        self.assertEqual(
            self.estudiante.email,
            "estudiante.edicion@example.com",
        )