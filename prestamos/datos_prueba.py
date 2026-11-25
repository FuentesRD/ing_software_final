"""Datos de prueba de préstamos y reservas para `python manage.py cargar_datos_prueba`.

Contrato con el comando de catalogo (Diego): `cargar()` no recibe nada y devuelve un dict
{"nombre": cantidad_creada}. El comando la llama después de crear usuarios y libros, dentro
de una sola transacción; por eso aquí no se lanzan excepciones: si faltan datos se escribe
un aviso y se devuelven ceros, para no deshacer la carga de las demás apps.

Todo se crea con los servicios de prestamos/services.py, que aplican las reglas (RN-01 a
RN-15). Las filas solo se tocan a mano para mover fechas al pasado.

No duplica: si los usuarios de prueba ya tienen préstamos, no hace nada y devuelve ceros.
Usa random.Random(2026) y recorre usuarios y libros en orden fijo (username, isbn), así que
todos los integrantes obtienen los mismos datos aunque los pk cambien entre máquinas.
"""

import logging
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from catalogo.models import Ejemplar, Libro

from .models import PoliticaPrestamo, Prestamo, Reserva
from .services import (
    asignar_siguiente_reserva,
    entregar_prestamo,
    prestar_en_mostrador,
    reservar_libro,
    solicitar_prestamo,
    verificar_elegibilidad,
)

logger = logging.getLogger(__name__)

SEMILLA = 2026

USUARIOS_LECTORES = [f"est{i:02d}" for i in range(1, 21)] + [f"prof{i}" for i in range(1, 6)]
USUARIO_BIBLIOTECARIO = "biblio1"

DEVUELTOS = 10
ACTIVOS = 15
RESERVAS = 4  # en 3 libros: el primero con 2 en la fila para que se vea el FIFO (RN-12)
LIBROS_RESERVADOS = 3
SOLICITUDES = 8
VENCIDOS = 4

# Mínimos para intentar la carga. Los ejemplares ocupados al mismo tiempo son los de
# préstamos activos, solicitudes y vencidos (los devueltos se liberan antes).
MIN_LECTORES = 10
MIN_EJEMPLARES = ACTIVOS + SOLICITUDES + VENCIDOS


def _ceros():
    return {
        "solicitudes": 0,
        "activos": 0,
        "vencidos": 0,
        "devueltos": 0,
        "reservas": 0,
    }


def cargar():
    """Crea solicitudes, préstamos activos, vencidos y devueltos, y reservas en espera."""
    Usuario = get_user_model()
    if Prestamo.objects.filter(usuario__username__in=USUARIOS_LECTORES).exists():
        return _ceros()  # ya se cargaron antes

    bibliotecario = Usuario.objects.filter(
        username=USUARIO_BIBLIOTECARIO, tipo_usuario="BIBLIOTECARIO", is_active=True
    ).first()
    if bibliotecario is None:
        logger.warning(
            "Préstamos: no existe el bibliotecario %s; no se cargan datos de prueba.",
            USUARIO_BIBLIOTECARIO,
        )
        return _ceros()

    lectores = list(
        Usuario.objects.filter(
            username__in=USUARIOS_LECTORES,
            tipo_usuario__in=PoliticaPrestamo.TipoUsuario.values,
            is_active=True,
        ).order_by("username")
    )
    if len(lectores) < MIN_LECTORES:
        logger.warning(
            "Préstamos: hay %d lectores de prueba y se necesitan al menos %d; "
            "no se cargan datos de prueba.",
            len(lectores),
            MIN_LECTORES,
        )
        return _ceros()

    libros = list(Libro.objects.filter(activo=True).order_by("isbn"))
    disponibles = Ejemplar.objects.filter(
        libro__activo=True, estado=Ejemplar.Estado.DISPONIBLE
    ).count()
    if disponibles < MIN_EJEMPLARES:
        logger.warning(
            "Préstamos: hay %d ejemplares disponibles y se necesitan al menos %d; "
            "no se cargan datos de prueba.",
            disponibles,
            MIN_EJEMPLARES,
        )
        return _ceros()

    return _Carga(random.Random(SEMILLA), bibliotecario, lectores, libros).ejecutar()


