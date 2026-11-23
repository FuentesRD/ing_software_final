from django.urls import path

from .views import PanelReportesView

app_name = "reportes"

urlpatterns = [
    path("", PanelReportesView.as_view(), name="panel"),
]