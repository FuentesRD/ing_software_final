"""Datos mínimos para las pruebas de prestamos.

La creación de libros y ejemplares vive solo aquí: si cambian los modelos de catalogo (paquete B),
se ajusta este archivo y no cada prueba.
"""

from django.contrib.auth import get_user_model

from catalogo.models import Categoria, Editorial, Ejemplar, Libro


def crear_usuario(username, tipo_usuario="ESTUDIANTE"):
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@escuela.mx",
        password="clave-de-prueba",
        tipo_usuario=tipo_usuario,
    )


def crear_libro(isbn="9780000000001", titulo="Libro de prueba"):
    categoria, _ = Categoria.objects.get_or_create(nombre="Categoría de prueba")
    editorial, _ = Editorial.objects.get_or_create(nombre="Editorial de prueba")
    return Libro.objects.create(isbn=isbn, titulo=titulo, categoria=categoria, editorial=editorial)


def crear_ejemplar(libro, codigo_inventario):
    return Ejemplar.objects.create(libro=libro, codigo_inventario=codigo_inventario)
