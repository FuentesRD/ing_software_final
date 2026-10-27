# CLAUDE.md — Sistema de Gestión de Biblioteca Escolar

Proyecto final de Ingeniería de Software (Universidad Anáhuac, ago–dic 2026).
Equipo de 4 integrantes. Documentos de referencia en `docs/`:

- `docs/requerimientos_proyecto_final.html`: requerimientos completos. Léelo antes de implementar cualquier
  caso de uso (CU-XX), regla (RN-XX) o requerimiento (RF/RNF-XX).
- `docs/esquema_bd_biblioteca.html`: **referencia principal del modelo.** Es el esquema real de la implementación
  del profesor en Django (generado desde `information_schema`): tipos exactos, nombres de CHECK e índices,
  `on_delete`, app de cada modelo, métodos de modelo (sección 6) y datos de prueba. Si difiere del `.sql`, **manda este**.
- `docs/biblioteca_modelo_er.sql`: diseño original de la base. Referencia secundaria: **no lo ejecutes.**

## Forma de trabajar

- Antes de escribir código, lee `PLAN_DE_TRABAJO.md`: pregunta a qué integrante ayudas y trabaja solo en las apps de su sección.
- Responde y comenta siempre en **español**. Identificadores de código en español (como en los requerimientos).
- Quien te usa está aprendiendo Django: antes de cambios grandes explica el plan y el **por qué**; después, resume qué archivos tocaste.
- Cuando el usuario deba ejecutar algo él mismo, indica en qué terminal (PowerShell en Windows o bash en WSL/Linux) y recuérdale que debe estar en la raíz del repo con el entorno virtual activo (el prompt empieza con `(.venv)`).- Trabaja en pasos pequeños y verificables. Después de cada cambio de modelos: `makemigrations` → `migrate` → pruebas.
- Commits pequeños y descriptivos en español (`feat(prestamos): solicitar préstamo CU-06`). No hagas push sin que te lo pidan.
- Nunca escribas contraseñas ni credenciales en código, commits o mensajes. Nunca subas `.env`.
  Cuando se necesite el `.env`, avisa al usuario: lo crea en la raíz del repo copiando `.env.example` (`cp .env.example .env` en bash o `Copy-Item .env.example .env` en PowerShell) y llena las contraseñas con su editor.
## Entorno

- El equipo trabaja en Windows (CMD/PowerShell) y en WSL/Linux (bash). Python 3.13, Django 5.2 (LTS), Git, Docker Desktop. Si no sabes en cuál está el usuario, pregúntale antes de darle comandos.
- venv **propio** del proyecto en `.venv` (no usar venvs de otros proyectos).
  Activar en PowerShell con `.venv\Scripts\Activate.ps1`, en CMD con `.venv\Scripts\activate.bat`, en bash (WSL/Linux) con `source .venv/bin/activate`.
- Conector `mysqlclient`. Variables de entorno con `python-dotenv`.

### Base de datos: MySQL 8.4 con Docker Compose

Cada integrante levanta su propia base idéntica con `docker-compose.yml` (versionado en el repo):

- Imagen `mysql:8.4`, contenedor `biblioteca-mysql`, volumen con nombre para los datos.
- `utf8mb4` / `utf8mb4_0900_ai_ci`, motor InnoDB.
- Al primer arranque crea la base `DB_NAME` y el usuario `DB_USER` (`biblioteca_app`, host `'%'`) con `DB_PASSWORD`.
- Script en `docker/mysql-init/` que da a `biblioteca_app` permisos sobre `test_biblioteca`
  (las pruebas de Django crean esa base).
- Puerto del host tomado de `DB_PORT`. En la máquina de Eduardo es **3308**
  (el 3307 lo usa otro contenedor, `mysql-trabajo`, que **no** debe tocarse).

```powershell
docker compose up -d        # levantar la base
docker compose ps           # ver estado
docker compose down         # apagar (los datos se conservan en el volumen)
docker compose down -v      # apagar y BORRAR los datos (pedir confirmación antes)
```

Si Django no conecta (error 2002/10061), revisar que Docker Desktop esté abierto y el contenedor arriba.

`.env` (no se versiona) y `.env.example` (versionado, sin valores reales):
```
DB_NAME=biblioteca
DB_USER=biblioteca_app
DB_PASSWORD=
DB_ROOT_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3308
SECRET_KEY=
DEBUG=True
```

Configuración obligatoria en `settings.py`:
```python
AUTH_USER_MODEL = "cuentas.Usuario"
TIME_ZONE = "America/Mexico_City"
LANGUAGE_CODE = "es-mx"
USE_TZ = True
DATABASES["default"]["OPTIONS"] = {"charset": "utf8mb4"}
```

