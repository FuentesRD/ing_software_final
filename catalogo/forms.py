"""Formularios de catalogo: búsqueda, acervo y sugerencias."""
from django import forms

from .models import (
    Autor,
    Categoria,
    Editorial,
    Ejemplar,
    Libro,
    SugerenciaAdquisicion,
)
from .services import ESTADOS_MANUALES


class EstiloBootstrapMixin:
    """Agrega las clases de Bootstrap a cada campo del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                clase = "form-select"
            else:
                clase = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {clase}".strip()


class BusquedaLibrosForm(EstiloBootstrapMixin, forms.Form):
    """Filtros de la búsqueda del catálogo (CU-04, RF-02)."""

    CRITERIOS = [
        ("todo", "Todo"),
        ("titulo", "Título"),
        ("autor", "Autor"),
        ("isbn", "ISBN"),
    ]

    q = forms.CharField(label="Buscar", required=False, max_length=255)
    criterio = forms.ChoiceField(
        label="Buscar en", choices=CRITERIOS, required=False
    )
    categoria = forms.ModelChoiceField(
        label="Categoría",
        queryset=Categoria.objects.all(),
        required=False,
        empty_label="Todas",
    )
    editorial = forms.ModelChoiceField(
        label="Editorial",
        queryset=Editorial.objects.all(),
        required=False,
        empty_label="Todas",
    )
    solo_disponibles = forms.BooleanField(
        label="Solo con ejemplares disponibles", required=False
    )


class LibroForm(EstiloBootstrapMixin, forms.ModelForm):
    """Alta y edición de libros (CU-17)."""

    autores = forms.ModelMultipleChoiceField(
        label="Autores",
        queryset=Autor.objects.all(),
        help_text="Mantén presionado Ctrl para elegir varios.",
    )

    class Meta:
        model = Libro
        fields = [
            "isbn",
            "titulo",
            "subtitulo",
            "autores",
            "categoria",
            "editorial",
            "anio_publicacion",
            "edicion",
            "idioma",
            "num_paginas",
            "descripcion",
            "portada",
            "costo_reposicion",
        ]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}


class EjemplarForm(EstiloBootstrapMixin, forms.ModelForm):
    """Alta y edición de ejemplares (CU-18).

    El bibliotecario solo asigna DISPONIBLE, EN_REPARACION o BAJA. Un
    ejemplar prestado, reservado o perdido no cambia de estado desde aquí.
    """

    class Meta:
        model = Ejemplar
        fields = [
            "codigo_inventario",
            "estado",
            "ubicacion",
            "fecha_adquisicion",
            "observaciones",
        ]
        widgets = {"fecha_adquisicion": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        manuales = [
            (valor, etiqueta)
            for valor, etiqueta in Ejemplar.Estado.choices
            if valor in ESTADOS_MANUALES
        ]
        estado_actual = self.instance.estado if self.instance.pk else None
        if estado_actual and estado_actual not in ESTADOS_MANUALES:
            self.fields["estado"].disabled = True
            self.fields["estado"].help_text = (
                "Este estado lo controla préstamos o multas."
            )
        else:
            self.fields["estado"].choices = manuales


class SugerenciaForm(EstiloBootstrapMixin, forms.ModelForm):
    """El profesor sugiere la compra de un libro (CU-16)."""

    class Meta:
        model = SugerenciaAdquisicion
        fields = ["titulo", "autores", "isbn", "justificacion"]
        widgets = {"justificacion": forms.Textarea(attrs={"rows": 4})}


class ResponderSugerenciaForm(EstiloBootstrapMixin, forms.Form):
    """El bibliotecario aprueba o rechaza una sugerencia (CU-33)."""

    estado = forms.ChoiceField(
        label="Decisión",
        choices=[
            (SugerenciaAdquisicion.Estado.APROBADA, "Aprobar"),
            (SugerenciaAdquisicion.Estado.RECHAZADA, "Rechazar"),
        ],
        widget=forms.RadioSelect,
    )
    respuesta = forms.CharField(label="Respuesta al profesor", max_length=255)