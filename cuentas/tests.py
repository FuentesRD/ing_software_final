from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from .models import Carrera, Departamento, Estudiante, Profesor, Usuario


class ModelosCuentasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(
            clave="ISW",
            nombre="Ingeniería de Software",
        )
        cls.departamento = Departamento.objects.create(
            nombre="Ingeniería",
        )

    def crear_usuario(self, nombre, tipo):
        return Usuario.objects.create_user(
            username=nombre,
            email=f"{nombre}@example.com",
            tipo_usuario=tipo,
        )

    def test_estudiante_comparte_clave_primaria_con_usuario(self):
        usuario = self.crear_usuario("alumno", "ESTUDIANTE")
        estudiante = Estudiante.objects.create(
            usuario=usuario,
            matricula="A001",
            semestre=1,
            carrera=self.carrera,
        )
        self.assertEqual(estudiante.pk, usuario.pk)

    def test_profesor_comparte_clave_primaria_con_usuario(self):
        usuario = self.crear_usuario("docente", "PROFESOR")
        profesor = Profesor.objects.create(
            usuario=usuario,
            num_empleado="P001",
            departamento=self.departamento,
        )
        self.assertEqual(profesor.pk, usuario.pk)

    def test_rechaza_semestres_fuera_del_rango(self):
        usuario = self.crear_usuario("alumno", "ESTUDIANTE")
        for semestre in (0, 13):
            with self.subTest(semestre=semestre):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Estudiante.objects.create(
                            usuario=usuario,
                            matricula="A001",
                            semestre=semestre,
                            carrera=self.carrera,
                        )

    def test_no_permite_matriculas_duplicadas(self):
        primero = self.crear_usuario("alumno1", "ESTUDIANTE")
        segundo = self.crear_usuario("alumno2", "ESTUDIANTE")
        Estudiante.objects.create(
            usuario=primero,
            matricula="A001",
            semestre=1,
            carrera=self.carrera,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Estudiante.objects.create(
                    usuario=segundo,
                    matricula="A001",
                    semestre=2,
                    carrera=self.carrera,
                )

    def test_protege_carrera_con_estudiantes(self):
        usuario = self.crear_usuario("alumno", "ESTUDIANTE")
        Estudiante.objects.create(
            usuario=usuario,
            matricula="A001",
            semestre=1,
            carrera=self.carrera,
        )
        with self.assertRaises(ProtectedError):
            self.carrera.delete()

    def test_protege_departamento_con_profesores(self):
        usuario = self.crear_usuario("docente", "PROFESOR")
        Profesor.objects.create(
            usuario=usuario,
            num_empleado="P001",
            departamento=self.departamento,
        )
        with self.assertRaises(ProtectedError):
            self.departamento.delete()