# Sistema de Gestión de Biblioteca Escolar

Proyecto final de Ingeniería de Software · Agosto–Diciembre 2026

## Equipo
- Diego
- Alvaro
- Samanta
- Ricardo

## Stack
Python 3.13 · Django 5.2 · MySQL 8.4 (Docker) · Bootstrap 5 · Visual Paradigm

## Estructura del repositorio
```
CLAUDE.md        Instrucciones del proyecto para Claude Code
docs/            Requerimientos, diagramas UML (.vpp) y diseño de BD
  bd/            esquema_bd_biblioteca.html (referencia principal) y modelo ER original
docker/          Configuración de MySQL en Docker        (Fase 1)
biblioteca/      Configuración de Django                  (Fase 2)
cuentas/, catalogo/, prestamos/, multas/, ...  Apps        (Fase 3+)
```
## Plan de trabajo
El reparto de tareas, los contratos entre apps y el calendario están en
[`PLAN_DE_TRABAJO.md`](PLAN_DE_TRABAJO.md).

## Flujo de trabajo con Git
| Rama | Uso |
|---|---|
| `main` | Solo versiones entregadas (etiquetas `entrega-1`, `entrega-2`, ...) |
| `develop` | Integración del trabajo diario |
| `feature/<tarea>` | Una rama por tarea, sale de `develop` y regresa por Pull Request |

1. `git switch develop && git pull`
2. `git switch -c feature/mi-tarea`
3. Commits pequeños con prefijo: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
4. `git push -u origin feature/mi-tarea` y abrir PR hacia `develop`
5. Otro integrante revisa y aprueba el PR

## Instalación
*(Se completa en la Fase 1 y 2)*

## Levantar la base de datos con Docker

### Requisitos

- Docker Desktop instalado y funcionando.
- Docker Compose.
- Archivo `.env` configurado.

### Configuración

1. Copiar las variables de entorno:

   cp .env.example .env

2. Abrir `.env` y configurar DB_PASSWORD y
   DB_ROOT_PASSWORD con contraseñas seguras.

3. Iniciar MySQL:

   docker compose up -d

4. Verificar el contenedor:

   docker compose ps

5. Conectarse a MySQL:

   docker compose exec db mysql -u biblioteca_app -p biblioteca

### Bases de datos

- biblioteca: base principal para migraciones de Django.
- biblioteca_modelo: referencia del profesor con 18 tablas.
- test_biblioteca: base que Django crea durante las pruebas.

### Scripts de inicialización

Los archivos de docker/mysql/init/ configuran:

- 01_permisos.sql: permisos para pruebas y lectura.
- 02_modelo_referencia.sql: modelo SQL del profesor.

Los scripts se ejecutan automáticamente solo cuando
MySQL inicializa un volumen de datos vacío.

### Importante

No subir el archivo .env al repositorio.

No ejecutar docker compose down -v si se desean
conservar los datos de MySQL.

### Requisitos

- Python 3.13.
- Docker Desktop funcionando.
- Herramientas para instalar mysqlclient.

En macOS:

    brew install mysql-client pkg-config
    export PKG_CONFIG_PATH="$(brew --prefix mysql-client)/lib/pkgconfig"

En WSL/Linux (Ubuntu/Debian):

    sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config

### Entorno virtual

Desde la raíz del repositorio, en macOS:

    python3.13 -m venv .venv
    source .venv/bin/activate

En Windows PowerShell:

    py -3.13 -m venv .venv
    .venv\Scripts\Activate.ps1

En WSL/Linux, con Python 3.13 instalado:

    python3.13 -m venv .venv
    source .venv/bin/activate

Con el entorno activo:

    python -m pip install -r requirements.txt

### Variables de entorno

Copiar .env.example como .env, si todavía no existe.
En macOS o WSL/Linux:

    cp .env.example .env

En PowerShell:

    Copy-Item .env.example .env

Configurar las contraseñas y el puerto de MySQL.
Generar una SECRET_KEY y copiar el resultado al .env:

    python -c "import secrets; print(secrets.token_urlsafe(50))"

Para desarrollo, usar DEBUG=True. No subir .env a Git.

### Iniciar el proyecto

    docker compose up -d
    docker compose ps

Esperar a que MySQL aparezca saludable y ejecutar:

    python manage.py migrate
    python manage.py runserver

Abrir http://127.0.0.1:8000/.
Detener el servidor con Ctrl+C.

El proyecto usa cuentas.Usuario como usuario personalizado.
Las apps catalogo, prestamos, multas, notificaciones y reportes
se incluyen vacías para el desarrollo de cada integrante.
Los correos de desarrollo se muestran en la terminal.