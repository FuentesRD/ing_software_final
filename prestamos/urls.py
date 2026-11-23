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
    # Bibliotecario
    path("solicitudes/", views.SolicitudesPendientesView.as_view(), name="solicitudes"),
    path("solicitudes/<int:pk>/entregar/", views.EntregarPrestamoView.as_view(), name="entregar"),
    path("mostrador/", views.PrestamoMostradorView.as_view(), name="mostrador"),
    path("reservas/", views.ReservasView.as_view(), name="reservas"),
    path("reservas/<int:pk>/recoger/", views.RecogerReservaView.as_view(), name="recoger_reserva"),
    path(
        "reservas/<int:pk>/cancelar/",
        views.CancelarReservaBibliotecarioView.as_view(),
        name="cancelar_reserva_bibliotecario",
    ),
    path("politicas/", views.PoliticasView.as_view(), name="politicas"),
    path("politicas/<int:pk>/editar/", views.EditarPoliticaView.as_view(), name="politica_editar"),
]
