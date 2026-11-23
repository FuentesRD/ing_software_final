from django import forms


class FiltroReporteForm(forms.Form):
    fecha_inicio = forms.DateField(
        label="Desde",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_fin = forms.DateField(
        label="Hasta",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        datos = super().clean()
        inicio = datos.get("fecha_inicio")
        fin = datos.get("fecha_fin")

        if inicio and fin and inicio > fin:
            self.add_error(
                "fecha_fin",
                "La fecha final debe ser igual o posterior a la inicial.",
            )

        return datos