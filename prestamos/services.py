"""Servicios de la app prestamos: reglas de negocio que usan varias apps.

Las otras apps se usan solo a través de los contratos de PLAN_DE_TRABAJO.md (sección 3):
Libro.ejemplares_disponibles(), Ejemplar.es_prestable(), tiene_multas_pendientes(),
monto_adeudado() y notificar().

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
# Único lugar de prestamos que toca el estado de un ejemplar.
# Escritura: contrato Ejemplar.cambiar_estado(estado) de catalogo (B → C); quien llama ya
# tiene el ejemplar bloqueado con select_for_update() dentro de transaction.atomic().
# Lectura: el campo `estado` y los valores de Ejemplar.Estado, documentados por catalogo;
# el contrato no tiene métodos de lectura aparte de es_prestable().

_ESTADOS_NO_ASIGNABLES = {
    Ejemplar.Estado.EN_REPARACION,
    Ejemplar.Estado.PERDIDO,
    Ejemplar.Estado.BAJA,
}


def _cambiar_estado_ejemplar(ejemplar, estado):
    ejemplar.cambiar_estado(estado)


def _ejemplar_asignable(ejemplar):
    """Un ejemplar devuelto o liberado puede apartarse si no está dañado, perdido ni dado de baja."""
    return ejemplar.estado not in _ESTADOS_NO_ASIGNABLES


def _ejemplar_apartado(ejemplar):
    """¿El ejemplar está apartado (RESERVADO) para una solicitud o una reserva?"""
    return ejemplar.estado == Ejemplar.Estado.RESERVADO


def _liberar_ejemplar(ejemplar):
    """Un ejemplar apartado queda libre: pasa a la siguiente reserva (RN-12) o a DISPONIBLE."""
    if asignar_siguiente_reserva(ejemplar) is None:
        _cambiar_estado_ejemplar(ejemplar, Ejemplar.Estado.DISPONIBLE)


# --- Utilidades internas -------------------------------------------------------------

def _bloquear_usuario(usuario):
    return get_user_model().objects.select_for_update().get(pk=usuario.pk)


def _validar_bibliotecario(usuario, accion="registrar la entrega de un préstamo"):
    if usuario is None or usuario.tipo_usuario != "BIBLIOTECARIO":
        raise OperacionNoPermitida(f"Solo un bibliotecario puede {accion}.")


def _validar_dueno(objeto, usuario):
    """RNF-02: un lector solo opera sobre sus propios préstamos y reservas."""
    if objeto.usuario_id != usuario.pk:
        raise OperacionNoPermitida(f"{objeto} no te pertenece.")


def _formato_fecha(fecha_hora):
    return timezone.localtime(fecha_hora).strftime("%d/%m/%Y %H:%M")


def _bloquear_reserva_con_ejemplar(reserva):
    """Bloquea el ejemplar asignado y luego la reserva, respetando el orden ejemplar → reserva."""
    ejemplar_id = Reserva.objects.values_list("ejemplar_asignado_id", flat=True).get(pk=reserva.pk)
    ejemplar = Ejemplar.objects.select_for_update().get(pk=ejemplar_id) if ejemplar_id else None
    reserva = Reserva.objects.select_for_update().get(pk=reserva.pk)
    if reserva.ejemplar_asignado_id != ejemplar_id:
        raise OperacionNoPermitida("La reserva cambió mientras se procesaba; inténtalo de nuevo.")
    return reserva, ejemplar


def _cancelar_y_liberar(reserva, ejemplar):
    """Cancela una reserva ya bloqueada; si tenía un ejemplar apartado, lo libera (RN-12)."""
    tenia_ejemplar_apartado = reserva.estado == Reserva.Estado.DISPONIBLE
    reserva.cancelar()
    if tenia_ejemplar_apartado and ejemplar is not None:
        _liberar_ejemplar(ejemplar)


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

def tiene_prestamos_vencidos(usuario, excluir=None):
    """RN-08: ¿el usuario tiene algún préstamo vencido? (contrato C → C, D).

    Cuenta los préstamos en estado VENCIDO y también los ACTIVOS cuya fecha de vencimiento
    ya pasó, aunque el comando de vencimientos (CU-34) todavía no los haya marcado.
    `excluir`: préstamo que no debe contarse (al renovar, el propio préstamo se revisa aparte).
    """
    hoy = timezone.localdate()
    prestamos = Prestamo.objects.filter(
        Q(estado=Prestamo.Estado.VENCIDO)
        | Q(estado=Prestamo.Estado.ACTIVO, fecha_vencimiento__lt=hoy),
        usuario=usuario,
    )
    if excluir is not None:
        prestamos = prestamos.exclude(pk=excluir.pk)
    return prestamos.exists()


def esta_vencido(prestamo):
    """RN-09: VENCIDO, o ACTIVO con la fecha de vencimiento ya pasada."""
    return prestamo.estado == Prestamo.Estado.VENCIDO or (
        prestamo.estado == Prestamo.Estado.ACTIVO
        and prestamo.fecha_vencimiento is not None
        and prestamo.fecha_vencimiento < timezone.localdate()
    )


def posicion_en_cola(reserva):
    """RN-12: lugar de una reserva PENDIENTE en la fila de su libro (1 = la siguiente).

    Devuelve None si la reserva ya no está pendiente.
    """
    if reserva.estado != Reserva.Estado.PENDIENTE:
        return None
    anteriores = Reserva.objects.filter(
        Q(fecha_reserva__lt=reserva.fecha_reserva)
        | Q(fecha_reserva=reserva.fecha_reserva, pk__lt=reserva.pk),
        libro_id=reserva.libro_id,
        estado=Reserva.Estado.PENDIENTE,
    )
    return anteriores.count() + 1


def verificar_elegibilidad(usuario, libro=None, excluir=None):
    """CU-07: motivos por los que `usuario` no puede pedir un préstamo; lista vacía si puede.

    - `libro`: si se indica, también revisa que no tenga ya un préstamo vigente de ese título (RN-11).
    - `excluir`: préstamo que no debe contarse (al entregar una solicitud, ya cuenta para RN-02 y RN-11).
    """
    # Import aquí y no al inicio: multas tiene llave foránea a prestamo (import circular).
    from multas.services import monto_adeudado, tiene_multas_pendientes

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
        # CU-06, excepción 4a: además del motivo, se informa el monto adeudado.
        motivos.append(
            f"Tienes multas pendientes de pago. Monto adeudado: ${monto_adeudado(usuario):,.2f}."
        )
    if tiene_prestamos_vencidos(usuario, excluir=excluir):
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


def cancelar_solicitud(prestamo, usuario):
    """CU-08: el lector cancela su solicitud; el ejemplar pasa a la siguiente reserva o a DISPONIBLE."""
    with transaction.atomic():
        usuario = _bloquear_usuario(usuario)
        prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
        _validar_dueno(prestamo, usuario)
        ejemplar = Ejemplar.objects.select_for_update().get(pk=prestamo.ejemplar_id)

        prestamo.cancelar()
        _liberar_ejemplar(ejemplar)
    return prestamo


def renovar_prestamo(prestamo, usuario):
    """CU-10: el lector renueva su préstamo (RN-03, RN-08, RN-09, RN-10).

    Lanza UsuarioNoElegible con todos los motivos de rechazo juntos.
    """
    with transaction.atomic():
        usuario = _bloquear_usuario(usuario)
        prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
        _validar_dueno(prestamo, usuario)
        libro = prestamo.ejemplar.libro

        motivos = []
        if esta_vencido(prestamo):  # RN-09
            motivos.append("El préstamo está vencido: devuélvelo en la biblioteca.")
        elif prestamo.estado != Prestamo.Estado.ACTIVO:
            motivos.append(
                f"Solo se renuevan préstamos activos; este está «{prestamo.get_estado_display()}»."
            )
        # CU-07 sin contar este préstamo: renovar no suma libros (RN-02) ni repite título (RN-11).
        motivos.extend(verificar_elegibilidad(usuario, libro, excluir=prestamo))
        if prestamo.estado == Prestamo.Estado.ACTIVO and prestamo.renovaciones_restantes() == 0:
            motivos.append("Ya usaste todas las renovaciones de este préstamo.")  # RN-03
        reservas_de_otros = Reserva.objects.filter(
            libro=libro, estado=Reserva.Estado.PENDIENTE
        ).exclude(usuario=usuario)
        if reservas_de_otros.exists():  # RN-09
            motivos.append(f"Otro usuario reservó «{libro}»; no se puede renovar.")
        if motivos:
            raise UsuarioNoElegible(motivos)

        prestamo.renovar()  # RN-10
        notificar(
            usuario,
            "GENERAL",
            f"Renovaste «{libro}» (préstamo {prestamo.pk}). "
            f"Nueva fecha de devolución: {prestamo.fecha_vencimiento:%d/%m/%Y}.",
        )
    return prestamo


def reservar_libro(usuario, libro):
    """CU-11: el lector reserva un libro sin ejemplares disponibles; entra a la cola FIFO (RN-12)."""
    with transaction.atomic():
        usuario = _bloquear_usuario(usuario)
        if libro.ejemplares_disponibles().exists():
            raise OperacionNoPermitida(
                f"Hay ejemplares disponibles de «{libro}»: solicita el préstamo en lugar de reservar."
            )
        reserva_activa = Reserva.objects.filter(
            usuario=usuario,
            libro=libro,
            estado__in=[Reserva.Estado.PENDIENTE, Reserva.Estado.DISPONIBLE],
        )
        if reserva_activa.exists():
            raise OperacionNoPermitida(f"Ya tienes una reserva activa de «{libro}».")

        motivos = verificar_elegibilidad(usuario, libro)
        if motivos:
            raise UsuarioNoElegible(motivos)

        reserva = Reserva.objects.create(usuario=usuario, libro=libro)
        notificar(
            usuario,
            "GENERAL",
            f"Reservaste «{libro}». Tu lugar en la fila es el {posicion_en_cola(reserva)}.",
        )
    return reserva


def cancelar_reserva(reserva, usuario):
    """CU-12: el lector cancela su reserva; si ya tenía un ejemplar apartado, éste se libera."""
    with transaction.atomic():
        usuario = _bloquear_usuario(usuario)
        reserva, ejemplar = _bloquear_reserva_con_ejemplar(reserva)
        _validar_dueno(reserva, usuario)
        _cancelar_y_liberar(reserva, ejemplar)
    return reserva


def recoger_reserva(reserva, bibliotecario):
    """El lector recoge en mostrador el ejemplar apartado por su reserva DISPONIBLE.

    Se crea un préstamo ACTIVO (RN-01), el ejemplar pasa a PRESTADO y la reserva a ATENDIDA.
    """
    _validar_bibliotecario(bibliotecario)
    with transaction.atomic():
        usuario = _bloquear_usuario(reserva.usuario)
        reserva, ejemplar = _bloquear_reserva_con_ejemplar(reserva)

        if reserva.estado != Reserva.Estado.DISPONIBLE:
            raise OperacionNoPermitida(
                f"La reserva está «{reserva.get_estado_display()}»: "
                "solo se recoge una reserva disponible para recoger."
            )
        if reserva.fecha_expiracion is not None and timezone.now() > reserva.fecha_expiracion:
            raise OperacionNoPermitida(
                f"El plazo para recoger venció el {_formato_fecha(reserva.fecha_expiracion)}."
            )
        if ejemplar is None or not _ejemplar_apartado(ejemplar):
            raise OperacionNoPermitida("El ejemplar apartado para esta reserva ya no está disponible.")

        motivos = verificar_elegibilidad(usuario, reserva.libro)
        if motivos:
            raise UsuarioNoElegible(motivos)

        prestamo = Prestamo.objects.create(usuario=usuario, ejemplar=ejemplar)
        prestamo.entregar(bibliotecario)
        _cambiar_estado_ejemplar(ejemplar, Ejemplar.Estado.PRESTADO)
        reserva.atender()
        notificar(
            usuario,
            "GENERAL",
            f"Recibiste «{reserva.libro}» (préstamo {prestamo.pk}). "
            f"Devuélvelo a más tardar el {prestamo.fecha_vencimiento:%d/%m/%Y}.",
        )
    return prestamo


# --- Funciones del bibliotecario: CU-30 gestionar reservas -----------------------------

# El motivo va en la notificación (notificacion.mensaje es varchar(500)); con este tope el
# mensaje completo cabe aunque el título del libro tenga 255 caracteres.
MAX_LONGITUD_MOTIVO = 150


def listar_reservas(libro=None, estado=None):
    """CU-30: reservas filtradas por libro y/o estado, en orden de llegada.

    Solo lee: el permiso lo revisa la vista. La paginación (RNF-05) también va en la vista.
    """
    reservas = Reserva.objects.select_related("usuario", "libro", "ejemplar_asignado")
    if libro is not None:
        reservas = reservas.filter(libro=libro)
    if estado is not None:
        if estado not in Reserva.Estado.values:
            raise ValueError(f"Estado de reserva desconocido: {estado}")
        reservas = reservas.filter(estado=estado)
    return reservas.order_by("fecha_reserva", "pk")


def cola_de_reservas(libro):
    """CU-30 / RN-12: reservas PENDIENTES de un libro en orden FIFO; la primera es la siguiente."""
    return (
        Reserva.objects.filter(libro=libro, estado=Reserva.Estado.PENDIENTE)
        .select_related("usuario")
        .order_by("fecha_reserva", "pk")
    )


def cancelar_reserva_por_bibliotecario(reserva, bibliotecario, motivo):
    """CU-30: el bibliotecario cancela la reserva de cualquier usuario, con motivo obligatorio.

    El motivo no se guarda en la reserva (la tabla no tiene esa columna); se le envía al
    usuario en la notificación. Si había un ejemplar apartado, se libera (RN-12).
    """
    _validar_bibliotecario(bibliotecario, "cancelar la reserva de otro usuario")
    motivo = (motivo or "").strip()
    if not motivo:
        raise OperacionNoPermitida("Indica el motivo de la cancelación.")
    if len(motivo) > MAX_LONGITUD_MOTIVO:
        raise OperacionNoPermitida(
            f"El motivo no puede pasar de {MAX_LONGITUD_MOTIVO} caracteres."
        )

    with transaction.atomic():
        usuario = _bloquear_usuario(reserva.usuario)
        reserva, ejemplar = _bloquear_reserva_con_ejemplar(reserva)
        _cancelar_y_liberar(reserva, ejemplar)
        notificar(
            usuario,
            "GENERAL",
            f"La biblioteca canceló tu reserva de «{reserva.libro}». Motivo: {motivo}",
        )
    return reserva


# --- Funciones del bibliotecario: CU-31 configurar políticas ---------------------------

CAMPOS_EDITABLES_POLITICA = (
    "dias_prestamo",
    "max_libros",
    "max_renovaciones",
    "multa_por_dia",
    "multa_maxima",
    "horas_para_recoger",
)


def actualizar_politica(politica, bibliotecario, **cambios):
    """CU-31: el bibliotecario cambia los valores de una política (RN-01 a RN-06).

    Valida con full_clean(): tipos, decimales, CHECK de la tabla y PoliticaPrestamo.clean().
    Si algo no es válido lanza ValidationError (un mensaje por campo) y no guarda nada.

    Efecto en préstamos existentes: los ya entregados conservan su fecha de vencimiento, pero
    renovaciones_restantes() y calcular_multa() usan siempre la política vigente.
    """
    _validar_bibliotecario(bibliotecario, "configurar las políticas de préstamo")
    if not cambios:
        raise OperacionNoPermitida("No hay cambios que guardar.")
    no_editables = sorted(set(cambios) - set(CAMPOS_EDITABLES_POLITICA))
    if no_editables:
        raise OperacionNoPermitida(
            f"Estos campos no se pueden cambiar: {', '.join(no_editables)}."
        )

    with transaction.atomic():
        politica = PoliticaPrestamo.objects.select_for_update().get(pk=politica.pk)
        for campo, valor in cambios.items():
            setattr(politica, campo, valor)
        politica.full_clean()
        politica.save(update_fields=[*cambios, "actualizado_en"])
    return politica
