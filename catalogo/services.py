"""Reglas de negocio de catalogo. Las vistas solo llaman a estas funciones."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q

from .models import Autor, Ejemplar, Libro, LibroAutor, SugerenciaAdquisicion

# Estados que el bibliotecario puede asignar a mano (CU-18). RESERVADO y
# PRESTADO los asigna prestamos; PERDIDO lo asigna multas (RN-13).
ESTADOS_MANUALES = [
    Ejemplar.Estado.DISPONIBLE,
    Ejemplar.Estado.EN_REPARACION,
    Ejemplar.Estado.BAJA,
]

# Ejemplares en manos de un usuario o apartados: no se tocan desde catálogo.
ESTADOS_OCUPADOS = [Ejemplar.Estado.PRESTADO, Ejemplar.Estado.RESERVADO]


def buscar_libros(
    texto="",
    criterio="todo",
    categoria=None,
    editorial=None,
    solo_disponibles=False,
    incluir_bajas=False,
):
    """Búsqueda del catálogo (CU-04, RF-02) con disponibilidad por libro.

    Devuelve un queryset anotado con `total_ejemplares` y `disponibles`, con
    categoría, editorial y autores precargados para no repetir consultas
    por cada fila (RNF-05).
    """
    libros = Libro.objects.select_related("categoria", "editorial")
    if not incluir_bajas:
        libros = libros.filter(activo=True)

    texto = (texto or "").strip()
    if texto:
        por_titulo = Q(titulo__icontains=texto) | Q(subtitulo__icontains=texto)
        por_autor = Q(autores__nombre__icontains=texto) | Q(
            autores__apellidos__icontains=texto
        )
        por_isbn = Q(isbn__icontains=texto.replace("-", ""))
        filtros = {
            "titulo": por_titulo,
            "autor": por_autor,
            "isbn": por_isbn,
            "todo": por_titulo | por_autor | por_isbn,
        }
        coincidencias = Libro.objects.filter(filtros.get(criterio, filtros["todo"]))
        libros = libros.filter(pk__in=coincidencias.values("pk"))

    if categoria:
        libros = libros.filter(categoria=categoria)
    if editorial:
        libros = libros.filter(editorial=editorial)

    libros = libros.annotate(
        total_ejemplares=Count("ejemplares", distinct=True),
        disponibles=Count(
            "ejemplares",
            filter=Q(ejemplares__estado=Ejemplar.Estado.DISPONIBLE),
            distinct=True,
        ),
    )
    if solo_disponibles:
        libros = libros.filter(disponibles__gt=0)

    autores_en_orden = Prefetch(
        "autores",
        queryset=Autor.objects.order_by("libroautor__orden"),
    )
    return libros.prefetch_related(autores_en_orden).order_by("titulo")


def autores_de(libro):
    """Autores del libro en el orden de la portada."""
    return [
        relacion.autor
        for relacion in LibroAutor.objects.filter(libro=libro)
        .select_related("autor")
        .order_by("orden")
    ]


@transaction.atomic
def dar_de_baja_libro(libro):
    """Baja lógica del libro (CU-17): nunca se borra.

    No procede si algún ejemplar está prestado o reservado. Los demás
    ejemplares pasan a BAJA, salvo los PERDIDO, que conservan su estado.
    """
    libro = Libro.objects.select_for_update().get(pk=libro.pk)
    ejemplares = libro.ejemplares.select_for_update()
    if ejemplares.filter(estado__in=ESTADOS_OCUPADOS).exists():
        raise ValidationError(
            "No se puede dar de baja: hay ejemplares prestados o reservados."
        )
    ejemplares.filter(
        estado__in=[Ejemplar.Estado.DISPONIBLE, Ejemplar.Estado.EN_REPARACION]
    ).update(estado=Ejemplar.Estado.BAJA)
    libro.activo = False
    libro.save(update_fields=["activo"])
    return libro


def reactivar_libro(libro):
    """Vuelve a mostrar en el catálogo un libro dado de baja."""
    libro.activo = True
    libro.save(update_fields=["activo"])
    return libro


@transaction.atomic
def responder_sugerencia(sugerencia, estado, respuesta):
    """El bibliotecario aprueba o rechaza una sugerencia (CU-33)."""
    if estado not in (
        SugerenciaAdquisicion.Estado.APROBADA,
        SugerenciaAdquisicion.Estado.RECHAZADA,
    ):
        raise ValidationError("La respuesta debe aprobar o rechazar la sugerencia.")
    if sugerencia.estado != SugerenciaAdquisicion.Estado.PENDIENTE:
        raise ValidationError("Esta sugerencia ya fue respondida.")
    if not (respuesta or "").strip():
        raise ValidationError("Escribe una respuesta para el profesor.")
    sugerencia.estado = estado
    sugerencia.respuesta = respuesta.strip()
    sugerencia.save(update_fields=["estado", "respuesta"])
    return sugerencia