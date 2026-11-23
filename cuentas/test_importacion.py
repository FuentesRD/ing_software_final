import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .importacion import COLUMNAS_CSV, importar_usuarios_csv
from .models import Usuario


class ImportacionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.responsable = Usuario.objects.create_user(
            username="responsable_csv",
            email="responsable.csv@example.com",
            tipo_usuario="BIBLIOTECARIO",
        )

    def fila(self, nombre):
        datos = dict.fromkeys(COLUMNAS_CSV, "")
        datos.update({
            "username": nombre,
            "email": f"{nombre}@example.com",
            "tipo_usuario": "BIBLIOTECARIO",
            "password1": "TemporalParaPruebas739!Luna",
            "password2": "TemporalParaPruebas739!Luna",
        })
        return datos

    def archivo(self, filas):
        contenido = io.StringIO(newline="")
        escritor = csv.DictWriter(
            contenido,
            fieldnames=COLUMNAS_CSV,
        )
        escritor.writeheader()
        escritor.writerows(filas)

        return SimpleUploadedFile(
            "usuarios.csv",
            contenido.getvalue().encode("utf-8"),
            content_type="text/csv",
        )

    def test_importa_usuarios_con_contrasena_protegida(self):
        cantidad = importar_usuarios_csv(
            responsable=self.responsable,
            archivo=self.archivo([
                self.fila("nuevo_csv"),
                self.fila("otro_csv"),
            ]),
        )

        self.assertEqual(cantidad, 2)
        usuario = Usuario.objects.get(username="nuevo_csv")
        self.assertTrue(
            usuario.check_password("TemporalParaPruebas739!Luna")
        )
        self.assertFalse(usuario.is_superuser)

    def test_fila_incorrecta_revierte_toda_la_importacion(self):
        incorrecta = self.fila("invalido_csv")
        incorrecta["email"] = "correo-invalido"

        with self.assertRaises(ValidationError) as error:
            importar_usuarios_csv(
                responsable=self.responsable,
                archivo=self.archivo([
                    self.fila("valido_csv"),
                    incorrecta,
                ]),
            )

        self.assertIn("Fila 3", str(error.exception))
        self.assertFalse(
            Usuario.objects.filter(username="valido_csv").exists()
        )

    def test_duplicados_en_archivo_revierten_la_importacion(self):
        datos = self.fila("duplicado_csv")

        with self.assertRaises(ValidationError):
            importar_usuarios_csv(
                responsable=self.responsable,
                archivo=self.archivo([datos, datos]),
            )

        self.assertFalse(
            Usuario.objects.filter(username="duplicado_csv").exists()
        )

    def test_rechaza_columnas_incorrectas(self):
        archivo = SimpleUploadedFile(
            "usuarios.csv",
            b"nombre,correo\nEjemplo,ejemplo@example.com\n",
        )

        with self.assertRaises(ValidationError):
            importar_usuarios_csv(
                responsable=self.responsable,
                archivo=archivo,
            )

    def test_estudiante_no_puede_importar(self):
        estudiante = Usuario.objects.create_user(
            username="lector_csv",
            email="lector.csv@example.com",
            tipo_usuario="ESTUDIANTE",
        )

        with self.assertRaises(PermissionDenied):
            importar_usuarios_csv(
                responsable=estudiante,
                archivo=self.archivo([self.fila("prohibido_csv")]),
            )

        self.assertFalse(
            Usuario.objects.filter(username="prohibido_csv").exists()
        )

    def test_bibliotecario_importa_desde_la_pantalla(self):
        self.client.force_login(self.responsable)

        respuesta = self.client.post(
            reverse("cuentas:usuarios_importar"),
            {"archivo": self.archivo([self.fila("desde_web_csv")])},
        )

        self.assertRedirects(
            respuesta,
            reverse("cuentas:usuarios_lista"),
        )
        self.assertTrue(
            Usuario.objects.filter(username="desde_web_csv").exists()
        )

    def test_error_se_muestra_sin_guardar_usuarios(self):
        self.client.force_login(self.responsable)
        incorrecta = self.fila("invalido_web_csv")
        incorrecta["email"] = "correo-invalido"

        respuesta = self.client.post(
            reverse("cuentas:usuarios_importar"),
            {
                "archivo": self.archivo([
                    self.fila("valido_web_csv"),
                    incorrecta,
                ]),
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Fila 3")
        self.assertFalse(
            Usuario.objects.filter(username="valido_web_csv").exists()
        )

    def test_lectores_no_pueden_abrir_ni_enviar_csv(self):
        for rol in ("ESTUDIANTE", "PROFESOR"):
            usuario = Usuario.objects.create_user(
                username=f"lector_web_{rol}",
                email=f"{rol.lower()}@example.com",
                tipo_usuario=rol,
            )
            self.client.force_login(usuario)
            ruta = reverse("cuentas:usuarios_importar")

            with self.subTest(rol=rol):
                self.assertEqual(
                    self.client.get(ruta).status_code,
                    403,
                )
                respuesta = self.client.post(
                    ruta,
                    {"archivo": self.archivo([self.fila("prohibido_web")])},
                )
                self.assertEqual(respuesta.status_code, 403)

        self.assertFalse(
            Usuario.objects.filter(username="prohibido_web").exists()
        )