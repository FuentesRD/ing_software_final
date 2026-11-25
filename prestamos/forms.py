"""Formularios de prestamos: solo validan la entrada y buscan objetos; las reglas están en services.py."""

from django import forms
from django.contrib.auth import get_user_model

from catalogo.models import Ejemplar

from .models import PoliticaPrestamo, Reserva
from .services import CAMPOS_EDITABLES_POLITICA


class PrestamoMostradorForm(forms.Form):
    """CU-24: identifica al lector y al ejemplar; prestar_en_mostrador() decide si procede."""

    username = forms.CharField(
        label="Usuario del lector",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    codigo_inventario = forms.CharField(
        label="Código de inventario del ejemplar",
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        try:
            return get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            raise forms.ValidationError("No existe un usuario con ese nombre de usuario.")

    def clean_codigo_inventario(self):
        codigo = self.cleaned_data["codigo_inventario"].strip()
        try:
            return Ejemplar.objects.select_related("libro").get(codigo_inventario=codigo)
        except Ejemplar.DoesNotExist:
            raise forms.ValidationError("No existe un ejemplar con ese código de inventario.")


class FiltroReservasForm(forms.Form):
    """CU-30: filtro opcional por estado en la lista de reservas."""

    estado = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=[("", "Todos")] + list(Reserva.Estado.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class PoliticaPrestamoForm(forms.ModelForm):
    """CU-31: los campos editables de una política; actualizar_politica() hace la validación final."""

    class Meta:
        model = PoliticaPrestamo
        fields = CAMPOS_EDITABLES_POLITICA

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")
