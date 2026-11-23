from django.conf import settings
from django.db import models
from django.utils import timezone


class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        VENCE_PRONTO = "VENCE_PRONTO"
        VENCIDO = "VENCIDO"
        RESERVA_DISPONIBLE = "RESERVA_DISPONIBLE"
        MULTA = "MULTA"
        GENERAL = "GENERAL"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    mensaje = models.CharField(max_length=500)
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notificacion"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tipo__in=["VENCE_PRONTO", "VENCIDO", "RESERVA_DISPONIBLE", "MULTA", "GENERAL"]),
                name="ck_notificacion_tipo",
            )
        ]

    def __str__(self):
        return f"{self.tipo} para {self.usuario_id}"
