from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Carrera, Departamento, Estudiante, Profesor, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos de biblioteca", {
            "fields": (
                "tipo_usuario",
                "telefono",
                "bloqueado",
                "motivo_bloqueo",
            ),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos de biblioteca", {
            "fields": ("email", "tipo_usuario", "telefono"),
        }),
    )
    list_display = (
        "username",
        "email",
        "tipo_usuario",
        "bloqueado",
        "is_active",
    )
    list_filter = UserAdmin.list_filter + ("tipo_usuario", "bloqueado")


admin.site.register(Carrera)
admin.site.register(Departamento)
admin.site.register(Estudiante)
admin.site.register(Profesor)