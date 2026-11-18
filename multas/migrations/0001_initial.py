import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("prestamos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Multa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("motivo", models.CharField(choices=[("RETRASO", "Retraso"), ("DANIO", "Danio"), ("PERDIDA", "Perdida")], max_length=10)),
                ("dias_retraso", models.PositiveSmallIntegerField(default=0)),
                ("monto", models.DecimalField(decimal_places=2, max_digits=10)),
                ("estado", models.CharField(choices=[("PENDIENTE", "Pendiente"), ("PAGADA", "Pagada"), ("CONDONADA", "Condonada")], db_index=True, default="PENDIENTE", max_length=10)),
                ("fecha_generacion", models.DateTimeField(default=django.utils.timezone.now)),
                ("justificacion_condonacion", models.CharField(blank=True, max_length=255, null=True)),
                ("condonada_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="multas_condonadas", to=settings.AUTH_USER_MODEL)),
                ("prestamo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="multas", to="prestamos.prestamo")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="multas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "multa",
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("monto__gt", 0)), name="ck_multa_monto"),
                    models.CheckConstraint(condition=models.Q(("motivo__in", ["RETRASO", "DANIO", "PERDIDA"])), name="ck_multa_motivo"),
                    models.CheckConstraint(condition=models.Q(("estado__in", ["PENDIENTE", "PAGADA", "CONDONADA"])), name="ck_multa_estado"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Pago",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("monto", models.DecimalField(decimal_places=2, max_digits=10)),
                ("metodo", models.CharField(choices=[("EFECTIVO", "Efectivo"), ("TARJETA", "Tarjeta"), ("TRANSFERENCIA", "Transferencia")], max_length=15)),
                ("folio_recibo", models.CharField(max_length=30, unique=True)),
                ("fecha_pago", models.DateTimeField(default=django.utils.timezone.now)),
                ("multa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pagos", to="multas.multa")),
                ("registrado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pagos_registrados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "pago",
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("monto__gt", 0)), name="ck_pago_monto"),
                    models.CheckConstraint(condition=models.Q(("metodo__in", ["EFECTIVO", "TARJETA", "TRANSFERENCIA"])), name="ck_pago_metodo"),
                ],
            },
        ),
    ]
