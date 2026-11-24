"""Carga datos de prueba para todo el sistema.

    python manage.py cargar_datos_prueba
    python manage.py cargar_datos_prueba --libros 10000   # además, prueba de RNF-05

Cada app carga sus propios datos. Para sumar los de otra app, basta con que
esa app tenga un módulo datos_prueba.py con una función cargar() que reciba
nada y devuelva un dict {"nombre": cantidad_creada}. Este comando la llama
si existe (ver APPS_OPCIONALES).
"""
from importlib import import_module

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.datos_prueba import (
    cargar_catalogo,
    cargar_sugerencias,
    generar_libros_masivos,
)
from cuentas.datos_prueba import CONTRASENA_PRUEBA, cargar_usuarios
from cuentas.models import Profesor

# En este orden: préstamos necesita libros y usuarios; multas, préstamos.
APPS_OPCIONALES = ["prestamos", "multas", "notificaciones"]


class Command(BaseCommand):
    help = "Carga datos de prueba: usuarios, catálogo y lo que aporte cada app."

    def add_arguments(self, parser):
        parser.add_argument(
            "--libros",
            type=int,
            default=0,
            help="Libros sintéticos extra para medir rendimiento (p. ej. 10000).",
        )

    def handle(self, *args, **opciones):
        with transaction.atomic():
            self._mostrar("Usuarios", cargar_usuarios())
            self._mostrar("Catálogo", cargar_catalogo())
            profesores = list(Profesor.objects.order_by("num_empleado"))
            self._mostrar("Sugerencias", cargar_sugerencias(profesores))

            for app in APPS_OPCIONALES:
                modulo = f"{app}.datos_prueba"
                try:
                    datos = import_module(modulo)
                except ModuleNotFoundError as error:
                    if error.name != modulo:
                        raise  # el módulo existe pero falla al importar algo
                    self.stdout.write(f"  {app}: sin datos de prueba todavía")
                    continue
                self._mostrar(app.capitalize(), datos.cargar())

            if opciones["libros"]:
                self._mostrar(
                    "Carga masiva", generar_libros_masivos(opciones["libros"])
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Listo. Usuarios: biblio1, prof1..prof5, est01..est20 "
                f"(contraseña: {CONTRASENA_PRUEBA})"
            )
        )

    def _mostrar(self, titulo, creados):
        detalle = ", ".join(f"{nombre}: {n}" for nombre, n in creados.items())
        self.stdout.write(f"  {titulo} → nuevos {detalle}")