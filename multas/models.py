from django.conf import settings
from django.db import models
from django.utils import timezone


class Multa(models.Model):
    class Motivo(models.TextChoices):
        RETRASO = "RETRASO"
        DANIO = "DANIO"
        PERDIDA = "PERDIDA"

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE"
        PAGADA = "PAGADA"
        CONDONADA = "CONDONADA"

    prestamo = models.ForeignKey("prestamos.Prestamo", on_delete=models.PROTECT, related_name="multas")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="multas")
    motivo = models.CharField(max_length=10, choices=Motivo.choices)
    dias_retraso = models.PositiveSmallIntegerField(default=0)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    fecha_generacion = models.DateTimeField(default=timezone.now)
    justificacion_condonacion = models.CharField(max_length=255, null=True, blank=True)
    condonada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="multas_condonadas"
    )

    class Meta:
        db_table = "multa"
        constraints = [
            models.CheckConstraint(condition=models.Q(monto__gt=0), name="ck_multa_monto"),
            models.CheckConstraint(
                condition=models.Q(motivo__in=["RETRASO", "DANIO", "PERDIDA"]), name="ck_multa_motivo"
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=["PENDIENTE", "PAGADA", "CONDONADA"]), name="ck_multa_estado"
            ),
        ]

    def __str__(self):
        return f"Multa {self.pk} ({self.estado})"


class Pago(models.Model):
    class Metodo(models.TextChoices):
        EFECTIVO = "EFECTIVO"
        TARJETA = "TARJETA"
        TRANSFERENCIA = "TRANSFERENCIA"

    multa = models.ForeignKey(Multa, on_delete=models.PROTECT, related_name="pagos")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=15, choices=Metodo.choices)
    folio_recibo = models.CharField(max_length=30, unique=True)
    fecha_pago = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pagos_registrados"
    )

    class Meta:
        db_table = "pago"
        constraints = [
            models.CheckConstraint(condition=models.Q(monto__gt=0), name="ck_pago_monto"),
            models.CheckConstraint(
                condition=models.Q(metodo__in=["EFECTIVO", "TARJETA", "TRANSFERENCIA"]), name="ck_pago_metodo"
            ),
        ]

    def __str__(self):
        return f"Pago {self.folio_recibo}"
