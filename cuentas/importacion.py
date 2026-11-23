import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from .forms import CrearUsuarioForm
from .models import Usuario


COLUMNAS_CSV = (
    "username",
    "first_name",
    "last_name",
    "email",
    "tipo_usuario",
    "telefono",
    "password1",
    "password2",
    "matricula",
    "semestre",
    "carrera",
    "num_empleado",
    "departamento",
)


def leer_csv_usuarios(archivo):
    try:
        contenido = archivo.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError("El archivo debe estar codificado en UTF-8.")

    lector = csv.DictReader(
        io.StringIO(contenido, newline=""),
        strict=True,
    )
    filas = []

    try:
        if lector.fieldnames != list(COLUMNAS_CSV):
            raise ValidationError(
                "Las columnas deben aparecer en este orden: "
                + ",".join(COLUMNAS_CSV)
            )

        for numero, fila in enumerate(lector, start=2):
            if None in fila or any(valor is None for valor in fila.values()):
                raise ValidationError(
                    f"Fila {numero}: cantidad de columnas incorrecta."
                )

            filas.append((numero, fila))

    except csv.Error:
        raise ValidationError("El archivo contiene un formato CSV inválido.")

    if not filas:
        raise ValidationError("El archivo no contiene usuarios.")

    return filas


@transaction.atomic
def importar_usuarios_csv(*, responsable, archivo):
    if (
        not responsable.is_authenticated
        or not responsable.is_active
        or responsable.tipo_usuario != Usuario.TipoUsuario.BIBLIOTECARIO
    ):
        raise PermissionDenied(
            "Solo el bibliotecario puede importar usuarios."
        )

    filas = leer_csv_usuarios(archivo)
    errores = []
    creados = 0

    for numero, datos in filas:
        formulario = CrearUsuarioForm(data=datos)

        if not formulario.is_valid():
            for campo, mensajes in formulario.errors.items():
                for mensaje in mensajes:
                    errores.append(f"Fila {numero}, {campo}: {mensaje}")
            continue

        try:
            with transaction.atomic():
                formulario.save()
        except IntegrityError:
            errores.append(
                f"Fila {numero}: un dato único está duplicado "
                "o una referencia dejó de existir."
            )
        else:
            creados += 1

    if errores:
        raise ValidationError(errores)

    return creados