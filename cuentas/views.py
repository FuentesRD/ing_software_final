from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import CrearUsuarioForm
from .mixins import BibliotecarioRequeridoMixin
from .models import Usuario


@login_required
def inicio(request):
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