class _Carga:
    """Pasos de la carga. El orden importa:

    1. Devueltos primero: sus ejemplares quedan libres para lo demás.
    2. Activos, empezando por libros de un solo ejemplar, que quedan sin copias.
    3. Reservas sobre esos libros sin copias (reservar_libro lo exige).
    4. Solicitudes con fecha de hoy (en el pasado, CU-35 las expiraría).
    5. Vencidos al final: un préstamo vencido bloquea al usuario (RN-08).
    """

    def __init__(self, rng, bibliotecario, lectores, libros):
        self.rng = rng
        self.bibliotecario = bibliotecario
        self.lectores = lectores
        self.libros = libros
        self.creados = _ceros()

    def ejecutar(self):
        for _ in range(DEVUELTOS):
            self._crear_devuelto()

        libros_sin_copias = self._libros_de_un_ejemplar()[:LIBROS_RESERVADOS]
        for libro in libros_sin_copias:
            self._crear_activo([libro])
        for _ in range(ACTIVOS - len(libros_sin_copias)):
            self._crear_activo(self.libros)

        for i in range(RESERVAS):
            if libros_sin_copias:
                # 0, 0, 1, 2: el primer libro recibe dos reservas.
                indice = max(i - 1, 0) % len(libros_sin_copias)
                self._crear_reserva(libros_sin_copias[indice])

        for _ in range(SOLICITUDES):
            self._crear_solicitud()

        for _ in range(VENCIDOS):
            self._crear_vencido()

        return self.creados

    # --- Selección de lector y libro ---------------------------------------------

    def _libros_de_un_ejemplar(self):
        """Libros con exactamente un ejemplar disponible, en orden aleatorio fijo."""
        ids = set(
            Libro.objects.filter(pk__in=[libro.pk for libro in self.libros])
            .annotate(
                n=Count("ejemplares", filter=Q(ejemplares__estado=Ejemplar.Estado.DISPONIBLE))
            )
            .filter(n=1)
            .values_list("pk", flat=True)
        )
        candidatos = [libro for libro in self.libros if libro.pk in ids]
        self.rng.shuffle(candidatos)
        return candidatos

    def _intentar(self, libros, accion):
        """Prueba pares (lector, libro) en orden aleatorio hasta que `accion` funcione.

        Las reglas las revisan los servicios; aquí solo se descartan rápido los pares que
        no proceden. Devuelve lo que regrese `accion`, o None si ningún par sirvió.
        """
        lectores = self.lectores[:]
        self.rng.shuffle(lectores)
        for lector in lectores:
            if verificar_elegibilidad(lector):
                continue
            opciones = libros[:]
            self.rng.shuffle(opciones)
            for libro in opciones:
                if not libro.ejemplares_disponibles().exists():
                    continue
                if verificar_elegibilidad(lector, libro):
                    continue  # p. ej. ya tiene ese título (RN-11)
                try:
                    return accion(lector, libro)
                except ValidationError:
                    continue
        return None

    def _prestar(self, lector, libro):
        """CU-24: préstamo en mostrador del primer ejemplar disponible."""
        ejemplar = libro.ejemplares_disponibles().order_by("codigo_inventario").first()
        return prestar_en_mostrador(lector, ejemplar, self.bibliotecario)

    def _mover_fechas(self, prestamo, dias_atras, fecha_vencimiento):
        """Mueve al pasado las fechas de un préstamo recién entregado."""
        fecha_prestamo = timezone.now() - timedelta(days=dias_atras)
        fecha_solicitud = fecha_prestamo - timedelta(hours=self.rng.randint(1, 30))
        cambios = {
            "fecha_solicitud": fecha_solicitud,
            "fecha_prestamo": fecha_prestamo,
            "fecha_vencimiento": fecha_vencimiento,
        }
        if prestamo.fecha_limite_recoger is not None:  # se pidió en línea: conserva RN-06
            plazo = prestamo.fecha_limite_recoger - prestamo.fecha_solicitud
            cambios["fecha_limite_recoger"] = fecha_solicitud + plazo
        Prestamo.objects.filter(pk=prestamo.pk).update(**cambios)
        prestamo.refresh_from_db()

    # --- Pasos -------------------------------------------------------------------

    def _crear_devuelto(self):
        prestamo = self._intentar(self.libros, self._prestar)
        if prestamo is None:
            return
        dias = PoliticaPrestamo.para(prestamo.usuario).dias_prestamo
        dias_atras = self.rng.randint(dias + 5, dias + 90)
        inicio = timezone.localdate() - timedelta(days=dias_atras)
        self._mover_fechas(prestamo, dias_atras, inicio + timedelta(days=dias))
        # Se devuelve antes de vencer (sin retraso, así no le corresponde multa) y en el pasado.
        fecha_devolucion = prestamo.fecha_prestamo + timedelta(
            days=self.rng.randint(1, dias - 1) if dias > 1 else 0,
            hours=self.rng.randint(0, 6),
        )
        _registrar_devolucion(prestamo, self.bibliotecario, fecha_devolucion)
        self.creados["devueltos"] += 1

    def _crear_activo(self, libros):
        def por_solicitud(lector, libro):
            # CU-06 + CU-23: el lector lo pide en línea y el bibliotecario lo entrega.
            prestamo = solicitar_prestamo(lector, libro)
            return entregar_prestamo(prestamo, self.bibliotecario)

        # La mitad por solicitud en línea y la otra mitad en mostrador.
        accion = por_solicitud if self.creados["activos"] % 2 == 0 else self._prestar
        prestamo = self._intentar(libros, accion)
        if prestamo is None:
            return
        # Entregado hace unos días, pero sin vencer todavía.
        dias = PoliticaPrestamo.para(prestamo.usuario).dias_prestamo
        dias_atras = self.rng.randint(0, dias - 1)
        self._mover_fechas(
            prestamo, dias_atras, prestamo.fecha_vencimiento - timedelta(days=dias_atras)
        )
        self.creados["activos"] += 1

    def _crear_reserva(self, libro):
        reserva = self._intentar_reserva(libro)
        if reserva is not None:
            self.creados["reservas"] += 1

    def _intentar_reserva(self, libro):
        lectores = self.lectores[:]
        self.rng.shuffle(lectores)
        for lector in lectores:
            try:
                return reservar_libro(lector, libro)
            except ValidationError:
                continue  # no elegible, ya tiene el libro o ya lo reservó
        return None

    def _crear_solicitud(self):
        if self._intentar(self.libros, solicitar_prestamo) is not None:
            self.creados["solicitudes"] += 1

    def _crear_vencido(self):
        prestamo = self._intentar(self.libros, self._prestar)
        if prestamo is None:
            return
        dias = PoliticaPrestamo.para(prestamo.usuario).dias_prestamo
        retraso = self.rng.randint(1, 20)
        self._mover_fechas(
            prestamo, dias + retraso, timezone.localdate() - timedelta(days=retraso)
        )
        prestamo.marcar_vencido()  # CU-34: ACTIVO → VENCIDO
        self.creados["vencidos"] += 1


def _registrar_devolucion(prestamo, bibliotecario, fecha):
    """Devolución mínima (CU-25) para los datos de prueba, sin multa.

    TODO: cambiar por el servicio de devolución del paquete D (Samanta) cuando exista.
    Sigue el contrato de PLAN_DE_TRABAJO.md: después de cambiar el préstamo se llama a
    asignar_siguiente_reserva() y, si devuelve None, el ejemplar queda DISPONIBLE.
    """
    with transaction.atomic():
        prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
        ejemplar = Ejemplar.objects.select_for_update().get(pk=prestamo.ejemplar_id)
        prestamo.marcar_devuelto(bibliotecario, fecha)
        if asignar_siguiente_reserva(ejemplar) is None:
            ejemplar.cambiar_estado(Ejemplar.Estado.DISPONIBLE)
