from django.test import TestCase

from .forms import CrearUsuarioForm
from .models import Carrera, Departamento, Estudiante, Profesor, Usuario


class CrearUsuarioFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(
            clave="ISW",
            nombre="Ingeniería de Software",
        )
        cls.departamento = Departamento.objects.create(
            nombre="Ingeniería",
        )

    def datos_base(self, rol):
        return {
            "username": "cuenta_prueba",
            "email": "cuenta@example.com",
            "tipo_usuario": rol,
            "password1": "ClaveTemporalParaPruebas839!",
            "password2": "ClaveTemporalParaPruebas839!",
        }

    def test_crea_estudiante_con_perfil(self):
        datos = self.datos_base("ESTUDIANTE")
        datos.update({
            "matricula": "A001",
            "semestre": 3,
            "carrera": self.carrera.pk,
        })
        formulario = CrearUsuarioForm(data=datos)

        self.assertTrue(formulario.is_valid(), formulario.errors)
        usuario = formulario.save()
        perfil = Estudiante.objects.get(usuario=usuario)

        self.assertEqual(perfil.matricula, "A001")
        self.assertEqual(perfil.carrera, self.carrera)
        self.assertTrue(
            usuario.check_password(datos["password1"])
        )
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_crea_profesor_con_perfil(self):
        datos = self.datos_base("PROFESOR")
        datos.update({
            "num_empleado": "P001",
            "departamento": self.departamento.pk,
        })
        formulario = CrearUsuarioForm(data=datos)

        self.assertTrue(formulario.is_valid(), formulario.errors)
        usuario = formulario.save()
        perfil = Profesor.objects.get(usuario=usuario)

        self.assertEqual(perfil.num_empleado, "P001")
        self.assertEqual(perfil.departamento, self.departamento)

    def test_estudiante_exige_datos_academicos(self):
        formulario = CrearUsuarioForm(
            data=self.datos_base("ESTUDIANTE")
        )

        self.assertFalse(formulario.is_valid())
        for campo in ("matricula", "semestre", "carrera"):
            self.assertIn(campo, formulario.errors)

        self.assertFalse(
            Usuario.objects.filter(username="cuenta_prueba").exists()
        )