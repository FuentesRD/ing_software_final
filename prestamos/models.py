"""Modelos de la app prestamos: políticas, préstamos y reservas.

Tablas, columnas y restricciones según docs/bd/esquema_bd_biblioteca.html (sección 5.3).
Las otras apps se usan solo a través de los contratos de PLAN_DE_TRABAJO.md (sección 3).
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TransicionInvalida(ValidationError):
    """Cambio de estado que no permite el diagrama de estados (sección 10.3 de los requerimientos)."""


def _validar_transicion(objeto, permitidos, destino):
    """Lanza TransicionInvalida si `objeto.estado` no está en `permitidos`."""
    if objeto.estado not in permitidos:
        actual = objeto.Estado(objeto.estado).label
        raise TransicionInvalida(
            f"No se puede pasar de «{actual}» a «{destino.label}»."
        )


class PoliticaPrestamo(models.Model):
    """Parámetros de préstamo por tipo de usuario lector (RN-01 a RN-06)."""

    class TipoUsuario(models.TextChoices):
        ESTUDIANTE = "ESTUDIANTE", "Estudiante"
        PROFESOR = "PROFESOR", "Profesor"

    tipo_usuario = models.CharField(
        "tipo de usuario", max_length=15, choices=TipoUsuario.choices, unique=True
    )
    dias_prestamo = models.PositiveSmallIntegerField("días de préstamo")
    max_libros = models.PositiveSmallIntegerField("máximo de libros")
    max_renovaciones = models.PositiveSmallIntegerField("máximo de renovaciones")
    multa_por_dia = models.DecimalField("multa por día", max_digits=8, decimal_places=2)
    multa_maxima = models.DecimalField("multa máxima", max_digits=8, decimal_places=2)
    horas_para_recoger = models.PositiveSmallIntegerField("horas para recoger")
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        db_table = "politica_prestamo"
        verbose_name = "política de préstamo"
        verbose_name_plural = "políticas de préstamo"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(multa_maxima__gte=0, multa_por_dia__gte=0),
                name="ck_politica_multas",
            ),
            models.CheckConstraint(
                condition=models.Q(tipo_usuario__in=["ESTUDIANTE", "PROFESOR"]),
                name="ck_politica_tipo",
            ),
        ]

    def __str__(self):
        return f"Política {self.get_tipo_usuario_display()}"

    @classmethod
    def para(cls, usuario):
        """Política que aplica a `usuario` según su tipo (contrato C → D).

        Lanza ValueError si el usuario no es lector (p. ej. un bibliotecario).
        """
        if usuario.tipo_usuario not in cls.TipoUsuario.values:
            raise ValueError(
                f"El usuario {usuario} no es lector: los bibliotecarios no tienen política de préstamo."
            )
        return cls.objects.get(tipo_usuario=usuario.tipo_usuario)


class Prestamo(models.Model):
    """Préstamo de un ejemplar a un usuario lector, de la solicitud a la devolución."""

    class Estado(models.TextChoices):
        SOLICITADO = "SOLICITADO", "Solicitado"
        ACTIVO = "ACTIVO", "Activo"
        VENCIDO = "VENCIDO", "Vencido"
        DEVUELTO = "DEVUELTO", "Devuelto"
        CANCELADO = "CANCELADO", "Cancelado"
        EXPIRADO = "EXPIRADO", "Expirado"
        PERDIDO = "PERDIDO", "Perdido"

    # Préstamos que cuentan para el máximo de libros (RN-02).
    ESTADOS_VIGENTES = (Estado.SOLICITADO, Estado.ACTIVO, Estado.VENCIDO)

    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.SOLICITADO, db_index=True
    )
    fecha_solicitud = models.DateTimeField("fecha de solicitud", default=timezone.now)
    fecha_limite_recoger = models.DateTimeField("límite para recoger", null=True, blank=True)
    fecha_prestamo = models.DateTimeField("fecha de préstamo", null=True, blank=True)
    fecha_vencimiento = models.DateField("fecha de vencimiento", null=True, blank=True, db_index=True)
    fecha_devolucion = models.DateTimeField("fecha de devolución", null=True, blank=True)
    num_renovaciones = models.PositiveSmallIntegerField("renovaciones", default=0)
    observaciones = models.CharField(max_length=255, null=True, blank=True)
    # Llaves foráneas al final y en orden alfabético, como en el esquema de referencia.
    ejemplar = models.ForeignKey(
        "catalogo.Ejemplar", on_delete=models.PROTECT, related_name="prestamos"
    )
    entregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prestamos_entregados",
    )
    recibido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prestamos_recibidos",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prestamos"
    )

    class Meta:
        db_table = "prestamo"
        verbose_name = "préstamo"
        verbose_name_plural = "préstamos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=[
                    "SOLICITADO", "ACTIVO", "VENCIDO", "DEVUELTO", "CANCELADO", "EXPIRADO", "PERDIDO",
                ]),
                name="ck_prestamo_estado",
            ),
        ]

    def __str__(self):
        return f"Préstamo {self.pk} ({self.get_estado_display()})"

    # --- Reglas de negocio ---

    def renovaciones_restantes(self):
        """RN-03: renovaciones que aún le quedan a este préstamo."""
        politica = PoliticaPrestamo.para(self.usuario)
        return max(politica.max_renovaciones - self.num_renovaciones, 0)

    def dias_retraso(self, fecha=None):
        """Días naturales de retraso respecto a `fecha_vencimiento` (RN-07); nunca negativo.

        Sin `fecha`, usa la fecha de devolución si ya se devolvió, o la de hoy.
        """
        if self.fecha_vencimiento is None:
            return 0
        if fecha is None:
            fecha = (
                timezone.localdate(self.fecha_devolucion)
                if self.fecha_devolucion
                else timezone.localdate()
            )
        return max((fecha - self.fecha_vencimiento).days, 0)

    def calcular_multa(self, politica=None):
        """RN-07: min(días de retraso × multa por día, multa máxima)."""
        politica = politica or PoliticaPrestamo.para(self.usuario)
        return min(self.dias_retraso() * politica.multa_por_dia, politica.multa_maxima)

    # --- Cambios de estado (contrato C → D) ---
    # Solo cambian el préstamo. El estado del ejemplar lo cambian los servicios,
    # dentro de transaction.atomic() y con select_for_update() (RNF-03).

    def entregar(self, bibliotecario):
        """CU-23: SOLICITADO → ACTIVO. Fija la fecha de vencimiento según la política (RN-01)."""
        _validar_transicion(self, [self.Estado.SOLICITADO], self.Estado.ACTIVO)
        politica = PoliticaPrestamo.para(self.usuario)
        self.estado = self.Estado.ACTIVO
        self.fecha_prestamo = timezone.now()
        self.fecha_vencimiento = timezone.localdate() + timedelta(days=politica.dias_prestamo)
        self.entregado_por = bibliotecario
        self.save(update_fields=["estado", "fecha_prestamo", "fecha_vencimiento", "entregado_por"])

    def marcar_vencido(self):
        """CU-34: ACTIVO → VENCIDO."""
        _validar_transicion(self, [self.Estado.ACTIVO], self.Estado.VENCIDO)
        self.estado = self.Estado.VENCIDO
        self.save(update_fields=["estado"])

    def marcar_devuelto(self, bibliotecario, fecha=None):
        """CU-25: ACTIVO o VENCIDO → DEVUELTO."""
        _validar_transicion(self, [self.Estado.ACTIVO, self.Estado.VENCIDO], self.Estado.DEVUELTO)
        self.estado = self.Estado.DEVUELTO
        self.fecha_devolucion = fecha or timezone.now()
        self.recibido_por = bibliotecario
        self.save(update_fields=["estado", "fecha_devolucion", "recibido_por"])

    def marcar_perdido(self):
        """CU-27: ACTIVO o VENCIDO → PERDIDO."""
        _validar_transicion(self, [self.Estado.ACTIVO, self.Estado.VENCIDO], self.Estado.PERDIDO)
        self.estado = self.Estado.PERDIDO
        self.save(update_fields=["estado"])

    def cancelar(self):
        """CU-08: SOLICITADO → CANCELADO."""
        _validar_transicion(self, [self.Estado.SOLICITADO], self.Estado.CANCELADO)
        self.estado = self.Estado.CANCELADO
        self.save(update_fields=["estado"])

    def expirar(self):
        """CU-35: SOLICITADO → EXPIRADO (no se recogió a tiempo, RN-06)."""
        _validar_transicion(self, [self.Estado.SOLICITADO], self.Estado.EXPIRADO)
        self.estado = self.Estado.EXPIRADO
        self.save(update_fields=["estado"])


class Reserva(models.Model):
    """Reserva de un libro sin ejemplares disponibles; cola FIFO por fecha_reserva (RN-12)."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        DISPONIBLE = "DISPONIBLE", "Disponible para recoger"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"
        EXPIRADA = "EXPIRADA", "Expirada"

    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    fecha_reserva = models.DateTimeField("fecha de reserva", default=timezone.now)
    fecha_expiracion = models.DateTimeField("fecha de expiración", null=True, blank=True)
    # Llaves foráneas al final y en orden alfabético, como en el esquema de referencia.
    ejemplar_asignado = models.ForeignKey(
        "catalogo.Ejemplar",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_asignadas",
    )
    libro = models.ForeignKey("catalogo.Libro", on_delete=models.PROTECT, related_name="reservas")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservas"
    )

    class Meta:
        db_table = "reserva"
        ordering = ["fecha_reserva"]
        indexes = [
            models.Index(fields=["libro", "fecha_reserva"], name="idx_reserva_libro_fecha"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=[
                    "PENDIENTE", "DISPONIBLE", "ATENDIDA", "CANCELADA", "EXPIRADA",
                ]),
                name="ck_reserva_estado",
            ),
        ]

    def __str__(self):
        return f"Reserva {self.pk} ({self.get_estado_display()})"

    # --- Cambios de estado ---

    def marcar_disponible(self, ejemplar):
        """RN-12: PENDIENTE → DISPONIBLE. Aparta `ejemplar` y fija el plazo para recogerlo (RN-06)."""
        _validar_transicion(self, [self.Estado.PENDIENTE], self.Estado.DISPONIBLE)
        politica = PoliticaPrestamo.para(self.usuario)
        self.estado = self.Estado.DISPONIBLE
        self.ejemplar_asignado = ejemplar
        self.fecha_expiracion = timezone.now() + timedelta(hours=politica.horas_para_recoger)
        self.save(update_fields=["estado", "ejemplar_asignado", "fecha_expiracion"])

    def atender(self):
        """DISPONIBLE → ATENDIDA: la reserva se convirtió en préstamo."""
        _validar_transicion(self, [self.Estado.DISPONIBLE], self.Estado.ATENDIDA)
        self.estado = self.Estado.ATENDIDA
        self.save(update_fields=["estado"])

    def cancelar(self):
        """CU-12: PENDIENTE o DISPONIBLE → CANCELADA."""
        _validar_transicion(
            self, [self.Estado.PENDIENTE, self.Estado.DISPONIBLE], self.Estado.CANCELADA
        )
        self.estado = self.Estado.CANCELADA
        self.save(update_fields=["estado"])

    def expirar(self):
        """CU-35: DISPONIBLE → EXPIRADA (no se recogió a tiempo; contrato C → D)."""
        _validar_transicion(self, [self.Estado.DISPONIBLE], self.Estado.EXPIRADA)
        self.estado = self.Estado.EXPIRADA
        self.save(update_fields=["estado"])
