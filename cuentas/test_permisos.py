from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.views import View

from .mixins import (
    BibliotecarioRequeridoMixin,
    LectorRequeridoMixin,
    ProfesorRequeridoMixin,
)
from .models import Usuario


class VistaPrueba(View):
    def get(self, request):
        return HttpResponse("Acceso permitido")


class VistaBibliotecario(BibliotecarioRequeridoMixin, VistaPrueba):
    pass


class VistaLector(LectorRequeridoMixin, VistaPrueba):
    pass


class VistaProfesor(ProfesorRequeridoMixin, VistaPrueba):
    pass


class PermisosTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def solicitar(self, vista, usuario):
        request = self.factory.get("/")
        request.user = usuario
        return vista.as_view()(request)

    def test_sin_sesion_redirige_al_login(self):
        for vista in (VistaBibliotecario, VistaLector, VistaProfesor):
            with self.subTest(vista=vista.__name__):
                respuesta = self.solicitar(vista, AnonymousUser())
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.url, "/login/?next=/")

    def test_acceso_segun_rol(self):
        casos = (
            (VistaBibliotecario, {"BIBLIOTECARIO"}),
            (VistaLector, {"ESTUDIANTE", "PROFESOR"}),
            (VistaProfesor, {"PROFESOR"}),
        )

        for vista, permitidos in casos:
            for rol in Usuario.TipoUsuario.values:
                with self.subTest(vista=vista.__name__, rol=rol):
                    usuario = Usuario(tipo_usuario=rol, is_active=True)

                    if rol in permitidos:
                        respuesta = self.solicitar(vista, usuario)
                        self.assertEqual(respuesta.status_code, 200)
                    else:
                        with self.assertRaises(PermissionDenied):
                            self.solicitar(vista, usuario)

    def test_usuario_inactivo_no_puede_acceder(self):
        casos = (
            (VistaBibliotecario, "BIBLIOTECARIO"),
            (VistaLector, "ESTUDIANTE"),
            (VistaProfesor, "PROFESOR"),
        )

        for vista, rol in casos:
            with self.subTest(vista=vista.__name__):
                usuario = Usuario(tipo_usuario=rol, is_active=False)
                with self.assertRaises(PermissionDenied):
                    self.solicitar(vista, usuario)