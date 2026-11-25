from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from multas.models import Multa, Pago
from multas.services import (
    condonar_multa,
    monto_adeudado,
    registrar_devolucion,
    registrar_pago,
    registrar_perdida_o_danio,
)

try:
    from cuentas.mixins import BibliotecarioRequeridoMixin
except ImportError:
    class BibliotecarioRequeridoMixin(UserPassesTestMixin):
        def test_func(self):
            user = self.request.user
            return user.is_authenticated and (
                user.is_superuser or getattr(user, "tipo_usuario", None) == "BIBLIOTECARIO"
            )


@login_required
def mis_multas(request):
    """CU-14 / RNF-02: Muestra las multas y pagos del usuario autenticado."""
    multas = (
        Multa.objects.filter(usuario=request.user)
        .select_related("prestamo", "condonada_por")
        .prefetch_related("pagos")
        .order_by("-fecha_generacion")
    )
    total_adeudado = monto_adeudado(request.user)
    return render(
        request,
        "multas/mis_multas.html",
        {
            "multas": multas,
            "total_adeudado": total_adeudado,
        },
    )


class RegistrarDevolucionView(BibliotecarioRequeridoMixin, View):
    """CU-25: Registra la devolución física de un préstamo."""

    template_name = "multas/registrar_devolucion.html"

    def get(self, request, prestamo_id=None):
        from prestamos.models import Prestamo
        prestamo = get_object_or_404(Prestamo, pk=prestamo_id) if prestamo_id else None
        prestamos_activos = Prestamo.objects.filter(estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO]).select_related("usuario", "ejemplar")
        return render(
            request,
            self.template_name,
            {
                "prestamo": prestamo,
                "prestamos_activos": prestamos_activos,
            },
        )

    def post(self, request, prestamo_id=None):
        from prestamos.models import Prestamo
        id_objetivo = prestamo_id or request.POST.get("prestamo_id")
        prestamo = get_object_or_404(Prestamo, pk=id_objetivo)
        try:
            registrar_devolucion(prestamo=prestamo, recibido_por_usuario=request.user)
            messages.success(request, f"Devolución registrada para el préstamo #{prestamo.pk}.")
            return redirect("multas:registrar_devolucion")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("multas:registrar_devolucion")


class RegistrarPerdidaDanioView(BibliotecarioRequeridoMixin, View):
    """CU-27 / RN-13: Registra pérdida o daño de ejemplar y genera la multa correspondiente."""

    template_name = "multas/registrar_perdida_dano.html"

    def get(self, request, prestamo_id=None):
        from prestamos.models import Prestamo
        from prestamos.models import Prestamo
        prestamo = get_object_or_404(Prestamo, pk=prestamo_id) if prestamo_id else None
        return render(
            request,
            self.template_name,
            {
                "prestamo": prestamo,
                "motivos": [Multa.Motivo.DANIO, Multa.Motivo.PERDIDA],
            },
        )

    def post(self, request, prestamo_id=None):
        from prestamos.models import Prestamo
        id_objetivo = prestamo_id or request.POST.get("prestamo_id")
        prestamo = get_object_or_404(Prestamo, pk=id_objetivo)
        motivo = request.POST.get("motivo", "").strip()
        costo_raw = request.POST.get("costo_reposicion", "").strip()

        try:
            costo_reposicion = Decimal(costo_raw)
            multa = registrar_perdida_o_danio(
                prestamo=prestamo,
                motivo=motivo,
                costo_reposicion=costo_reposicion,
                recibido_por_usuario=request.user,
            )
            messages.success(
                request,
                f"Se registró {multa.get_motivo_display()} y se generó la multa #{multa.pk} por ${multa.monto}.",
            )
            return redirect("multas:mis_multas")
        except (InvalidOperation, ValidationError) as exc:
            msg = "Ingresa un costo de reposición válido." if isinstance(exc, InvalidOperation) else "; ".join(exc.messages)
            messages.error(request, msg)
            return render(
                request,
                self.template_name,
                {
                    "prestamo": prestamo,
                    "motivos": [Multa.Motivo.DANIO, Multa.Motivo.PERDIDA],
                },
            )


class RegistrarPagoView(BibliotecarioRequeridoMixin, View):
    """CU-28: Registra un pago parcial o total sobre una multa pendiente."""

    template_name = "multas/registrar_pago.html"

    def get(self, request, multa_id):
        multa = get_object_or_404(Multa.objects.select_related("usuario").prefetch_related("pagos"), pk=multa_id)
        pagado = sum((p.monto for p in multa.pagos.all()), Decimal("0.00"))
        saldo = max(multa.monto - pagado, Decimal("0.00"))
        return render(
            request,
            self.template_name,
            {
                "multa": multa,
                "saldo": saldo,
                "metodos": Pago.Metodo.choices,
            },
        )

    def post(self, request, multa_id):
        multa = get_object_or_404(Multa, pk=multa_id)
        monto_raw = request.POST.get("monto", "").strip()
        metodo = request.POST.get("metodo", "").strip()
        folio_recibo = request.POST.get("folio_recibo", "").strip()

        try:
            monto = Decimal(monto_raw)
            pago = registrar_pago(
                multa=multa,
                monto=monto,
                metodo=metodo,
                folio_recibo=folio_recibo,
                registrado_por_usuario=request.user,
            )
            messages.success(request, f"Pago registrado con folio {pago.folio_recibo}.")
            return redirect("multas:registrar_pago", multa_id=multa.pk)
        except (InvalidOperation, ValidationError) as exc:
            msg = "Ingresa un monto válido." if isinstance(exc, InvalidOperation) else "; ".join(exc.messages)
            messages.error(request, msg)
            return redirect("multas:registrar_pago", multa_id=multa.pk)


class CondonarMultaView(BibliotecarioRequeridoMixin, View):
    """CU-29 / RN-14: Condona una multa pendiente con justificación obligatoria."""

    template_name = "multas/condonar_multa.html"

    def get(self, request, multa_id):
        multa = get_object_or_404(Multa.objects.select_related("usuario"), pk=multa_id)
        return render(request, self.template_name, {"multa": multa})

    def post(self, request, multa_id):
        multa = get_object_or_404(Multa, pk=multa_id)
        justificacion = request.POST.get("justificacion", "")
        try:
            condonar_multa(
                multa=multa,
                justificacion=justificacion,
                condonada_por_usuario=request.user,
            )
            messages.success(request, f"La multa #{multa.pk} fue condonada.")
            return redirect("multas:condonar_multa", multa_id=multa.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("multas:condonar_multa", multa_id=multa.pk)