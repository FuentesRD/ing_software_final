"""Vistas de multas (paquete D). Solo orquestan: las reglas viven en multas/services.py."""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from cuentas.mixins import BibliotecarioRequeridoMixin
from multas.models import Multa, Pago
from multas.services import (
    condonar_multa,
    monto_adeudado,
    registrar_devolucion,
    registrar_pago,
    registrar_perdida_o_danio,
    saldo_de,
)

POR_PAGINA = 20

MOTIVOS_PERDIDA_DANIO = [
    (Multa.Motivo.DANIO, "Daño"),
    (Multa.Motivo.PERDIDA, "Pérdida"),
]


def _texto_error(exc):
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)


def _con_pagado(queryset):
    """Agrega a cada multa el total pagado, para mostrar su saldo sin una consulta por fila."""
    return queryset.annotate(
        pagado=Coalesce(
            Sum("pagos__monto"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )


@login_required
def mis_multas(request):
    """CU-14 / RNF-02: el usuario ve solo sus multas, sus pagos y lo que adeuda."""
    multas = _con_pagado(
        Multa.objects.filter(usuario=request.user)
        .select_related("prestamo__ejemplar__libro")
        .order_by("-fecha_generacion")
    )
    page_obj = Paginator(multas, POR_PAGINA).get_page(request.GET.get("page"))
    return render(
        request,
        "multas/mis_multas.html",
        {
            "multas": page_obj.object_list,
            "page_obj": page_obj,
            "total_adeudado": monto_adeudado(request.user),
        },
    )


class MultasListaView(BibliotecarioRequeridoMixin, ListView):
    """Listado de multas para el bibliotecario, con filtro por estado y búsqueda por lector."""

    template_name = "multas/lista.html"
    context_object_name = "multas"
    paginate_by = POR_PAGINA

    def get_queryset(self):
        self.estado = self.request.GET.get("estado", Multa.Estado.PENDIENTE)
        self.q = self.request.GET.get("q", "").strip()
        multas = Multa.objects.select_related("usuario", "prestamo__ejemplar__libro")
        if self.estado in Multa.Estado.values:
            multas = multas.filter(estado=self.estado)
        if self.q:
            multas = multas.filter(
                Q(usuario__username__icontains=self.q)
                | Q(usuario__first_name__icontains=self.q)
                | Q(usuario__last_name__icontains=self.q)
            )
        return _con_pagado(multas).order_by("-fecha_generacion")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update({"estado": self.estado, "q": self.q, "estados": Multa.Estado.values})
        return contexto


class RegistrarDevolucionView(BibliotecarioRequeridoMixin, View):
    """CU-25: lista los préstamos en curso y registra la devolución del que se elija."""

    template_name = "multas/registrar_devolucion.html"

    def get(self, request, prestamo_id=None):
        from prestamos.models import Prestamo

        q = request.GET.get("q", "").strip()
        prestamos = (
            Prestamo.objects.filter(estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO])
            .select_related("usuario", "ejemplar__libro")
            .order_by("fecha_vencimiento", "pk")
        )
        if prestamo_id:
            prestamos = prestamos.filter(pk=prestamo_id)
        if q:
            prestamos = prestamos.filter(
                Q(usuario__username__icontains=q)
                | Q(usuario__first_name__icontains=q)
                | Q(usuario__last_name__icontains=q)
                | Q(ejemplar__codigo_inventario__icontains=q)
                | Q(ejemplar__libro__titulo__icontains=q)
            )
        page_obj = Paginator(prestamos, POR_PAGINA).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {"prestamos": page_obj.object_list, "page_obj": page_obj, "q": q},
        )

    def post(self, request, prestamo_id=None):
        from prestamos.models import Prestamo

        prestamo = get_object_or_404(Prestamo, pk=prestamo_id or request.POST.get("prestamo_id"))
        try:
            multa = registrar_devolucion(prestamo=prestamo, recibido_por_usuario=request.user)
        except ValidationError as exc:
            messages.error(request, _texto_error(exc))
        else:
            texto = f"Devolución registrada para el préstamo {prestamo.pk}."
            if multa is not None:
                texto += f" Se generó una multa de ${multa.monto} por {multa.dias_retraso} día(s) de retraso."
            messages.success(request, texto)
        return redirect("multas:registrar_devolucion")


