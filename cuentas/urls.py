from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "cuentas"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="cuentas/login.html",
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="cuentas/recuperar.html",
            email_template_name="cuentas/recuperar_email.txt",
            subject_template_name="cuentas/recuperar_asunto.txt",
            success_url=reverse_lazy("cuentas:recuperar_enviado"),
        ),
        name="recuperar",
    ),
    path(
        "recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="cuentas/recuperar_enviado.html",
        ),
        name="recuperar_enviado",
    ),
    path(
        "restablecer/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="cuentas/restablecer.html",
            success_url=reverse_lazy("cuentas:restablecer_completo"),
        ),
        name="restablecer",
    ),
    path(
        "restablecer/completo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="cuentas/restablecer_completo.html",
        ),
        name="restablecer_completo",
    ),
]