"""Genera el diccionario de datos en Markdown a partir de los modelos.

    python manage.py diccionario_datos --salida docs/bd/diccionario_datos.md

Los tipos salen de la conexión a MySQL, así que coinciden con lo que crean
las migraciones. La descripción de cada columna es el verbose_name del campo.
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, models
from django.db.models.fields import NOT_PROVIDED

APPS_DEL_DOMINIO = ["cuentas", "catalogo", "prestamos", "multas", "notificaciones"]


def _tipo(campo):
    """Tipo tal como lo muestra MySQL (bool → tinyint(1), numeric → decimal)."""
    tipo = (campo.db_type(connection) or "").lower()
    if tipo == "bool":
        return "tinyint(1)"
    return tipo.replace("numeric", "decimal").replace(", ", ",")


OPERADORES = {"in": "IN", "gte": ">=", "lte": "<=", "gt": ">", "lt": "<"}


def _condicion(q):
    """Convierte Q(estado__in=[...]) en «estado IN (...)» para leerlo fácil."""
    partes = []
    for hijo in q.children:
        if not isinstance(hijo, tuple):
            return str(q)
        consulta, valor = hijo
        campo, _, operador = consulta.partition("__")
        operador = OPERADORES.get(operador or "exact", "=")
        if isinstance(valor, (list, tuple)):
            valor = "(" + ", ".join(f"'{v}'" for v in valor) + ")"
        partes.append(f"{campo} {operador} {valor}")
    return f" {q.connector} ".join(partes)


def _llave(campo):
    if campo.primary_key and campo.is_relation:
        return f"PK, FK → {campo.related_model._meta.db_table}"
    if campo.primary_key:
        return "PK"
    if campo.is_relation:
        return f"FK → {campo.related_model._meta.db_table}"
    if campo.unique:
        return "UQ"
    if campo.db_index:
        return "Índice"
    return ""


def _default(campo):
    if getattr(campo, "auto_now_add", False):
        return "fecha y hora al crear"
    if getattr(campo, "auto_now", False):
        return "fecha y hora al guardar"
    if campo.default is NOT_PROVIDED:
        return ""
    if callable(campo.default):
        return f"{campo.default.__name__}()"
    return repr(campo.default)


def _descripcion(campo):
    if campo.primary_key and not campo.is_relation:
        return "Identificador"
    texto = str(campo.verbose_name).capitalize()
    if campo.choices:
        valores = " · ".join(str(valor) for valor, _ in campo.choices)
        texto += f". Valores: {valores}"
    return texto


def _resumen_modelo(modelo):
    doc = (modelo.__doc__ or "").strip()
    # Django inventa un docstring "Modelo(campo, ...)" si la clase no tiene uno.
    if not doc or doc.startswith(f"{modelo.__name__}("):
        return ""
    return doc.splitlines()[0]


class Command(BaseCommand):
    help = "Escribe el diccionario de datos de las tablas del dominio en Markdown."

    def add_arguments(self, parser):
        parser.add_argument("--salida", help="Archivo .md; si no, se imprime.")

    def handle(self, *args, **opciones):
        lineas = [
            "# Diccionario de datos",
            "",
            "Generado con `python manage.py diccionario_datos` a partir de los "
            "modelos de Django (tipos de MySQL).",
            "",
        ]
        for etiqueta in APPS_DEL_DOMINIO:
            for modelo in apps.get_app_config(etiqueta).get_models():
                lineas += self._tabla(modelo)

        texto = "\n".join(lineas) + "\n"
        if opciones["salida"]:
            with open(opciones["salida"], "w", encoding="utf-8") as archivo:
                archivo.write(texto)
            self.stdout.write(self.style.SUCCESS(f"Escrito en {opciones['salida']}"))
        else:
            self.stdout.write(texto)

    def _tabla(self, modelo):
        meta = modelo._meta
        lineas = [f"## `{meta.db_table}`", ""]
        resumen = _resumen_modelo(modelo)
        if resumen:
            lineas += [resumen, ""]
        lineas += [
            f"Modelo: `{meta.label}`",
            "",
            "| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |",
            "|---|---|---|---|---|---|",
        ]
        for campo in meta.local_concrete_fields:
            lineas.append(
                f"| `{campo.column}` | {_tipo(campo)} | "
                f"{'Sí' if campo.null else 'No'} | {_llave(campo)} | "
                f"{_default(campo)} | {_descripcion(campo)} |"
            )

        restricciones = [
            c for c in meta.constraints
            if isinstance(c, (models.CheckConstraint, models.UniqueConstraint))
        ]
        if restricciones:
            lineas += ["", "Restricciones:", ""]
            for restriccion in restricciones:
                if isinstance(restriccion, models.UniqueConstraint):
                    columnas = ", ".join(restriccion.fields)
                    lineas.append(f"- `{restriccion.name}`: UNIQUE ({columnas})")
                else:
                    condicion = _condicion(restriccion.condition)
                    lineas.append(f"- `{restriccion.name}`: CHECK ({condicion})")
        if meta.indexes:
            lineas += ["", "Índices compuestos:", ""]
            for indice in meta.indexes:
                lineas.append(f"- `{indice.name}`: ({', '.join(indice.fields)})")
        lineas.append("")
        return lineas