from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import CrearUsuarioForm, EditarUsuarioForm
from .mixins import BibliotecarioRequeridoMixin
from .models import Usuario
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView

from .services import cambiar_estado_cuenta


@login_required
def inicio(request):
    if request.user.tipo_usuario == Usuario.TipoUsuario.BIBLIOTECARIO:
        return redirect("cuentas:usuarios_lista")

    return render(request, "cuentas/inicio.html")


class ListaUsuariosView(BibliotecarioRequeridoMixin, ListView):
    model = Usuario
    template_name = "cuentas/usuarios_lista.html"
    context_object_name = "usuarios"
    paginate_by = 20
    ordering = ["username"]


class CrearUsuarioView(BibliotecarioRequeridoMixin, CreateView):
    form_class = CrearUsuarioForm
    template_name = "cuentas/usuario_formulario.html"
    success_url = reverse_lazy("cuentas:usuarios_lista")


class EditarUsuarioView(BibliotecarioRequeridoMixin, UpdateView):
    model = Usuario
    form_class = EditarUsuarioForm
    template_name = "cuentas/usuario_editar.html"
    success_url = reverse_lazy("cuentas:usuarios_lista")

class CambiarEstadoUsuarioView(
    BibliotecarioRequeridoMixin,
    DetailView,
):
    model = Usuario
    template_name = "cuentas/usuario_estado.html"
    context_object_name = "cuenta"

    def post(self, request, *args, **kwargs):
        cuenta = self.get_object()

        try:
            cambiar_estado_cuenta(
                responsable=request.user,
                usuario_id=cuenta.pk,
                activar=self.kwargs["activar"],
            )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        except Usuario.DoesNotExist:
            raise Http404("El usuario ya no existe.")
        else:
            messages.success(request, "Estado de la cuenta actualizado.")

        return redirect("cuentas:usuarios_lista")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["activar"] = self.kwargs["activar"]
        return contexto