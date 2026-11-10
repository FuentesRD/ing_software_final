"""Servicios de la app prestamos: reglas de negocio que usan varias apps.

Las otras apps se usan solo a través de los contratos de PLAN_DE_TRABAJO.md (sección 3):
Libro.ejemplares_disponibles(), Ejemplar.es_prestable(), tiene_multas_pendientes() y notificar().

Las operaciones que cambian préstamos, reservas o ejemplares corren en transaction.atomic() y
bloquean las filas con select_for_update() (RNF-03), siempre en el mismo orden para evitar
bloqueos cruzados: usuario → préstamo → ejemplar → reserva.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from catalogo.models import Ejemplar
from notificaciones.services import notificar

from .models import PoliticaPrestamo, Prestamo, Reserva


class UsuarioNoElegible(ValidationError):
    """El usuario no cumple CU-07; `motivos` trae la lista de razones para mostrarle."""

    def __init__(self, motivos):
        super().__init__(motivos)
        self.motivos = list(motivos)


class SinEjemplaresDisponibles(ValidationError):
    """No hay un ejemplar que se pueda prestar (RN-15); se puede ofrecer reservar."""


class OperacionNoPermitida(ValidationError):
    """La operación no procede: falta de permiso, plazo vencido o ejemplar no apto."""


# --- Estado del ejemplar -------------------------------------------------------------
# Único lugar que lee o escribe Ejemplar.estado. Es provisional: cuando catalogo (Diego)
# ofrezca un contrato para cambiar el estado, solo se ajusta esta sección.

_ESTADOS_NO_ASIGNABLES = {
    Ejemplar.Estado.EN_REPARACION,
    Ejemplar.Estado.PERDIDO,
    Ejemplar.Estado.BAJA,
}


def _cambiar_estado_ejemplar(ejemplar, estado):
    ejemplar.estado = estado
    ejemplar.save(update_fields=["estado"])


def _ejemplar_asignable(ejemplar):
    """Un ejemplar devuelto o liberado puede apartarse si no está dañado, perdido ni dado de baja."""
    return ejemplar.estado not in _ESTADOS_NO_ASIGNABLES


# --- Utilidades internas -------------------------------------------------------------

def _bloquear_usuario(usuario):
    return get_user_model().objects.select_for_update().get(pk=usuario.pk)


def _validar_bibliotecario(usuario):
    if usuario is None or usuario.tipo_usuario != "BIBLIOTECARIO":
        raise OperacionNoPermitida("Solo un bibliotecario puede registrar la entrega de un préstamo.")


def _formato_fecha(fecha_hora):
    return timezone.localtime(fecha_hora).strftime("%d/%m/%Y %H:%M")


def _tomar_ejemplar_disponible(libro):
    """Bloquea y devuelve un ejemplar prestable del libro (RN-15)."""
    for ejemplar in libro.ejemplares_disponibles().select_for_update().order_by("pk"):
        # Se vuelve a revisar con el contrato: otro usuario pudo tomarlo mientras esperábamos el bloqueo.
        if ejemplar.es_prestable():
            return ejemplar
    raise SinEjemplaresDisponibles(
        f"Ya no hay ejemplares disponibles de «{libro}». Puedes reservarlo."
    )


# --- Consultas -----------------------------------------------------------------------

def tiene_prestamos_vencidos(usuario):
    """RN-08: ¿el usuario tiene algún préstamo vencido? (contrato C → C, D).

    Cuenta los préstamos en estado VENCIDO y también los ACTIVOS cuya fecha de vencimiento
    ya pasó, aunque el comando de vencimientos (CU-34) todavía no los haya marcado.
    """
    hoy = timezone.localdate()
    return Prestamo.objects.filter(
        Q(estado=Prestamo.Estado.VENCIDO)
        | Q(estado=Prestamo.Estado.ACTIVO, fecha_vencimiento__lt=hoy),
        usuario=usuario,
    ).exists()


def verificar_elegibilidad(usuario, libro=None, excluir=None):
    """CU-07: motivos por los que `usuario` no puede pedir un préstamo; lista vacía si puede.

    - `libro`: si se indica, también revisa que no tenga ya un préstamo vigente de ese título (RN-11).
    - `excluir`: préstamo que no debe contarse (al entregar una solicitud, ya cuenta para RN-02 y RN-11).
    """
    # Import aquí y no al inicio: multas tiene llave foránea a prestamo (import circular).
    from multas.services import tiene_multas_pendientes

    motivos = []
    if not usuario.is_active:
        motivos.append("Tu cuenta está dada de baja.")
    if usuario.bloqueado:
        motivos.append(
            f"Tu cuenta está bloqueada: {usuario.motivo_bloqueo}"
            if usuario.motivo_bloqueo
            else "Tu cuenta está bloqueada."
        )

    try:
        politica = PoliticaPrestamo.para(usuario)
    except ValueError:
        motivos.append("Solo estudiantes y profesores pueden pedir libros prestados.")
        return motivos

    if tiene_multas_pendientes(usuario):
        motivos.append("Tienes multas pendientes de pago.")
    if tiene_prestamos_vencidos(usuario):
        motivos.append("Tienes préstamos vencidos sin devolver.")

    vigentes = Prestamo.objects.filter(usuario=usuario, estado__in=Prestamo.ESTADOS_VIGENTES)
    if excluir is not None:
        vigentes = vigentes.exclude(pk=excluir.pk)

    total_vigentes = vigentes.count()
    if total_vigentes >= politica.max_libros:
        motivos.append(
            f"Ya tienes {total_vigentes} libros prestados o solicitados; "
            f"el máximo para tu tipo de usuario es {politica.max_libros}."
        )
    if libro is not None and vigentes.filter(ejemplar__libro=libro).exists():
        motivos.append(f"Ya tienes un préstamo vigente de «{libro}».")

    return motivos


# --- Operaciones ---------------------------------------------------------------------

def solicitar_prestamo(usuario, libro):
    """CU-06: el lector solicita en línea un libro; se le aparta un ejemplar para recogerlo.

    Lanza UsuarioNoElegible o SinEjemplaresDisponibles; en ese caso no cambia nada.
    """
    with transaction.atomic():
        usuario = _bloquear_usuario(usuario)
        motivos = verificar_elegibilidad(usuario, libro)
        if motivos:
            raise UsuarioNoElegible(motivos)

        ejemplar = _tomar_ejemplar_disponible(libro)
        politica = PoliticaPrestamo.para(usuario)
        ahora = timezone.now()
        prestamo = Prestamo.objects.create(
            usuario=usuario,
            ejemplar=ejemplar,
            estado=Prestamo.Estado.SOLICITADO,
            fecha_solicitud=ahora,
            fecha_limite_recoger=ahora + timedelta(hours=politica.horas_para_recoger),  # RN-06
        )
        _cambiar_estado_ejemplar(ejemplar, Ejemplar.Estado.RESERVADO)
        notificar(
            usuario,
            "GENERAL",
            f"Tu solicitud {prestamo.pk} de «{libro}» está lista. Recoge el ejemplar "
            f"{ejemplar.codigo_inventario} antes del {_formato_fecha(prestamo.fecha_limite_recoger)}.",
        )
    return prestamo


def entregar_prestamo(prestamo, bibliotecario):
    """CU-23: el bibliotecario entrega un préstamo SOLICITADO; pasa a ACTIVO (RN-01)."""
    _validar_bibliotecario(bibliotecario)
    with transaction.atomic():
        usuario = _bloquear_usuario(prestamo.usuario)
        prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
        ejemplar = Ejemplar.objects.select_for_update().get(pk=prestamo.ejemplar_id)

        if (
            prestamo.estado == Prestamo.Estado.SOLICITADO
            and prestamo.fecha_limite_recoger is not None
            and timezone.now() > prestamo.fecha_limite_recoger
        ):
            raise OperacionNoPermitida(
                f"El plazo para recoger venció el {_formato_fecha(prestamo.fecha_limite_recoger)}."
            )

        motivos = verificar_elegibilidad(usuario, ejemplar.libro, excluir=prestamo)
        if motivos:
            raise UsuarioNoElegible(motivos)

        prestamo.entregar(bibliotecario)
        _cambiar_estado_ejemplar(ejemplar, Ejemplar.Estado.PRESTADO)
        notificar(
            usuario,
            "GENERAL",
            f"Recibiste «{ejemplar.libro}» (préstamo {prestamo.pk}). "
            f"Devuélvelo a más tardar el {prestamo.fecha_vencimiento:%d/%m/%Y}.",
        )
    return prestamo


def prestar_en_mostrador(usuario, ejemplar, bibliotecario):
    """CU-24: el bibliotecario presta un ejemplar en mostrador; el préstamo nace ACTIVO (RN-01)."""
    _validar_bibliotecario(bibliotecario)
    with transaction.atomic():
        usuario = _bloquear_usuario(usuario)
        ejemplar = Ejemplar.objects.select_for_update().get(pk=ejemplar.pk)

        motivos = verificar_elegibilidad(usuario, ejemplar.libro)
        if motivos:
            raise UsuarioNoElegible(motivos)
        if not ejemplar.es_prestable():  # RN-15
            raise SinEjemplaresDisponibles(
                f"El ejemplar {ejemplar.codigo_inventario} no está disponible para préstamo."
            )

        prestamo = Prestamo.objects.create(usuario=usuario, ejemplar=ejemplar)
        prestamo.entregar(bibliotecario)
        _cambiar_estado_ejemplar(ejemplar, Ejemplar.Estado.PRESTADO)
        notificar(
            usuario,
            "GENERAL",
            f"Recibiste «{ejemplar.libro}» (préstamo {prestamo.pk}). "
            f"Devuélvelo a más tardar el {prestamo.fecha_vencimiento:%d/%m/%Y}.",
        )
    return prestamo


def asignar_siguiente_reserva(ejemplar):
    """RN-12: aparta `ejemplar` para la reserva PENDIENTE más antigua de su libro (contrato C → D).

    Devuelve la reserva asignada, o None si no hay reservas pendientes. En ese caso no cambia
    el ejemplar: quien llama (la devolución de D) lo deja DISPONIBLE.
    """
    with transaction.atomic():
        ejemplar = Ejemplar.objects.select_for_update().get(pk=ejemplar.pk)
        if not _ejemplar_asignable(ejemplar):
            raise OperacionNoPermitida(
                f"El ejemplar {ejemplar.codigo_inventario} no se puede apartar para una reserva."
            )

        reserva = (
            Reserva.objects.select_for_update()
            .filter(libro=ejemplar.libro, estado=Reserva.Estado.PENDIENTE)
            .order_by("fecha_reserva", "pk")
            .first()
        )
        if reserva is None:
            return None

        reserva.marcar_disponible(ejemplar)
        _cambiar_estado_ejemplar(ejemplar, Ejemplar.Estado.RESERVADO)
        notificar(
            reserva.usuario,
            "RESERVA_DISPONIBLE",
            f"«{ejemplar.libro}», que reservaste, ya está disponible. "
            f"Recógelo antes del {_formato_fecha(reserva.fecha_expiracion)}.",
        )
    return reserva
