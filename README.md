# Sistema de Gestión de Biblioteca Escolar

Proyecto final de Ingeniería de Software · Agosto–Diciembre 2026

## Equipo
- Diego ...
- ...
- ...
- ...

## Stack
Python 3.12 · Django 5.2 · MySQL 8.4 (Docker) · Bootstrap 5 · Visual Paradigm

## Estructura del repositorio
```
CLAUDE.md        Instrucciones del proyecto para Claude Code
docs/            Requerimientos, diagramas UML (.vpp) y diseño de BD
  bd/            esquema_bd_biblioteca.html (referencia principal) y modelo ER original
docker/          Configuración de MySQL en Docker        (Fase 1)
biblioteca/      Configuración de Django                  (Fase 2)
cuentas/, catalogo/, prestamos/, multas/, ...  Apps        (Fase 3+)
```

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
