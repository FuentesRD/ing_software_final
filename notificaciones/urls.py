from django.urls import path

from notificaciones import views

app_name = "notificaciones"

urlpatterns = [
    path("", views.mis_notificaciones, name="mis_notificaciones"),
    path("marcar-leidas/", views.marcar_leidas, name="marcar_leidas"),
]
