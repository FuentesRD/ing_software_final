# Migración de datos: políticas de préstamo predeterminadas (RN-01 a RN-06).
# Es el único lugar del código con estos valores; el resto los lee de la tabla politica_prestamo.

from decimal import Decimal

from django.db import migrations

POLITICAS_INICIALES = [
    {
        "tipo_usuario": "ESTUDIANTE",
        "dias_prestamo": 7,
        "max_libros": 3,
        "max_renovaciones": 1,
        "multa_por_dia": Decimal("10.00"),
        "multa_maxima": Decimal("300.00"),
        "horas_para_recoger": 48,
    },
    {
        "tipo_usuario": "PROFESOR",
        "dias_prestamo": 30,
        "max_libros": 10,
        "max_renovaciones": 2,
        "multa_por_dia": Decimal("10.00"),
        "multa_maxima": Decimal("300.00"),
        "horas_para_recoger": 48,
    },
]


def crear_politicas(apps, schema_editor):
    PoliticaPrestamo = apps.get_model("prestamos", "PoliticaPrestamo")
    for datos in POLITICAS_INICIALES:
        PoliticaPrestamo.objects.update_or_create(
            tipo_usuario=datos["tipo_usuario"], defaults=datos
        )


def borrar_politicas(apps, schema_editor):
    PoliticaPrestamo = apps.get_model("prestamos", "PoliticaPrestamo")
    PoliticaPrestamo.objects.filter(
        tipo_usuario__in=[datos["tipo_usuario"] for datos in POLITICAS_INICIALES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('prestamos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_politicas, borrar_politicas),
    ]
