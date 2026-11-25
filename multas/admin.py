from django.contrib import admin

from multas.models import Multa, Pago


@admin.register(Multa)
class MultaAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "prestamo", "motivo", "monto", "estado", "fecha_generacion")
    list_filter = ("estado", "motivo")
    search_fields = ("usuario__username", "usuario__email", "id")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("folio_recibo", "multa", "monto", "metodo", "fecha_pago", "registrado_por")
    list_filter = ("metodo",)
    search_fields = ("folio_recibo", "multa__usuario__username")

    def has_delete_permission(self, request, obj=None):
        return False