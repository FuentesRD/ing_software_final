"""Vistas de la app prestamos (paquete C).

Las vistas solo orquestan: buscan los objetos, llaman a prestamos/services.py y muestran el
resultado con messages. Las reglas de negocio viven en los servicios y en los modelos.
Toda acción que cambia estado usa POST (http_method_names = ["post"]).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from catalogo.models import Libro
from cuentas.mixins import LectorRequeridoMixin

from . import services
from .models import Prestamo, Reserva

POR_PAGINA = 10  # RNF-05


def _mostrar_errores(request, error):
    """Pasa a messages cada motivo de un ValidationError (UsuarioNoElegible trae varios)."""
    for mensaje in error.messages:
        messages.error(request, mensaje)


class AccionPostView(View):
    """Base de las acciones que cambian estado: solo POST, llama al servicio y redirige.

    Las subclases implementan `ejecutar()` (devuelve el mensaje de éxito) y `url_destino()`.
    Los errores de negocio de los servicios son ValidationError (UsuarioNoElegible,
    OperacionNoPermitida, SinEjemplaresDisponibles, TransicionInvalida).
    """

    http_method_names = ["post"]

    def ejecutar(self):
        raise NotImplementedError

    def url_destino(self):
        raise NotImplementedError

    def url_si_falla(self):
        return self.url_destino()

    def post(self, request, *args, **kwargs):
        try:
            mensaje = self.ejecutar()
        except ValidationError as error:
            _mostrar_errores(request, error)
            return redirect(self.url_si_falla())
        messages.success(request, mensaje)
        return redirect(self.url_destino())


# --- Lector: solicitar y reservar (CU-06, CU-11) ---------------------------------------

class LibroAccionMixin:
    """Busca el libro activo de la URL (`libro_id`)."""

    def get_libro(self):
        if not hasattr(self, "_libro"):
            self._libro = get_object_or_404(Libro, pk=self.kwargs["libro_id"], activo=True)
        return self._libro


class SolicitarPrestamoView(LectorRequeridoMixin, LibroAccionMixin, TemplateView):
    """CU-06: GET confirma el libro; POST llama a solicitar_prestamo()."""

    template_name = "prestamos/solicitar.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        libro = self.get_libro()
        contexto["libro"] = libro
        contexto["hay_disponibles"] = libro.ejemplares_disponibles().exists()
        return contexto

    def post(self, request, *args, **kwargs):
        libro = self.get_libro()
        try:
            prestamo = services.solicitar_prestamo(request.user, libro)
        except ValidationError as error:
            _mostrar_errores(request, error)
            return redirect("prestamos:solicitar", libro_id=libro.pk)
        messages.success(
            request,
            f"Solicitaste «{libro}». Recoge el ejemplar "
            f"{prestamo.ejemplar.codigo_inventario} en la biblioteca.",
        )
        return redirect("prestamos:mis_prestamos")


class ReservarLibroView(LectorRequeridoMixin, LibroAccionMixin, TemplateView):
    """CU-11: GET confirma el libro; POST llama a reservar_libro()."""

    template_name = "prestamos/reservar.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        libro = self.get_libro()
        contexto["libro"] = libro
        contexto["hay_disponibles"] = libro.ejemplares_disponibles().exists()
        return contexto

    def post(self, request, *args, **kwargs):
        libro = self.get_libro()
        try:
            reserva = services.reservar_libro(request.user, libro)
        except ValidationError as error:
            _mostrar_errores(request, error)
            return redirect("prestamos:reservar", libro_id=libro.pk)
        messages.success(
            request,
            f"Reservaste «{libro}». Tu lugar en la fila es el "
            f"{services.posicion_en_cola(reserva)}.",
        )
        return redirect("prestamos:mis_reservas")


# --- Lector: mis préstamos (CU-08, CU-09, CU-10) ---------------------------------------

class MisPrestamosView(LectorRequeridoMixin, ListView):
    template_name = "prestamos/mis_prestamos.html"
    context_object_name = "prestamos"
    paginate_by = POR_PAGINA

    def get_queryset(self):
        return services.prestamos_de(self.request.user)


class PrestamoDelLectorMixin(LectorRequeridoMixin):
    """RNF-02: el préstamo debe ser del lector; si no, 404."""

    def get_prestamo(self):
        return get_object_or_404(Prestamo, pk=self.kwargs["pk"], usuario=self.request.user)

    def url_destino(self):
        return reverse("prestamos:mis_prestamos")


class RenovarPrestamoView(PrestamoDelLectorMixin, AccionPostView):
    def ejecutar(self):
        prestamo = services.renovar_prestamo(self.get_prestamo(), self.request.user)
        return (
            f"Renovaste «{prestamo.ejemplar.libro}». Nueva fecha de devolución: "
            f"{prestamo.fecha_vencimiento:%d/%m/%Y}."
        )


class CancelarSolicitudView(PrestamoDelLectorMixin, AccionPostView):
    def ejecutar(self):
        prestamo = services.cancelar_solicitud(self.get_prestamo(), self.request.user)
        return f"Cancelaste tu solicitud de «{prestamo.ejemplar.libro}»."


# --- Lector: mis reservas (CU-12) ------------------------------------------------------

class MisReservasView(LectorRequeridoMixin, ListView):
    template_name = "prestamos/mis_reservas.html"
    context_object_name = "reservas"
    paginate_by = POR_PAGINA

    def get_queryset(self):
        return services.reservas_de(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        for reserva in contexto["reservas"]:
            reserva.posicion = services.posicion_en_cola(reserva)
        return contexto


class CancelarReservaView(LectorRequeridoMixin, AccionPostView):
    def ejecutar(self):
        reserva = get_object_or_404(Reserva, pk=self.kwargs["pk"], usuario=self.request.user)
        reserva = services.cancelar_reserva(reserva, self.request.user)
        return f"Cancelaste tu reserva de «{reserva.libro}»."

    def url_destino(self):
        return reverse("prestamos:mis_reservas")
