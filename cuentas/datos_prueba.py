"""Usuarios de prueba (los usa el comando cargar_datos_prueba de catalogo).

Todos comparten la contraseña CONTRASENA_PRUEBA. Cargar dos veces no
duplica nada: cada usuario se busca por su username antes de crearlo.
"""
from django.contrib.auth.hashers import make_password

from .models import Carrera, Departamento, Estudiante, Profesor, Usuario

CONTRASENA_PRUEBA = "biblioteca2026"

CARRERAS = [
    ("ISTI", "Ingeniería en Sistemas y Tecnologías de la Información"),
    ("IIND", "Ingeniería Industrial"),
    ("ADM", "Administración de Empresas"),
    ("DER", "Derecho"),
    ("PSI", "Psicología"),
    ("ARQ", "Arquitectura"),
]

DEPARTAMENTOS = [
    "Ingeniería",
    "Ciencias Básicas",
    "Economía y Negocios",
    "Humanidades",
    "Ciencias Sociales",
]

# (username, nombre, apellidos)
BIBLIOTECARIOS = [
    ("biblio1", "Laura", "Méndez Ortiz"),
    ("biblio2", "Jorge", "Salinas Ruiz"),
]

PROFESORES = [
    ("prof1", "Ricardo", "Herrera Lozano"),
    ("prof2", "Patricia", "Gómez Vargas"),
    ("prof3", "Alberto", "Navarro Cruz"),
    ("prof4", "Claudia", "Romero Aguilar"),
    ("prof5", "Fernando", "Ibarra Soto"),
]

ESTUDIANTES = [
    ("est01", "Ana", "García López"),
    ("est02", "Luis", "Martínez Pérez"),
    ("est03", "María", "Hernández Torres"),
    ("est04", "Carlos", "Ramírez Flores"),
    ("est05", "Sofía", "Sánchez Morales"),
    ("est06", "Diego", "Castillo Reyes"),
    ("est07", "Valeria", "Jiménez Ruiz"),
    ("est08", "Andrés", "Vázquez Díaz"),
    ("est09", "Fernanda", "Rojas Mendoza"),
    ("est10", "Emilio", "Chávez Guzmán"),
    ("est11", "Camila", "Ortega Silva"),
    ("est12", "Javier", "Delgado Núñez"),
    ("est13", "Regina", "Castro Medina"),
    ("est14", "Mateo", "Rivera Campos"),
    ("est15", "Daniela", "Fuentes Vega"),
    ("est16", "Sebastián", "Moreno Ríos"),
    ("est17", "Ximena", "Cruz Herrera"),
    ("est18", "Alejandro", "Peña Contreras"),
    ("est19", "Paula", "Luna Domínguez"),
    ("est20", "Santiago", "Estrada Rosales"),
]


def _usuario(username, nombre, apellidos, tipo, clave_hash, **extra):
    usuario, nuevo = Usuario.objects.get_or_create(
        username=username,
        defaults={
            "first_name": nombre,
            "last_name": apellidos,
            "email": f"{username}@escuela.mx",
            "tipo_usuario": tipo,
            "password": clave_hash,
            **extra,
        },
    )
    return usuario, nuevo


def cargar_usuarios():
    """Crea carreras, departamentos, bibliotecarios, profesores y estudiantes.

    Devuelve un dict con cuántos registros nuevos se crearon de cada tipo.
    """
    # Se calcula el hash una sola vez: hacerlo por usuario tarda segundos.
    clave_hash = make_password(CONTRASENA_PRUEBA)
    creados = dict.fromkeys(
        ["carreras", "departamentos", "bibliotecarios", "profesores", "estudiantes"],
        0,
    )

    carreras = []
    for clave, nombre in CARRERAS:
        carrera, nueva = Carrera.objects.get_or_create(
            clave=clave, defaults={"nombre": nombre}
        )
        carreras.append(carrera)
        creados["carreras"] += nueva

    departamentos = []
    for nombre in DEPARTAMENTOS:
        departamento, nuevo = Departamento.objects.get_or_create(nombre=nombre)
        departamentos.append(departamento)
        creados["departamentos"] += nuevo

    for username, nombre, apellidos in BIBLIOTECARIOS:
        _, nuevo = _usuario(
            username,
            nombre,
            apellidos,
            Usuario.TipoUsuario.BIBLIOTECARIO,
            clave_hash,
            is_staff=True,
        )
        creados["bibliotecarios"] += nuevo

    for i, (username, nombre, apellidos) in enumerate(PROFESORES, start=1):
        usuario, nuevo = _usuario(
            username, nombre, apellidos, Usuario.TipoUsuario.PROFESOR, clave_hash
        )
        Profesor.objects.get_or_create(
            usuario=usuario,
            defaults={
                "num_empleado": f"EMP-{i:04d}",
                "departamento": departamentos[(i - 1) % len(departamentos)],
            },
        )
        creados["profesores"] += nuevo

    for i, (username, nombre, apellidos) in enumerate(ESTUDIANTES, start=1):
        usuario, nuevo = _usuario(
            username, nombre, apellidos, Usuario.TipoUsuario.ESTUDIANTE, clave_hash
        )
        Estudiante.objects.get_or_create(
            usuario=usuario,
            defaults={
                "matricula": f"A{2026000 + i}",
                "semestre": (i % 9) + 1,
                "carrera": carreras[(i - 1) % len(carreras)],
            },
        )
        creados["estudiantes"] += nuevo

    return creados