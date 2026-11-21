from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class TipoUsuario(models.TextChoices):
        ESTUDIANTE = "ESTUDIANTE", "Estudiante"
        PROFESOR = "PROFESOR", "Profesor"
        BIBLIOTECARIO = "BIBLIOTECARIO", "Bibliotecario"

    email = models.EmailField(unique=True)
    tipo_usuario = models.CharField(
        max_length=15,
        choices=TipoUsuario.choices,
        db_index=True,
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )
    bloqueado = models.BooleanField(default=False)
    motivo_bloqueo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "usuario"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    tipo_usuario__in=[
                        "ESTUDIANTE",
                        "PROFESOR",
                        "BIBLIOTECARIO",
                    ]
                ),
                name="ck_usuario_tipo",
            ),
        ]


class Carrera(models.Model):
    clave = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=120)

    class Meta:
        db_table = "carrera"

    def __str__(self):
        return self.nombre


class Departamento(models.Model):
    nombre = models.CharField(max_length=120, unique=True)

    class Meta:
        db_table = "departamento"

    def __str__(self):
        return self.nombre


class Estudiante(models.Model):
    usuario = models.OneToOneField(
        "cuentas.Usuario",
        on_delete=models.CASCADE,
        primary_key=True,
    )
    matricula = models.CharField(max_length=20, unique=True)
    semestre = models.PositiveSmallIntegerField()
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.PROTECT,
    )

    class Meta:
        db_table = "estudiante"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    semestre__gte=1,
                    semestre__lte=12,
                ),
                name="ck_estudiante_semestre",
            ),
        ]

    def __str__(self):
        return self.matricula


class Profesor(models.Model):
    usuario = models.OneToOneField(
        "cuentas.Usuario",
        on_delete=models.CASCADE,
        primary_key=True,
    )
    num_empleado = models.CharField(max_length=20, unique=True)
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.PROTECT,
    )

    class Meta:
        db_table = "profesor"

    def __str__(self):
        return self.num_empleado