> ⚠️ **`AUTH_USER_MODEL` debe existir antes del primer `migrate`.** El modelo `cuentas.Usuario` (hereda de `AbstractUser`) se crea y migra primero. Si ya se migró con el usuario por defecto, hay que borrar y recrear la base; avisa al usuario antes de hacerlo.

## Comandos

```powershell
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test                       # todas las pruebas
python manage.py test prestamos             # pruebas de una app
python manage.py procesar_vencimientos      # CU-34, CU-35, CU-36
python manage.py cargar_datos_prueba        # datos de prueba
pip freeze > requirements.txt
```

## Arquitectura

```
biblioteca/        configuración (settings, urls, wsgi)
cuentas/           Usuario, Estudiante, Profesor, Carrera, Departamento, login y roles
catalogo/          Autor, Editorial, Categoria, Libro, LibroAutor, Ejemplar
prestamos/         PoliticaPrestamo, Prestamo, Reserva
  management/commands/procesar_vencimientos.py
multas/            Multa, Pago
notificaciones/    Notificacion
reportes/          vistas de reportes
templates/         plantillas (base.html con Bootstrap 5 por CDN)
static/
docker/mysql-init/ scripts de inicialización de MySQL
docs/              requerimientos, esquema de referencia, modelo ER y artefactos
docker-compose.yml
```

Reglas de diseño:
- Las **reglas de negocio viven en servicios** (`<app>/services.py`) o métodos de modelo, nunca en vistas ni plantillas. Las vistas solo orquestan.
- Préstamo, devolución, renovación, reserva y multas dentro de `transaction.atomic()`; al asignar un ejemplar usar `select_for_update()` (RNF-03).
- Los valores de RN-01 a RN-06 **siempre** se leen de `PoliticaPrestamo` según `tipo_usuario`; nunca hardcodear 7, 30, 10, 300, etc.
- Sin borrado físico de préstamos, multas ni pagos (RN-16). Libros y usuarios usan baja lógica (`activo` / `is_active`).
- Vistas protegidas con `LoginRequiredMixin` / `@login_required` y verificación de rol (`BibliotecarioRequiredMixin`). Un lector solo ve sus propios préstamos y multas (RNF-02).
- Listados paginados (RNF-05). Interfaz en español y responsive (RNF-04). PEP 8 (RNF-06).
- Los modelos se registran en Django Admin, pero las funciones del bibliotecario tienen vistas propias.

## Reglas del modelo (coincidencia con `docs/esquema_bd_biblioteca.html`)

El objetivo es que nuestras migraciones produzcan el mismo esquema que el del profesor (secciones 5 y 6 del HTML).

- Mismos nombres de tabla (`class Meta: db_table = "..."`), columnas, tipos y nulabilidad que el diccionario de datos.
  Ojo con los tipos que genera Django: `PositiveSmallIntegerField` → `smallint unsigned` (p. ej. `semestre`, `orden`),
  `TextField` → `longtext`, `ImageField` → `varchar(100)` (`portada`).
- Apps de cada modelo según el HTML: `SugerenciaAdquisicion` vive en `catalogo`.
- `Estudiante` y `Profesor`: `OneToOneField(Usuario, primary_key=True)` (la PK es `usuario_id`).
- `LibroAutor` es el modelo `through` del `ManyToManyField` entre `Libro` y `Autor`, con `UniqueConstraint` `uq_libro_autor`.
- Estados y catálogos con `models.TextChoices` (valores y etiquetas como en el HTML) **y además** su `CheckConstraint`
  en `Meta.constraints` con el nombre `ck_<tabla>_<campo>` (`ck_usuario_tipo`, `ck_ejemplar_estado`, `ck_multa_monto`,
  `ck_politica_multas`, `ck_estudiante_semestre`, etc.). `TextChoices` solo valida en formularios, no crea el CHECK en MySQL.
- Índices compuestos en `Meta.indexes` con estos nombres: `idx_reserva_libro_fecha`, `idx_multa_usuario_estado`,
  `idx_notificacion_usuario_leida`. Índices simples (`db_index=True`) donde el HTML los muestra
  (`usuario.tipo_usuario`, `autor.apellidos`, `libro.titulo`, `ejemplar.estado`, `prestamo.estado`,
  `prestamo.fecha_vencimiento`, `reserva.estado`, `multa.estado`).
