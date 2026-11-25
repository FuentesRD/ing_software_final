"""Datos de prueba del catálogo (los usa el comando cargar_datos_prueba).

Títulos y autores son reales; los ISBN son de prueba: tienen formato y dígito
verificador válidos, pero usan el prefijo 979-9999, que no está asignado.
Cargar dos veces no duplica nada: todo se busca antes de crearlo.
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from .models import (
    Autor,
    Categoria,
    Editorial,
    Ejemplar,
    Libro,
    LibroAutor,
    SugerenciaAdquisicion,
)

# Semilla fija: los mismos datos en la máquina de todos.
SEMILLA = 2026

# (nombre, descripción)
CATEGORIAS = [
    ("Programación", "Lenguajes, algoritmos y estructuras de datos"),
    ("Ingeniería de software", "Diseño, patrones y gestión de proyectos"),
    ("Bases de datos", "Modelado, SQL y sistemas de datos"),
    ("Redes y sistemas", "Redes de computadoras y sistemas operativos"),
    ("Matemáticas", "Cálculo, álgebra, discretas y estadística"),
    ("Administración", "Administración y emprendimiento"),
    ("Literatura mexicana", "Novela, cuento y ensayo de autores mexicanos"),
    ("Literatura universal", "Clásicos y contemporáneos de otros países"),
    ("Ciencia ficción", "Novela de ciencia ficción"),
    ("Historia", "Historia y ensayo histórico"),
]

# (nombre, país)
EDITORIALES = [
    ("Addison-Wesley", "Estados Unidos"),
    ("Alfaguara", "España"),
    ("Anagrama", "España"),
    ("Cengage Learning", "Estados Unidos"),
    ("Fondo de Cultura Económica", "México"),
    ("McGraw-Hill", "Estados Unidos"),
    ("MIT Press", "Estados Unidos"),
    ("No Starch Press", "Estados Unidos"),
    ("O'Reilly Media", "Estados Unidos"),
    ("Pearson", "Reino Unido"),
    ("Penguin Random House", "Estados Unidos"),
    ("Planeta", "España"),
    ("Prentice Hall", "Estados Unidos"),
    ("Wiley", "Estados Unidos"),
]

# Autores como (nombre, apellidos, nacionalidad), en el orden de la portada.
# (título, autores, editorial, categoría, año, páginas, idioma)
LIBROS = [
    # Ingeniería de software
    ("Clean Code", [("Robert C.", "Martin", "Estados Unidos")],
     "Prentice Hall", "Ingeniería de software", 2008, 464, "Inglés"),
    ("The Pragmatic Programmer", [("Andrew", "Hunt", "Reino Unido"),
                                  ("David", "Thomas", "Reino Unido")],
     "Addison-Wesley", "Ingeniería de software", 1999, 352, "Inglés"),
    ("Design Patterns", [("Erich", "Gamma", "Suiza"),
                         ("Richard", "Helm", "Australia"),
                         ("Ralph", "Johnson", "Estados Unidos"),
                         ("John", "Vlissides", "Estados Unidos")],
     "Addison-Wesley", "Ingeniería de software", 1994, 395, "Inglés"),
    ("Head First Design Patterns", [("Eric", "Freeman", "Estados Unidos"),
                                    ("Elisabeth", "Robson", "Estados Unidos")],
     "O'Reilly Media", "Ingeniería de software", 2004, 694, "Inglés"),
    ("Refactoring", [("Martin", "Fowler", "Reino Unido")],
     "Addison-Wesley", "Ingeniería de software", 1999, 431, "Inglés"),
    ("Ingeniería de software: un enfoque práctico",
     [("Roger S.", "Pressman", "Estados Unidos")],
     "McGraw-Hill", "Ingeniería de software", 2010, 777, "Español"),
    ("Ingeniería de software", [("Ian", "Sommerville", "Reino Unido")],
     "Pearson", "Ingeniería de software", 2011, 792, "Español"),
    ("The Mythical Man-Month", [("Frederick P.", "Brooks", "Estados Unidos")],
     "Addison-Wesley", "Ingeniería de software", 1975, 322, "Inglés"),
    ("Domain-Driven Design", [("Eric", "Evans", "Estados Unidos")],
     "Addison-Wesley", "Ingeniería de software", 2003, 560, "Inglés"),
    # Programación
    ("The C Programming Language", [("Brian W.", "Kernighan", "Canadá"),
                                    ("Dennis M.", "Ritchie", "Estados Unidos")],
     "Prentice Hall", "Programación", 1978, 272, "Inglés"),
    ("Introduction to Algorithms", [("Thomas H.", "Cormen", "Estados Unidos"),
                                    ("Charles E.", "Leiserson", "Estados Unidos"),
                                    ("Ronald L.", "Rivest", "Estados Unidos"),
                                    ("Clifford", "Stein", "Estados Unidos")],
     "MIT Press", "Programación", 2009, 1312, "Inglés"),
    ("Structure and Interpretation of Computer Programs",
     [("Harold", "Abelson", "Estados Unidos"),
      ("Gerald Jay", "Sussman", "Estados Unidos")],
     "MIT Press", "Programación", 1985, 657, "Inglés"),
    ("Python Crash Course", [("Eric", "Matthes", "Estados Unidos")],
     "No Starch Press", "Programación", 2019, 544, "Inglés"),
    ("Automate the Boring Stuff with Python",
     [("Al", "Sweigart", "Estados Unidos")],
     "No Starch Press", "Programación", 2019, 592, "Inglés"),
    ("Fluent Python", [("Luciano", "Ramalho", "Brasil")],
     "O'Reilly Media", "Programación", 2015, 792, "Inglés"),
    ("Effective Java", [("Joshua", "Bloch", "Estados Unidos")],
     "Addison-Wesley", "Programación", 2018, 412, "Inglés"),
    # Bases de datos
    ("Database System Concepts", [("Abraham", "Silberschatz", "Estados Unidos"),
                                  ("Henry F.", "Korth", "Estados Unidos"),
                                  ("S.", "Sudarshan", "India")],
     "McGraw-Hill", "Bases de datos", 2019, 1376, "Inglés"),
    ("Fundamentos de sistemas de bases de datos",
     [("Ramez", "Elmasri", "Egipto"),
      ("Shamkant B.", "Navathe", "India")],
     "Pearson", "Bases de datos", 2007, 1040, "Español"),
    ("Designing Data-Intensive Applications",
     [("Martin", "Kleppmann", "Alemania")],
     "O'Reilly Media", "Bases de datos", 2017, 616, "Inglés"),
    # Redes y sistemas
    ("Computer Networking: A Top-Down Approach",
     [("James F.", "Kurose", "Estados Unidos"),
      ("Keith W.", "Ross", "Estados Unidos")],
     "Pearson", "Redes y sistemas", 2016, 864, "Inglés"),
    ("Redes de computadoras", [("Andrew S.", "Tanenbaum", "Países Bajos"),
                               ("David J.", "Wetherall", "Estados Unidos")],
     "Pearson", "Redes y sistemas", 2012, 816, "Español"),
    ("Sistemas operativos modernos", [("Andrew S.", "Tanenbaum", "Países Bajos")],
     "Pearson", "Redes y sistemas", 2009, 1104, "Español"),
    ("Operating System Concepts", [("Abraham", "Silberschatz", "Estados Unidos"),
                                   ("Peter B.", "Galvin", "Estados Unidos"),
                                   ("Greg", "Gagne", "Estados Unidos")],
     "Wiley", "Redes y sistemas", 2018, 976, "Inglés"),
    # Matemáticas
    ("Cálculo de una variable", [("James", "Stewart", "Canadá")],
     "Cengage Learning", "Matemáticas", 2012, 912, "Español"),
    ("Matemáticas discretas y sus aplicaciones",
     [("Kenneth H.", "Rosen", "Estados Unidos")],
     "McGraw-Hill", "Matemáticas", 2004, 912, "Español"),
    ("Álgebra lineal y sus aplicaciones", [("David C.", "Lay", "Estados Unidos")],
     "Pearson", "Matemáticas", 2012, 576, "Español"),
    ("Probabilidad y estadística para ingeniería y ciencias",
     [("Ronald E.", "Walpole", "Estados Unidos"),
      ("Raymond H.", "Myers", "Estados Unidos")],
     "Pearson", "Matemáticas", 2012, 816, "Español"),
    # Administración
    ("Administración", [("Stephen P.", "Robbins", "Estados Unidos"),
                        ("Mary", "Coulter", "Estados Unidos")],
     "Pearson", "Administración", 2014, 720, "Español"),
    ("El método Lean Startup", [("Eric", "Ries", "Estados Unidos")],
     "Penguin Random House", "Administración", 2011, 336, "Español"),
    # Literatura mexicana
    ("Pedro Páramo", [("Juan", "Rulfo", "México")],
     "Fondo de Cultura Económica", "Literatura mexicana", 1955, 128, "Español"),
    ("El llano en llamas", [("Juan", "Rulfo", "México")],
     "Fondo de Cultura Económica", "Literatura mexicana", 1953, 160, "Español"),
    ("La muerte de Artemio Cruz", [("Carlos", "Fuentes", "México")],
     "Fondo de Cultura Económica", "Literatura mexicana", 1962, 336, "Español"),
    ("Como agua para chocolate", [("Laura", "Esquivel", "México")],
     "Planeta", "Literatura mexicana", 1989, 256, "Español"),
    ("Balún Canán", [("Rosario", "Castellanos", "México")],
     "Fondo de Cultura Económica", "Literatura mexicana", 1957, 304, "Español"),
    ("Los de abajo", [("Mariano", "Azuela", "México")],
     "Fondo de Cultura Económica", "Literatura mexicana", 1915, 160, "Español"),
    ("Temporada de huracanes", [("Fernanda", "Melchor", "México")],
     "Penguin Random House", "Literatura mexicana", 2017, 224, "Español"),
    ("El complot mongol", [("Rafael", "Bernal", "México")],
     "Planeta", "Literatura mexicana", 1969, 240, "Español"),
    # Literatura universal
    ("Cien años de soledad", [("Gabriel", "García Márquez", "Colombia")],
     "Penguin Random House", "Literatura universal", 1967, 471, "Español"),
    ("Don Quijote de la Mancha", [("Miguel", "de Cervantes", "España")],
     "Alfaguara", "Literatura universal", 1605, 1376, "Español"),
    ("Rayuela", [("Julio", "Cortázar", "Argentina")],
     "Alfaguara", "Literatura universal", 1963, 736, "Español"),
    ("Ficciones", [("Jorge Luis", "Borges", "Argentina")],
     "Penguin Random House", "Literatura universal", 1944, 224, "Español"),
    ("1984", [("George", "Orwell", "Reino Unido")],
     "Penguin Random House", "Literatura universal", 1949, 352, "Español"),
    ("Los detectives salvajes", [("Roberto", "Bolaño", "Chile")],
     "Anagrama", "Literatura universal", 1998, 624, "Español"),
    # Ciencia ficción
    ("Fundación", [("Isaac", "Asimov", "Estados Unidos")],
     "Penguin Random House", "Ciencia ficción", 1951, 256, "Español"),
    ("Dune", [("Frank", "Herbert", "Estados Unidos")],
     "Penguin Random House", "Ciencia ficción", 1965, 896, "Español"),
    ("Fahrenheit 451", [("Ray", "Bradbury", "Estados Unidos")],
     "Planeta", "Ciencia ficción", 1953, 192, "Español"),
    ("Neuromante", [("William", "Gibson", "Estados Unidos")],
     "Planeta", "Ciencia ficción", 1984, 320, "Español"),
    # Historia
    ("Sapiens: de animales a dioses", [("Yuval Noah", "Harari", "Israel")],
     "Penguin Random House", "Historia", 2011, 496, "Español"),
    ("Armas, gérmenes y acero", [("Jared", "Diamond", "Estados Unidos")],
     "Penguin Random House", "Historia", 1997, 528, "Español"),
    ("El laberinto de la soledad", [("Octavio", "Paz", "México")],
     "Fondo de Cultura Económica", "Historia", 1950, 351, "Español"),
]

# Categorías de libros técnicos: su costo de reposición es más alto.
CATEGORIAS_TECNICAS = {
    "Programación", "Ingeniería de software", "Bases de datos",
    "Redes y sistemas", "Matemáticas",
}

# Estados con los que nacen los ejemplares extra. PRESTADO y RESERVADO no
# van aquí: los produce la carga de prestamos, para que siempre tengan su
# préstamo o reserva correspondiente.
ESTADOS_EXTRA = [
    (Ejemplar.Estado.DISPONIBLE, 85),
    (Ejemplar.Estado.EN_REPARACION, 7),
    (Ejemplar.Estado.PERDIDO, 4),
    (Ejemplar.Estado.BAJA, 4),
]


def isbn_prueba(numero):
    """ISBN-13 de prueba con dígito verificador válido (prefijo 979-9999)."""
    base = f"9799999{numero:05d}"
    suma = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    return base + str((10 - suma % 10) % 10)


def cargar_catalogo():
    """Crea categorías, editoriales, autores, libros y ejemplares.

    Devuelve un dict con cuántos registros nuevos se crearon de cada tipo.
    """
    rng = random.Random(SEMILLA)
    creados = dict.fromkeys(
        ["categorias", "editoriales", "autores", "libros", "ejemplares"], 0
    )

    categorias = {}
    for nombre, descripcion in CATEGORIAS:
        categorias[nombre], nuevo = Categoria.objects.get_or_create(
            nombre=nombre, defaults={"descripcion": descripcion}
        )
        creados["categorias"] += nuevo

    editoriales = {}
    for nombre, pais in EDITORIALES:
        editoriales[nombre], nuevo = Editorial.objects.get_or_create(
            nombre=nombre, defaults={"pais": pais}
        )
        creados["editoriales"] += nuevo

    codigo = 0
    for numero, (titulo, autores, editorial, categoria, anio, paginas,
                 idioma) in enumerate(LIBROS, start=1):
        costo = (
            rng.randrange(900, 1900, 50)
            if categoria in CATEGORIAS_TECNICAS
            else rng.randrange(250, 600, 25)
        )
        libro, nuevo = Libro.objects.get_or_create(
            isbn=isbn_prueba(numero),
            defaults={
                "titulo": titulo,
                "anio_publicacion": anio,
                "num_paginas": paginas,
                "idioma": idioma,
                "costo_reposicion": Decimal(costo),
                "categoria": categorias[categoria],
                "editorial": editoriales[editorial],
            },
        )
        creados["libros"] += nuevo

        for orden, (nombre, apellidos, nacionalidad) in enumerate(autores, start=1):
            autor, nuevo = Autor.objects.get_or_create(
                nombre=nombre,
                apellidos=apellidos,
                defaults={"nacionalidad": nacionalidad},
            )
            creados["autores"] += nuevo
            LibroAutor.objects.get_or_create(
                libro=libro, autor=autor, defaults={"orden": orden}
            )

        # 1 a 3 ejemplares por libro; el primero siempre DISPONIBLE.
        # Estante: una letra por categoría (A, B, C...) y un número del 1 al 6.
        letra = chr(ord("A") + list(categorias).index(categoria))
        estante = f"{letra}-{rng.randint(1, 6)}"
        for copia in range(rng.choice([1, 2, 2, 3, 3])):
            codigo += 1
            if copia == 0:
                estado = Ejemplar.Estado.DISPONIBLE
            else:
                estado = rng.choices(
                    [e for e, _ in ESTADOS_EXTRA],
                    weights=[p for _, p in ESTADOS_EXTRA],
                )[0]
            adquisicion = date(2018, 1, 15) + timedelta(days=rng.randint(0, 3000))
            _, nuevo = Ejemplar.objects.get_or_create(
                codigo_inventario=f"INV-{codigo:05d}",
                defaults={
                    "libro": libro,
                    "estado": estado,
                    "ubicacion": f"Estante {estante}",
                    "fecha_adquisicion": adquisicion,
                },
            )
            creados["ejemplares"] += nuevo

    return creados


# (título, autores, ISBN o None, justificación, estado, respuesta)
SUGERENCIAS = [
    ("Two Scoops of Django", "Daniel Feldroy, Audrey Feldroy", None,
     "Buenas prácticas de Django para el proyecto final de Ingeniería de Software.",
     SugerenciaAdquisicion.Estado.PENDIENTE, None),
    ("Software Architecture: The Hard Parts", "Neal Ford, Mark Richards", None,
     "Lectura complementaria para la materia de Arquitectura de Software.",
     SugerenciaAdquisicion.Estado.APROBADA, "Se compra para el próximo semestre."),
    ("Juego de tronos", "George R. R. Martin", None,
     "Propuesta para el club de lectura.",
     SugerenciaAdquisicion.Estado.RECHAZADA,
     "Fuera del enfoque académico del acervo."),
]


def cargar_sugerencias(profesores):
    """Crea las sugerencias de ejemplo, repartidas entre los profesores dados."""
    creadas = 0
    if not profesores:
        return {"sugerencias": 0}
    for i, (titulo, autores, isbn, justificacion, estado, respuesta) in enumerate(
        SUGERENCIAS
    ):
        _, nueva = SugerenciaAdquisicion.objects.get_or_create(
            titulo=titulo,
            defaults={
                "autores": autores,
                "isbn": isbn,
                "justificacion": justificacion,
                "estado": estado,
                "respuesta": respuesta,
                "profesor": profesores[i % len(profesores)],
            },
        )
        creadas += nueva
    return {"sugerencias": creadas}


def generar_libros_masivos(cantidad):
    """Agrega libros sintéticos (con un ejemplar cada uno) para medir RNF-05.

    Usa bulk_create por lotes: 10,000 libros tardan segundos, no minutos.
    """
    categorias = list(Categoria.objects.all())
    editoriales = list(Editorial.objects.all())
    if not categorias or not editoriales:
        raise ValueError("Primero carga el catálogo base.")

    existentes = Libro.objects.filter(titulo__startswith="Libro de carga ").count()
    nuevos = []
    for i in range(existentes + 1, cantidad + 1):
        nuevos.append(
            Libro(
                isbn=isbn_prueba(10000 + i),
                titulo=f"Libro de carga {i:05d}",
                categoria=categorias[i % len(categorias)],
                editorial=editoriales[i % len(editoriales)],
                costo_reposicion=Decimal(500),
            )
        )
    Libro.objects.bulk_create(nuevos, batch_size=1000)

    libros = Libro.objects.filter(titulo__startswith="Libro de carga ").exclude(
        ejemplares__isnull=False
    )
    Ejemplar.objects.bulk_create(
        [
            Ejemplar(codigo_inventario=f"CAR-{libro.titulo[-5:]}", libro=libro)
            for libro in libros
        ],
        batch_size=1000,
    )
    return {"libros_masivos": len(nuevos)}