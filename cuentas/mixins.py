from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Usuario


class RolRequeridoMixin(LoginRequiredMixin):
    roles_permitidos = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if (
            not request.user.is_active
            or request.user.tipo_usuario not in self.roles_permitidos
        ):
            raise PermissionDenied(
                "No tienes permiso para acceder a esta página."
            )

        return super().dispatch(request, *args, **kwargs)


class BibliotecarioRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = (
        Usuario.TipoUsuario.BIBLIOTECARIO,
    )


class LectorRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = (
        Usuario.TipoUsuario.ESTUDIANTE,
        Usuario.TipoUsuario.PROFESOR,
    )


class ProfesorRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = (
        Usuario.TipoUsuario.PROFESOR,
    )