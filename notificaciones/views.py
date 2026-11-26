"""CU-15: el usuario consulta sus notificaciones (RNF-02: solo las suyas)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from notificaciones.services import marcar_todas_leidas

POR_PAGINA = 20


@login_required
def mis_notificaciones(request):
    notificaciones = request.user.notificaciones.order_by("-fecha", "-pk")
    page_obj = Paginator(notificaciones, POR_PAGINA).get_page(request.GET.get("page"))
    return render(
        request,
        "notificaciones/mis_notificaciones.html",
        {
            "notificaciones": page_obj.object_list,
            "page_obj": page_obj,
            "sin_leer": notificaciones.filter(leida=False).count(),
        },
    )


@login_required
@require_POST
def marcar_leidas(request):
    total = marcar_todas_leidas(request.user)
    if total:
        messages.success(request, f"Se marcaron {total} notificación(es) como leídas.")
    return redirect("notificaciones:mis_notificaciones")
