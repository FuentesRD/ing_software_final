from django.views.generic import FormView

from cuentas.mixins import BibliotecarioRequeridoMixin

from .forms import FiltroReporteForm


class PanelReportesView(BibliotecarioRequeridoMixin, FormView):
    template_name = "reportes/panel.html"
    form_class = FiltroReporteForm

    def get_form_kwargs(self):
        opciones = super().get_form_kwargs()
        opciones["data"] = self.request.GET or None
        return opciones