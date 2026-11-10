from django.contrib import admin

from .models import PoliticaPrestamo, Prestamo, Reserva


@admin.register(PoliticaPrestamo)
class PoliticaPrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_usuario", "dias_prestamo", "max_libros", "max_renovaciones",
        "multa_por_dia", "multa_maxima", "horas_para_recoger", "actualizado_en",
    )

    def has_add_permission(self, request):
        # Hay una política por tipo de lector; se cargan con la migración de datos.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "ejemplar", "estado", "fecha_solicitud", "fecha_vencimiento")
    list_filter = ("estado",)
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name")
    raw_id_fields = ("usuario", "ejemplar", "entregado_por", "recibido_por")
    date_hierarchy = "fecha_solicitud"

    def has_delete_permission(self, request, obj=None):
        # RN-16: los préstamos nunca se borran.
        return False


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "libro", "estado", "fecha_reserva", "fecha_expiracion")
    list_filter = ("estado",)
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name")
    raw_id_fields = ("usuario", "libro", "ejemplar_asignado")

    def has_delete_permission(self, request, obj=None):
        # Se conserva el historial de reservas, igual que el de préstamos.
        return False
