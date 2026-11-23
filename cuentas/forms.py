from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import Carrera, Departamento, Estudiante, Profesor, Usuario


class CrearUsuarioForm(UserCreationForm):
    matricula = forms.CharField(max_length=20, required=False)
    semestre = forms.IntegerField(
        min_value=1,
        max_value=12,
        required=False,
    )
    carrera = forms.ModelChoiceField(
        queryset=Carrera.objects.all(),
        required=False,
    )
    num_empleado = forms.CharField(
        label="Número de empleado",
        max_length=20,
        required=False,
    )
    departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        required=False,
    )

    class Meta:
        model = Usuario
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "tipo_usuario",
            "telefono",
        )

    def clean(self):
        datos = super().clean()
        rol = datos.get("tipo_usuario")

        if rol == Usuario.TipoUsuario.ESTUDIANTE:
            obligatorios = ("matricula", "semestre", "carrera")
        elif rol == Usuario.TipoUsuario.PROFESOR:
            obligatorios = ("num_empleado", "departamento")
        else:
            obligatorios = ()

        for campo in obligatorios:
            if not datos.get(campo) and campo not in self.errors:
                self.add_error(campo, "Este campo es obligatorio para el rol.")

        matricula = datos.get("matricula")
        if (
            rol == Usuario.TipoUsuario.ESTUDIANTE
            and matricula
            and Estudiante.objects.filter(matricula=matricula).exists()
        ):
            self.add_error("matricula", "Esta matrícula ya está registrada.")

        numero = datos.get("num_empleado")
        if (
            rol == Usuario.TipoUsuario.PROFESOR
            and numero
            and Profesor.objects.filter(num_empleado=numero).exists()
        ):
            self.add_error(
                "num_empleado",
                "Este número de empleado ya está registrado.",
            )

        return datos

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError(
                "Este formulario debe guardar juntos el usuario y su perfil."
            )

        usuario = super().save(commit=True)
        datos = self.cleaned_data

        if usuario.tipo_usuario == Usuario.TipoUsuario.ESTUDIANTE:
            Estudiante.objects.create(
                usuario=usuario,
                matricula=datos["matricula"],
                semestre=datos["semestre"],
                carrera=datos["carrera"],
            )
        elif usuario.tipo_usuario == Usuario.TipoUsuario.PROFESOR:
            Profesor.objects.create(
                usuario=usuario,
                num_empleado=datos["num_empleado"],
                departamento=datos["departamento"],
            )

        return usuario


class EditarUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = (
            "first_name",
            "last_name",
            "email",
            "telefono",
        )

class BloquearUsuarioForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo del bloqueo",
        max_length=255,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
class ImportarUsuariosForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo CSV",
        help_text="Selecciona un CSV en UTF-8, separado por comas.",
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]

        if not archivo.name.lower().endswith(".csv"):
            raise forms.ValidationError("Selecciona un archivo .csv.")

        if archivo.size > 2 * 1024 * 1024:
            raise forms.ValidationError(
                "El archivo no puede superar 2 MB."
            )

        return archivo