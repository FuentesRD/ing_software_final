from django.core.paginator import Paginator
from django.db.models import Sum
from django.views.generic import FormView

from cuentas.mixins import BibliotecarioRequeridoMixin

from . import services
from .forms import FiltroReporteForm


class PanelReportesView(BibliotecarioRequeridoMixin, FormView):
    template_name = "reportes/panel.html"
    form_class = FiltroReporteForm
    http_method_names = ["get", "head", "options"]

    def get_form_kwargs(self):
        opciones = super().get_form_kwargs()
        opciones["data"] = self.request.GET
        return opciones

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        formulario = contexto["form"]

        if not formulario.is_valid():
            return contexto

        inicio = formulario.cleaned_data["fecha_inicio"]
        fin = formulario.cleaned_data["fecha_fin"]

        prestamos = services.prestamos_por_periodo(inicio, fin)
        libros = services.libros_mas_solicitados(inicio, fin)
        vencidos = services.prestamos_vencidos(inicio, fin)
        cobradas = services.multas_cobradas(inicio, fin)
        pendientes = services.multas_pendientes(inicio, fin)

        contexto["total_cobrado"] = cobradas.aggregate(
            total=Sum("monto", default=0),
        )["total"]
        contexto["total_pendiente"] = pendientes.aggregate(
            total=Sum("saldo_pendiente", default=0),
        )["total"]

        consultas = {
            "prestamos": prestamos,
            "libros": libros,
            "vencidos": vencidos,
            "cobradas": cobradas,
            "pendientes": pendientes,
        }

        parametros = self.request.GET.copy()
        for nombre in consultas:
            parametros.pop(f"pagina_{nombre}", None)
        contexto["filtros"] = parametros.urlencode()

        for nombre, consulta in consultas.items():
            contexto[nombre] = Paginator(consulta, 20).get_page(
                self.request.GET.get(f"pagina_{nombre}")
            )

        contexto["mostrar_resultados"] = True
        return contexto