- `on_delete` exactamente como la tabla "Relaciones" del HTML (PROTECT, CASCADE, SET_NULL).
- Valores por defecto en Django (`default=`, `auto_now`, `auto_now_add`, `timezone.now`), como en el HTML.
- Las dos políticas de préstamo iniciales se cargan con una migración de datos.
- Grupo de permisos "Bibliotecarios" (ver sección 7 del HTML).
- Métodos de modelo con los nombres de la sección 6 del HTML: `Usuario.politica`, `Usuario.motivos_no_elegible()`,
  `Usuario.tiene_multas_pendientes()`, `Usuario.tiene_prestamos_vencidos()`, `Prestamo.dias_retraso()`,
  `Prestamo.calcular_multa()`, `Prestamo.renovaciones_restantes()`, `Multa.saldo()`, `Multa.clean()` (RN-14),
  `Ejemplar.se_puede_prestar`, `Reserva.Meta.ordering = ["fecha_reserva"]`.
- RN-02 cuenta como préstamos vigentes los que están en SOLICITADO, ACTIVO y VENCIDO.
- Diferencias aceptables con el `.sql` (sección 8 del HTML): nombres de FK con hash, `ON DELETE NO ACTION` en MySQL,
  sin `DEFAULT` en columnas, tablas del framework y CHECK `>= 0` extra en campos `Positive*Field`.

## Reglas de negocio (resumen; detalle en los requerimientos)

| Regla | Estudiante | Profesor |
|---|---|---|
| RN-01 días de préstamo | 7 | 30 |
| RN-02 máx. libros simultáneos | 3 | 10 |
| RN-03 renovaciones por préstamo | 1 | 2 |
| RN-04 multa por día | $10.00 | $10.00 |
| RN-05 multa máxima por préstamo | $300.00 | $300.00 |
| RN-06 horas para recoger | 48 | 48 |

- RN-07 `monto = min(dias_retraso × multa_por_dia, multa_maxima)`; `dias_retraso = max(fecha_devolucion − fecha_vencimiento, 0)`.
- RN-08 Con multa PENDIENTE o préstamo VENCIDO no puede solicitar, renovar ni reservar.
- RN-09 No se renueva un préstamo vencido ni uno cuyo título tenga reservas pendientes de otros.
- RN-10 La renovación fija `fecha_vencimiento = hoy + dias_prestamo`.
- RN-11 No dos préstamos activos del mismo título por usuario.
- RN-12 Reservas FIFO por `fecha_reserva`; al devolver, el ejemplar se aparta al primero y se le notifica.
- RN-13 Pérdida/daño: multa por `libro.costo_reposicion`.
- RN-14 Solo el bibliotecario condona, con justificación obligatoria.
- RN-15 Ejemplar EN_REPARACION, PERDIDO o BAJA no se presta.
- RN-16 Préstamos y multas no se eliminan.

Estados del préstamo: `SOLICITADO → ACTIVO → (VENCIDO) → DEVUELTO`; también `CANCELADO`, `EXPIRADO`, `PERDIDO`. Ver diagrama 10.3.

## Pruebas

- `django.test.TestCase`, en `<app>/tests/` (un archivo por servicio o regla).
- Cobertura mínima obligatoria: RN-01 a RN-11 (RNF-07).
- El cálculo de multa debe probar casos límite: 0 días, 1 día, varios días y el tope máximo.
- Antes de dar por terminada una tarea, corre las pruebas de la app afectada y reporta el resultado.

## Datos de prueba

Comando `python manage.py cargar_datos_prueba` con al menos: 50 libros, 100 ejemplares,
20 estudiantes, 5 profesores, 2 bibliotecarios y las dos políticas de préstamo.
Como referencia, el profesor usa: 6 carreras, 5 departamentos, 10 categorías, 14 editoriales, 71 autores,
50 libros, 114 ejemplares, 28 usuarios, y préstamos, reservas, multas y pagos en todos sus estados
(las consultas de la sección 9 del HTML deben devolver resultados con nuestros datos).

## Orden de implementación sugerido

1. `git init` + `.gitignore`, `docker-compose.yml` + `docker/mysql-init/`, `.env.example`, venv,
   Django 5.2 + `mysqlclient` + `python-dotenv`, proyecto `biblioteca`, app `cuentas`
   (Usuario, Carrera, Departamento, Estudiante, Profesor) → primer `migrate`, `requirements.txt`, `README.md`, primer commit.
2. `catalogo` (modelos, admin, búsqueda CU-04/CU-05).
3. `prestamos`: política, solicitud (CU-06/07), entrega (CU-23/24), devolución (CU-25).
4. `multas`: generación (CU-26), pago (CU-28), condonación (CU-29).
5. Renovación (CU-10), reservas (CU-11/12/30), comando programado (CU-34/35/36).
6. Notificaciones, sugerencias, reportes, carga CSV, datos de prueba.
