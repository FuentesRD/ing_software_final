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