class RegistrarPerdidaDanioView(BibliotecarioRequeridoMixin, View):
    """CU-27 / RN-13: registra la pérdida o el daño de un ejemplar prestado y genera la multa."""

    template_name = "multas/registrar_perdida_dano.html"

    def _contexto(self, prestamo, motivo="", costo=None):
        return {
            "prestamo": prestamo,
            "motivos": MOTIVOS_PERDIDA_DANIO,
            "motivo": motivo,
            "costo": costo if costo is not None else prestamo.ejemplar.libro.costo_reposicion,
        }

    def _prestamo(self, prestamo_id):
        from prestamos.models import Prestamo

        return get_object_or_404(Prestamo.objects.select_related("usuario", "ejemplar__libro"), pk=prestamo_id)

    def get(self, request, prestamo_id=None):
        prestamo_id = prestamo_id or request.GET.get("prestamo_id")
        if not prestamo_id:
            messages.info(request, "Elige el préstamo en la lista de devoluciones.")
            return redirect("multas:registrar_devolucion")
        return render(request, self.template_name, self._contexto(self._prestamo(prestamo_id)))

    def post(self, request, prestamo_id=None):
        prestamo = self._prestamo(prestamo_id or request.POST.get("prestamo_id"))
        motivo = request.POST.get("motivo", "").strip()
        costo_texto = request.POST.get("costo_reposicion", "").strip()
        try:
            multa = registrar_perdida_o_danio(
                prestamo=prestamo,
                motivo=motivo,
                costo_reposicion=Decimal(costo_texto),
                recibido_por_usuario=request.user,
            )
        except (InvalidOperation, ValidationError) as exc:
            texto = "Ingresa un costo de reposición válido." if isinstance(exc, InvalidOperation) else _texto_error(exc)
            messages.error(request, texto)
            return render(request, self.template_name, self._contexto(prestamo, motivo, costo_texto))
        messages.success(request, f"Se generó la multa {multa.pk} por ${multa.monto}.")
        return redirect("multas:lista")


class RegistrarPagoView(BibliotecarioRequeridoMixin, View):
    """CU-28: registra un pago parcial o total sobre una multa pendiente."""

    template_name = "multas/registrar_pago.html"

    def get(self, request, multa_id):
        multa = get_object_or_404(Multa.objects.select_related("usuario"), pk=multa_id)
        return render(
            request,
            self.template_name,
            {
                "multa": multa,
                "pagos": multa.pagos.select_related("registrado_por").order_by("fecha_pago"),
                "saldo": saldo_de(multa),
                "metodos": Pago.Metodo.choices,
            },
        )

    def post(self, request, multa_id):
        multa = get_object_or_404(Multa, pk=multa_id)
        try:
            pago = registrar_pago(
                multa=multa,
                monto=Decimal(request.POST.get("monto", "").strip()),
                metodo=request.POST.get("metodo", "").strip(),
                folio_recibo=request.POST.get("folio_recibo", "").strip(),
                registrado_por_usuario=request.user,
            )
        except (InvalidOperation, ValidationError) as exc:
            texto = "Ingresa un monto válido." if isinstance(exc, InvalidOperation) else _texto_error(exc)
            messages.error(request, texto)
        else:
            messages.success(request, f"Pago registrado con folio {pago.folio_recibo}.")
        return redirect("multas:registrar_pago", multa_id=multa.pk)


class CondonarMultaView(BibliotecarioRequeridoMixin, View):
    """CU-29 / RN-14: condona una multa pendiente con justificación obligatoria."""

    template_name = "multas/condonar_multa.html"

    def get(self, request, multa_id):
        multa = get_object_or_404(Multa.objects.select_related("usuario"), pk=multa_id)
        return render(request, self.template_name, {"multa": multa, "saldo": saldo_de(multa)})

    def post(self, request, multa_id):
        multa = get_object_or_404(Multa, pk=multa_id)
        try:
            condonar_multa(
                multa=multa,
                justificacion=request.POST.get("justificacion", ""),
                condonada_por_usuario=request.user,
            )
        except ValidationError as exc:
            messages.error(request, _texto_error(exc))
            return redirect("multas:condonar_multa", multa_id=multa.pk)
        messages.success(request, f"La multa {multa.pk} fue condonada.")
        return redirect("multas:lista")
