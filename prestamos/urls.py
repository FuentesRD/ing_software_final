from django.urls import path

from . import views

app_name = "prestamos"

urlpatterns = [
    # Lector
    path("libro/<int:libro_id>/solicitar/", views.SolicitarPrestamoView.as_view(), name="solicitar"),
    path("libro/<int:libro_id>/reservar/", views.ReservarLibroView.as_view(), name="reservar"),
    path("mis-prestamos/", views.MisPrestamosView.as_view(), name="mis_prestamos"),
    path("mis-prestamos/<int:pk>/renovar/", views.RenovarPrestamoView.as_view(), name="renovar"),
    path(
        "mis-prestamos/<int:pk>/cancelar/",
        views.CancelarSolicitudView.as_view(),
        name="cancelar_solicitud",
    ),
    path("mis-reservas/", views.MisReservasView.as_view(), name="mis_reservas"),
    path(
        "mis-reservas/<int:pk>/cancelar/",
        views.CancelarReservaView.as_view(),
        name="cancelar_reserva",
    ),
]
