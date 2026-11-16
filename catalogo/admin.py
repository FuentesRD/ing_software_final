"""Registro de los modelos de catalogo en el sitio de administración.

El admin es para cargar y revisar datos durante el desarrollo; las funciones
del bibliotecario tendrán sus propias vistas (CU-17, CU-18, CU-19).
"""
from django.contrib import admin
from django.db.models import Count, Q

from .models import Autor, Categoria, Editorial, Ejemplar, Libro, LibroAutor


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "descripcion"]
    search_fields = ["nombre"]


@admin.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ["nombre", "pais"]
    search_fields = ["nombre"]


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ["apellidos", "nombre", "nacionalidad"]
    search_fields = ["apellidos", "nombre"]


class LibroAutorInline(admin.TabularInline):
    """Autores del libro, editables dentro de la página del libro."""

    model = LibroAutor
    extra = 1
    autocomplete_fields = ["autor"]


class EjemplarInline(admin.TabularInline):
    """Ejemplares del libro, editables dentro de la página del libro."""

    model = Ejemplar
    extra = 0
    fields = ["codigo_inventario", "estado", "ubicacion", "fecha_adquisicion"]


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = [
        "titulo",
        "isbn",
        "categoria",
        "editorial",
        "total_ejemplares",
        "disponibles",
        "activo",
    ]
    list_filter = ["activo", "categoria", "editorial", "idioma"]
    search_fields = ["titulo", "isbn", "autores__apellidos"]
    list_select_related = ["categoria", "editorial"]
    autocomplete_fields = ["categoria", "editorial"]
    inlines = [LibroAutorInline, EjemplarInline]

    def get_queryset(self, request):
        # Cuenta los ejemplares en la misma consulta del listado.
        return super().get_queryset(request).annotate(
            _total=Count("ejemplares", distinct=True),
            _disponibles=Count(
                "ejemplares",
                filter=Q(ejemplares__estado=Ejemplar.Estado.DISPONIBLE),
                distinct=True,
            ),
        )

    @admin.display(description="ejemplares", ordering="_total")
    def total_ejemplares(self, obj):
        return obj._total

    @admin.display(description="disponibles", ordering="_disponibles")
    def disponibles(self, obj):
        return obj._disponibles


@admin.register(Ejemplar)
class EjemplarAdmin(admin.ModelAdmin):
    list_display = ["codigo_inventario", "libro", "estado", "ubicacion"]
    list_filter = ["estado"]
    search_fields = ["codigo_inventario", "libro__titulo", "libro__isbn"]
    list_select_related = ["libro"]
    autocomplete_fields = ["libro"]