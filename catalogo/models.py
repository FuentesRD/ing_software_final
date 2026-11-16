"""Modelos de la app catalogo (Administración del acervo).

Referencia: docs/bd/esquema_bd_biblioteca.html, sección 5.2.
"""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class Categoria(models.Model):
    """Clasificación temática de los libros (CU-04, CU-19)."""

    nombre = models.CharField("nombre", max_length=100, unique=True)
    descripcion = models.CharField(
        "descripción", max_length=255, null=True, blank=True
    )

    class Meta:
        db_table = "categoria"
        ordering = ["nombre"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.nombre


class Editorial(models.Model):
    """Editoriales de los libros del acervo (CU-19)."""

    nombre = models.CharField("nombre", max_length=150, unique=True)
    pais = models.CharField("país", max_length=60, null=True, blank=True)

    class Meta:
        db_table = "editorial"
        ordering = ["nombre"]
        verbose_name = "editorial"
        verbose_name_plural = "editoriales"

    def __str__(self):
        return self.nombre


class Autor(models.Model):
    """Autores. Un autor puede tener varios libros (ver LibroAutor)."""

    nombre = models.CharField("nombre(s)", max_length=100)
    apellidos = models.CharField("apellidos", max_length=150, db_index=True)
    nacionalidad = models.CharField(
        "nacionalidad", max_length=60, null=True, blank=True
    )

    class Meta:
        db_table = "autor"
        ordering = ["apellidos", "nombre"]
        verbose_name = "autor"
        verbose_name_plural = "autores"

    def __str__(self):
        return f"{self.apellidos}, {self.nombre}"


# ISBN-10 (9 dígitos + dígito o X) o ISBN-13 (13 dígitos), sin guiones.
validar_isbn = RegexValidator(
    regex=r"^(\d{9}[\dX]|\d{13})$",
    message="El ISBN debe tener 10 o 13 caracteres, sin guiones.",
)


class Libro(models.Model):
    """Título del catálogo. Las copias físicas son Ejemplar (CU-04, CU-05, CU-17)."""

    isbn = models.CharField(
        "ISBN", max_length=13, unique=True, validators=[validar_isbn]
    )
    titulo = models.CharField("título", max_length=255, db_index=True)
    subtitulo = models.CharField(
        "subtítulo", max_length=255, null=True, blank=True
    )
    anio_publicacion = models.PositiveSmallIntegerField(
        "año de publicación", null=True, blank=True
    )
    edicion = models.CharField("edición", max_length=30, null=True, blank=True)
    idioma = models.CharField("idioma", max_length=30, default="Español")
    num_paginas = models.PositiveSmallIntegerField(
        "número de páginas", null=True, blank=True
    )
    descripcion = models.TextField("descripción", null=True, blank=True)
    portada = models.ImageField(
        "portada", upload_to="portadas/", null=True, blank=True
    )
    costo_reposicion = models.DecimalField(
        "costo de reposición", max_digits=10, decimal_places=2, default=0
    )
    activo = models.BooleanField("activo", default=True)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="libros",
        verbose_name="categoría",
    )
    editorial = models.ForeignKey(
        Editorial,
        on_delete=models.PROTECT,
        related_name="libros",
        verbose_name="editorial",
    )
    autores = models.ManyToManyField(
        Autor,
        through="LibroAutor",
        related_name="libros",
        verbose_name="autores",
    )

    class Meta:
        db_table = "libro"
        ordering = ["titulo"]
        verbose_name = "libro"
        verbose_name_plural = "libros"

    def __str__(self):
        return self.titulo

    def ejemplares_disponibles(self):
        """Queryset de los ejemplares de este libro que se pueden prestar (RN-15)."""
        return self.ejemplares.filter(estado=Ejemplar.Estado.DISPONIBLE)


class LibroAutor(models.Model):
    """Tabla puente libro ↔ autor; guarda el orden del autor en la portada."""

    orden = models.PositiveSmallIntegerField("orden", default=1)
    autor = models.ForeignKey(
        Autor, on_delete=models.PROTECT, verbose_name="autor"
    )
    libro = models.ForeignKey(
        Libro, on_delete=models.CASCADE, verbose_name="libro"
    )

    class Meta:
        db_table = "libro_autor"
        ordering = ["orden"]
        verbose_name = "autor del libro"
        verbose_name_plural = "autores del libro"
        constraints = [
            models.UniqueConstraint(
                fields=["libro", "autor"], name="uq_libro_autor"
            ),
        ]

    def __str__(self):
        return f"{self.libro} — {self.autor} ({self.orden})"


class Ejemplar(models.Model):
    """Copia física de un libro (CU-18). Su estado dice si se puede prestar."""

    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        RESERVADO = "RESERVADO", "Reservado"
        PRESTADO = "PRESTADO", "Prestado"
        EN_REPARACION = "EN_REPARACION", "En reparación"
        PERDIDO = "PERDIDO", "Perdido"
        BAJA = "BAJA", "Baja"

    codigo_inventario = models.CharField(
        "código de inventario", max_length=30, unique=True
    )
    ubicacion = models.CharField(
        "ubicación", max_length=50, null=True, blank=True
    )
    estado = models.CharField(
        "estado",
        max_length=15,
        choices=Estado.choices,
        default=Estado.DISPONIBLE,
        db_index=True,
    )
    fecha_adquisicion = models.DateField(
        "fecha de adquisición", null=True, blank=True
    )
    observaciones = models.CharField(
        "observaciones", max_length=255, null=True, blank=True
    )
    libro = models.ForeignKey(
        Libro,
        on_delete=models.PROTECT,
        related_name="ejemplares",
        verbose_name="libro",
    )

    class Meta:
        db_table = "ejemplar"
        ordering = ["codigo_inventario"]
        verbose_name = "ejemplar"
        verbose_name_plural = "ejemplares"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=[
                    "DISPONIBLE",
                    "RESERVADO",
                    "PRESTADO",
                    "EN_REPARACION",
                    "PERDIDO",
                    "BAJA",
                ]),
                name="ck_ejemplar_estado",
            ),
        ]

    def __str__(self):
        return f"{self.codigo_inventario} · {self.libro}"

    def es_prestable(self):
        """True si el ejemplar se puede prestar: solo DISPONIBLE (RN-15)."""
        return self.estado == self.Estado.DISPONIBLE

    def cambiar_estado(self, nuevo_estado):
        """Cambia el estado y lo guarda.

        Solo valida que el estado exista. Las reglas de cuándo se permite cada
        cambio viven en los servicios de prestamos y multas, que deben llamar
        a este método dentro de transaction.atomic() con el ejemplar bloqueado
        (select_for_update), como pide RNF-03.
        """
        if nuevo_estado not in self.Estado.values:
            raise ValidationError(f"Estado de ejemplar no válido: {nuevo_estado}")
        self.estado = nuevo_estado
        self.save(update_fields=["estado"])
        