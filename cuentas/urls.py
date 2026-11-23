from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "cuentas"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path(
        "usuarios/",
        views.ListaUsuariosView.as_view(),
        name="usuarios_lista",
    ),
    path(
        "usuarios/nuevo/",
        views.CrearUsuarioView.as_view(),
        name="usuario_crear",
    ),
    path(
        "usuarios/<int:pk>/editar/",
        views.EditarUsuarioView.as_view(),
        name="usuario_editar",
    ),
    path(
        "usuarios/<int:pk>/desactivar/",
        views.CambiarEstadoUsuarioView.as_view(),
        {"activar": False},
        name="usuario_desactivar",
    ),
    path(
        "usuarios/<int:pk>/reactivar/",
        views.CambiarEstadoUsuarioView.as_view(),
        {"activar": True},
        name="usuario_reactivar",
    ),
    path(
        "usuarios/<int:pk>/bloquear/",
        views.BloquearUsuarioView.as_view(),
        name="usuario_bloquear",
    ),
    path(
        "usuarios/<int:pk>/desbloquear/",
        views.DesbloquearUsuarioView.as_view(),
        name="usuario_desbloquear",
    ),
    path(
        "usuarios/importar/",
        views.ImportarUsuariosView.as_view(),
        name="usuarios_importar",
    ),
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