from django.urls import path

from multas import views

app_name = "multas"

urlpatterns = [
    path("mis-multas/", views.mis_multas, name="mis_multas"),
    path("devolucion/", views.RegistrarDevolucionView.as_view(), name="registrar_devolucion"),
    path("devolucion/<int:prestamo_id>/", views.RegistrarDevolucionView.as_view(), name="registrar_devolucion_prestamo"),
    path("perdida-danio/", views.RegistrarPerdidaDanioView.as_view(), name="registrar_perdida_danio"),
    path(
        "perdida-danio/<int:prestamo_id>/",
        views.RegistrarPerdidaDanioView.as_view(),
        name="registrar_perdida_danio_prestamo",
    ),
    path("<int:multa_id>/pagar/", views.RegistrarPagoView.as_view(), name="registrar_pago"),
    path("<int:multa_id>/condonar/", views.CondonarMultaView.as_view(), name="condonar_multa"),
]