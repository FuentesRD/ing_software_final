from django.test import SimpleTestCase

from .forms import FiltroReporteForm


class FiltroReporteFormTests(SimpleTestCase):
    def test_acepta_periodo_correcto(self):
        formulario = FiltroReporteForm(data={
            "fecha_inicio": "2026-11-01",
            "fecha_fin": "2026-11-21",
        })

        self.assertTrue(formulario.is_valid())

    def test_rechaza_periodo_invertido(self):
        formulario = FiltroReporteForm(data={
            "fecha_inicio": "2026-11-21",
            "fecha_fin": "2026-11-01",
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn("fecha_fin", formulario.errors)

    def test_acepta_fechas_vacias(self):
        formulario = FiltroReporteForm(data={})

        self.assertTrue(formulario.is_valid())

from django.test import TestCase
from django.urls import reverse

from cuentas.models import Usuario


class AccesoReportesTests(TestCase):
    def test_visitante_es_redirigido_al_login(self):
        url = reverse("reportes:panel")
        respuesta = self.client.get(url)

        self.assertRedirects(
            respuesta,
            f"{reverse('cuentas:login')}?next={url}",
        )

    def test_bibliotecario_puede_entrar(self):
        usuario = Usuario.objects.create_user(
            username="bibliotecario_reportes",
            tipo_usuario="BIBLIOTECARIO",
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("reportes:panel"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "reportes/panel.html")

    def test_lectores_no_pueden_entrar(self):
        for rol in ("ESTUDIANTE", "PROFESOR"):
            with self.subTest(rol=rol):
                usuario = Usuario.objects.create_user(
                    username=f"lector_{rol.lower()}",
                    email=f"{rol.lower()}@example.com",
                    tipo_usuario=rol,
                )
                self.client.force_login(usuario)

                respuesta = self.client.get(reverse("reportes:panel"))

                self.assertEqual(respuesta.status_code, 403)