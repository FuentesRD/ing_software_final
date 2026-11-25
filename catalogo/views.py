"""Vistas de catalogo. Las reglas viven en services.py; aquí solo se orquesta."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Case, ProtectedError, When
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from cuentas.mixins import BibliotecarioRequeridoMixin, ProfesorRequeridoMixin
from cuentas.models import Profesor, Usuario

from . import services
from .forms import (
    BusquedaLibrosForm,
    EjemplarForm,
    LibroForm,
    ResponderSugerenciaForm,
    SugerenciaForm,
)
from .models import (
    Autor,
    Categoria,
    Editorial,
    Ejemplar,
    Libro,
    SugerenciaAdquisicion,
)


def _es_bibliotecario(usuario):
    return usuario.tipo_usuario == Usuario.TipoUsuario.BIBLIOTECARIO


def _url_o_none(nombre, *args):
    """URL de otra app si ya existe; None mientras su dueño no la publique."""
    try:
        return reverse(nombre, args=args)
    except NoReverseMatch:
        return None


# --- CU-04 / CU-05: búsqueda y detalle (todos los usuarios) ---------------------


class BuscarLibrosView(LoginRequiredMixin, ListView):
    template_name = "catalogo/buscar.html"
    context_object_name = "libros"
    paginate_by = 20

    def get_queryset(self):
        self.form = BusquedaLibrosForm(self.request.GET or None)
        filtros = self.form.cleaned_data if self.form.is_valid() else {}
        return services.buscar_libros(
            texto=filtros.get("q", ""),
            criterio=filtros.get("criterio") or "todo",
            categoria=filtros.get("categoria"),
            editorial=filtros.get("editorial"),
            solo_disponibles=filtros.get("solo_disponibles", False),
            incluir_bajas=_es_bibliotecario(self.request.user),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        parametros = self.request.GET.copy()
        parametros.pop("page", None)
        contexto["form"] = self.form or BusquedaLibrosForm()
        contexto["filtros"] = parametros.urlencode()
        contexto["es_bibliotecario"] = _es_bibliotecario(self.request.user)
        return contexto


class DetalleLibroView(LoginRequiredMixin, DetailView):
    template_name = "catalogo/detalle.html"
    context_object_name = "libro"

    def get_queryset(self):
        consulta = Libro.objects.select_related("categoria", "editorial")
        if _es_bibliotecario(self.request.user):
            return consulta
        return consulta.filter(activo=True)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        libro = self.object
        usuario = self.request.user
        disponibles = libro.ejemplares_disponibles().count()
        contexto.update(
            {
                "autores": services.autores_de(libro),
                "ejemplares": libro.ejemplares.all(),
                "disponibles": disponibles,
                "es_bibliotecario": _es_bibliotecario(usuario),
                "es_lector": usuario.tipo_usuario
                in (Usuario.TipoUsuario.ESTUDIANTE, Usuario.TipoUsuario.PROFESOR),
                # Vistas de prestamos (paquete C): aparecen cuando existan.
                "url_solicitar": _url_o_none("prestamos:solicitar", libro.pk),
                "url_reservar": _url_o_none("prestamos:reservar", libro.pk),
            }
        )
        return contexto


# --- CU-17: libros (bibliotecario) --------------------------------------------------


class CrearLibroView(BibliotecarioRequeridoMixin, CreateView):
    model = Libro
    form_class = LibroForm
    template_name = "catalogo/formulario.html"
    extra_context = {"titulo": "Nuevo libro"}

    def form_valid(self, form):
        messages.success(
            self.request, "Libro registrado. Ahora agrega sus ejemplares."
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("catalogo:detalle", args=[self.object.pk])


class EditarLibroView(BibliotecarioRequeridoMixin, UpdateView):
    model = Libro
    form_class = LibroForm
    template_name = "catalogo/formulario.html"
    extra_context = {"titulo": "Editar libro"}

    def form_valid(self, form):
        messages.success(self.request, "Libro actualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("catalogo:detalle", args=[self.object.pk])


class BajaLibroView(BibliotecarioRequeridoMixin, View):
    """POST: baja lógica del libro; con ?reactivar=1 lo vuelve a activar."""

    def post(self, request, pk):
        libro = get_object_or_404(Libro, pk=pk)
        if request.POST.get("reactivar"):
            services.reactivar_libro(libro)
            messages.success(request, "El libro volvió al catálogo.")
        else:
            try:
                services.dar_de_baja_libro(libro)
                messages.success(request, "Libro dado de baja.")
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        return redirect("catalogo:detalle", pk=pk)


# --- CU-18: ejemplares (bibliotecario) ----------------------------------------------


class CrearEjemplarView(BibliotecarioRequeridoMixin, CreateView):
    model = Ejemplar
    form_class = EjemplarForm
    template_name = "catalogo/formulario.html"

    def dispatch(self, request, *args, **kwargs):
        self.libro = get_object_or_404(Libro, pk=kwargs["libro_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = f"Nuevo ejemplar de «{self.libro}»"
        return contexto

    def form_valid(self, form):
        form.instance.libro = self.libro
        messages.success(self.request, "Ejemplar registrado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("catalogo:detalle", args=[self.libro.pk])


class EditarEjemplarView(BibliotecarioRequeridoMixin, UpdateView):
    model = Ejemplar
    form_class = EjemplarForm
    template_name = "catalogo/formulario.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = f"Editar ejemplar {self.object.codigo_inventario}"
        return contexto

    def form_valid(self, form):
        messages.success(self.request, "Ejemplar actualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("catalogo:detalle", args=[self.object.libro_id])


# --- CU-19: autores, editoriales y categorías (bibliotecario) ---------------------
# Las tres pantallas son iguales; cada clase solo dice qué modelo y campos usa.


class _CatalogoSimpleMixin(BibliotecarioRequeridoMixin):
    lista_url = None  # nombre de la URL del listado

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["opciones"] = self.model._meta
        contexto["lista_url"] = self.lista_url
        contexto["prefijo"] = self.lista_url.removesuffix("_lista")
        return contexto

    def get_success_url(self):
        return reverse(self.lista_url)


class _ListaSimple(_CatalogoSimpleMixin, ListView):
    template_name = "catalogo/simple_lista.html"
    paginate_by = 25


class _CrearSimple(_CatalogoSimpleMixin, CreateView):
    template_name = "catalogo/formulario.html"

    def form_valid(self, form):
        nombre = self.model._meta.verbose_name.capitalize()
        messages.success(self.request, f"{nombre} registrado(a).")
        return super().form_valid(form)


class _EditarSimple(_CatalogoSimpleMixin, UpdateView):
    template_name = "catalogo/formulario.html"

    def form_valid(self, form):
        messages.success(self.request, "Cambios guardados.")
        return super().form_valid(form)


class _EliminarSimple(_CatalogoSimpleMixin, DeleteView):
    """Solo borra si nadie lo usa; si tiene libros, PROTECT lo impide."""

    template_name = "catalogo/simple_eliminar.html"

    def form_valid(self, form):
        try:
            respuesta = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "No se puede eliminar: hay libros que lo usan.",
            )
            return redirect(self.lista_url)
        messages.success(self.request, "Registro eliminado.")
        return respuesta


CAMPOS_AUTOR = ["nombre", "apellidos", "nacionalidad"]
CAMPOS_EDITORIAL = ["nombre", "pais"]
CAMPOS_CATEGORIA = ["nombre", "descripcion"]


class AutorListaView(_ListaSimple):
    model, lista_url = Autor, "catalogo:autor_lista"


class AutorCrearView(_CrearSimple):
    model, fields, lista_url = Autor, CAMPOS_AUTOR, "catalogo:autor_lista"


class AutorEditarView(_EditarSimple):
    model, fields, lista_url = Autor, CAMPOS_AUTOR, "catalogo:autor_lista"


class AutorEliminarView(_EliminarSimple):
    model, lista_url = Autor, "catalogo:autor_lista"


class EditorialListaView(_ListaSimple):
    model, lista_url = Editorial, "catalogo:editorial_lista"


class EditorialCrearView(_CrearSimple):
    model, fields, lista_url = Editorial, CAMPOS_EDITORIAL, "catalogo:editorial_lista"


class EditorialEditarView(_EditarSimple):
    model, fields, lista_url = Editorial, CAMPOS_EDITORIAL, "catalogo:editorial_lista"


class EditorialEliminarView(_EliminarSimple):
    model, lista_url = Editorial, "catalogo:editorial_lista"


class CategoriaListaView(_ListaSimple):
    model, lista_url = Categoria, "catalogo:categoria_lista"


class CategoriaCrearView(_CrearSimple):
    model, fields, lista_url = Categoria, CAMPOS_CATEGORIA, "catalogo:categoria_lista"


class CategoriaEditarView(_EditarSimple):
    model, fields, lista_url = Categoria, CAMPOS_CATEGORIA, "catalogo:categoria_lista"


class CategoriaEliminarView(_EliminarSimple):
    model, lista_url = Categoria, "catalogo:categoria_lista"


# --- CU-16 / CU-33: sugerencias de adquisición -----------------------------------


class SugerirLibroView(ProfesorRequeridoMixin, CreateView):
    """El profesor envía una sugerencia y ve las que ya envió (CU-16)."""

    model = SugerenciaAdquisicion
    form_class = SugerenciaForm
    template_name = "catalogo/sugerencias_profesor.html"
    success_url = reverse_lazy("catalogo:sugerir")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["mis_sugerencias"] = SugerenciaAdquisicion.objects.filter(
            profesor__usuario=self.request.user
        )
        return contexto

    def form_valid(self, form):
        form.instance.profesor = get_object_or_404(
            Profesor, usuario=self.request.user
        )
        messages.success(self.request, "Sugerencia enviada a la biblioteca.")
        return super().form_valid(form)


class SugerenciasListaView(BibliotecarioRequeridoMixin, ListView):
    """Bandeja del bibliotecario: primero las pendientes (CU-33)."""

    template_name = "catalogo/sugerencias_lista.html"
    context_object_name = "sugerencias"
    paginate_by = 20

    def get_queryset(self):
        pendientes_primero = Case(
            When(estado=SugerenciaAdquisicion.Estado.PENDIENTE, then=0),
            default=1,
        )
        return SugerenciaAdquisicion.objects.select_related(
            "profesor__usuario"
        ).order_by(pendientes_primero, "-fecha")


class ResponderSugerenciaView(BibliotecarioRequeridoMixin, FormView):
    form_class = ResponderSugerenciaForm
    template_name = "catalogo/sugerencia_responder.html"
    success_url = reverse_lazy("catalogo:sugerencias_lista")

    def dispatch(self, request, *args, **kwargs):
        self.sugerencia = get_object_or_404(SugerenciaAdquisicion, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["sugerencia"] = self.sugerencia
        return contexto

    def form_valid(self, form):
        try:
            services.responder_sugerencia(
                self.sugerencia,
                form.cleaned_data["estado"],
                form.cleaned_data["respuesta"],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "Respuesta registrada.")
        return super().form_valid(form)