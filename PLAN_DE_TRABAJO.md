# Plan de trabajo · Sistema de Gestión de Biblioteca Escolar

Proyecto final de Ingeniería de Software · Agosto–Diciembre 2026
Equipo: Alvaro, Diego, Ricardo y Samanta · Repo: `ing_software_final` (rama por defecto `develop`)

Este documento dice **qué hace cada integrante, en qué orden y qué depende de quién**.
Sirve para el equipo y para cualquier asistente de IA que usemos (Claude, ChatGPT, Gemini, Copilot, etc.).

---

## 0. Instrucciones para asistentes de IA

Si eres un asistente de IA ayudando a un integrante del equipo:

1. **Pregunta (o identifica) a qué integrante ayudas** y lee solo su sección (4.A, 4.B, 4.C o 4.D), más las secciones 1, 2 y 3.
2. **Trabaja solo dentro de las apps de ese integrante.** No crees ni modifiques modelos, vistas o migraciones de otra app.
3. **Usa los contratos de la sección 3** para comunicarte con otras apps. Si falta una función o un campo de otra app, **no lo implementes tú**: dile al usuario que lo coordine con el dueño de esa app.
4. **La referencia del modelo es `docs/bd/esquema_bd_biblioteca.html`.** Nombres de tablas (`db_table`), campos, tipos, estados y `on_delete` deben coincidir con ese archivo.
5. Código, comentarios, nombres de clases y funciones **en español** (como en los requerimientos). Sigue PEP 8.
6. **Nunca escribas contraseñas ni credenciales** en código, commits o mensajes. Todo va en `.env` (que no se sube).
7. Las reglas de negocio van en **modelos o servicios**, nunca en plantillas (RNF-06).
8. Operaciones de préstamo, devolución y multa dentro de `transaction.atomic` (RNF-03).
9. Antes de proponer cambios grandes, explica el plan y el porqué. El equipo está aprendiendo Django.
10. Requerimientos completos: `docs/requerimientos/requerimientos_proyecto_final.html`.

---

## 1. Resumen del reparto

| Paquete | Responsable | Apps Django | Casos de uso |
|---|---|---|---|
| **A. Usuarios y reportes** | Alvaro | `cuentas`, `reportes` | CU-01, 02, 03, 20, 21, 22, 32 |
| **B. Administración del acervo** | Diego | `catalogo` | CU-04, 05, 16, 17, 18, 19, 33 |
| **C. Préstamos y reservas** | Ricardo | `prestamos` | CU-06 a 13, 23, 24, 30, 31 |
| **D. Multas, devoluciones y procesos automáticos** | Samanta | `multas`, `notificaciones` | CU-14, 15, 25 a 29, 34, 35, 36 |

**Fase 1 (BD en Docker):** la terminan quienes ya la están trabajando. Es la base que todos usamos para conectarnos a MySQL.

### Trabajo de todos

- [ ] Sesión conjunta del **modelo de dominio** (diagrama de clases de análisis), antes de las clases de diseño.
- [ ] **Diagrama general de casos de uso**, con actores y generalización (Usuario lector → Estudiante, Profesor).
- [ ] Lista de **RF, RNF y RN** para el documento de especificación (vienen casi completos del profesor).
- [ ] **Revisar PRs** de los demás: cada PR lo aprueba alguien que no lo escribió.
- [ ] **Cierre:** demo por actor, PDF integrado y `.vpp` final.

---

## 2. Reglas comunes

### Git
- `main`: solo versiones entregadas. `develop`: integración diaria.
- Una rama por tarea: `feature/<app>-<tarea>` (ej. `feature/prestamos-solicitar`). Sale de `develop` y regresa por PR.
- Commits pequeños en español con prefijo: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Antes de empezar el día: `git switch develop && git pull`, y luego actualizar tu rama.

### Archivos compartidos
`settings.py`, `biblioteca/urls.py`, `templates/base.html` y `requirements.txt` los tocamos todos.
Cambios ahí van en **PRs pequeños** y se avisan en el grupo.

### Migraciones
- Nadie toca las migraciones de una app que no es suya.
- Nunca se edita ni se borra una migración que ya esté en `develop`.
- Antes de `makemigrations`: `git pull` de `develop`.
- Orden de integración por llaves foráneas: `cuentas` → `catalogo` → `prestamos` → `multas` / `notificaciones`.

### Visual Paradigm
- El `.vpp` es binario; Git no puede mezclar cambios de dos personas.
- Cada quien trabaja sus diagramas en su propio `.vpp`; un integrador los junta con *File › Import*.
- Si la importación no funciona, se trabaja por turnos avisando en el grupo.
- Imágenes exportadas en `docs/uml/` (PNG), con el nombre del diagrama.

### Documentos de texto
Descripciones de casos de uso y documento de requerimientos en el Google Doc compartido.
Cada caso de uso usa la **plantilla de la sección 8** de los requerimientos (16 campos).

### Sesión semanal
Miércoles 5:30–8:30 pm (tentativo).

---

## 3. Contratos entre paquetes

Estas son las piezas que un paquete le **entrega** a otro. Los nombres son una propuesta: el dueño puede cambiarlos, pero **debe avisar** y actualizar esta tabla.

| Qué | Dónde vive | Lo provee | Lo usan |
|---|---|---|---|
| Modelo `Usuario` (`AbstractUser`) con `tipo_usuario`, `bloqueado` | `cuentas/models.py` | A | Todos |
| Modelos `Estudiante`, `Profesor`, `Carrera`, `Departamento` | `cuentas/models.py` | A | B (sugerencias, datos de prueba), reportes |
| `BibliotecarioRequeridoMixin`, `LectorRequeridoMixin`, `ProfesorRequeridoMixin` | `cuentas/mixins.py` | A | B, C, D |
| Plantilla `base.html` (Bootstrap 5, navbar por rol, bloque de mensajes) | `templates/base.html` | A | B, C, D |
| Modelos `Libro`, `Ejemplar`, `Autor`, `Editorial`, `Categoria` | `catalogo/models.py` | B | C, D, reportes |
| `Libro.ejemplares_disponibles()` y `Ejemplar.es_prestable()` (RN-15) | `catalogo/models.py` | B | C |
| Comando `cargar_datos_prueba` | `catalogo/management/commands/` | B | Todos (para probar) |
| `PoliticaPrestamo.para(usuario)` | `prestamos/models.py` | C | D |
| `verificar_elegibilidad(usuario)` → lista de motivos de rechazo (CU-07) | `prestamos/services.py` | C | C (internamente) |
| `tiene_prestamos_vencidos(usuario)` | `prestamos/services.py` | C | C, D |
| Métodos de estado de `Prestamo`: `entregar()`, `marcar_vencido()`, `marcar_devuelto()`, `marcar_perdido()` | `prestamos/models.py` | C | D |
| `asignar_siguiente_reserva(ejemplar)` (RN-12) | `prestamos/services.py` | C | D (devolución y expiraciones) |
| `Reserva.expirar()` y expiración de solicitudes | `prestamos/models.py` | C | D (comando de vencimientos) |
| `tiene_multas_pendientes(usuario)` (RN-08) | `multas/services.py` | D | C |
| `notificar(usuario, tipo, mensaje)` | `notificaciones/services.py` | D | C, B (opcional) |

**Dependencia circular a cuidar:** `prestamos` necesita saber si hay multas pendientes (RN-08), y `multas` tiene llave foránea a `prestamo`.
Para evitar el import circular, C importa `tiene_multas_pendientes` **dentro de la función** `verificar_elegibilidad`, no al inicio del archivo.

---

## 4. Tareas por integrante

### 4.A · Usuarios y reportes — Alvaro

**Apps:** `cuentas`, `reportes` · **Tablas:** `usuario`, `estudiante`, `profesor`, `carrera`, `departamento`
**Requerimientos:** RF-01, RF-11, RF-14 · RNF-01, RNF-02, RNF-04

**Casos de uso:**

| ID | Caso de uso |
|---|---|
| CU-01 | Iniciar sesión |
| CU-02 | Cerrar sesión |
| CU-03 | Recuperar contraseña |
| CU-20 | Gestionar usuarios |
| CU-21 | Importar usuarios desde CSV |
| CU-22 | Bloquear / desbloquear usuario |
| CU-32 | Generar reportes |

> ⚠️ **A bloquea al resto del código.** El modelo `Usuario` y `AUTH_USER_MODEL` deben existir **antes del primer `migrate`**. Si alguien migra antes, hay que borrar la base y empezar de nuevo. Prioridad de esta semana.

**Esqueleto de Django (primero, semana 2):**
- [ ] `venv` y `requirements.txt` inicial: `Django>=5.2,<5.3`, `mysqlclient`, `python-dotenv`, `pytest-django`.
- [ ] Documentar en el README que en WSL/Linux `mysqlclient` necesita antes: `sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config`.
- [ ] `django-admin startproject biblioteca .` en la raíz del repo.
- [ ] `settings.py` leyendo `.env` con `python-dotenv`: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`; `OPTIONS: {"charset": "utf8mb4"}`.
- [ ] `TIME_ZONE = "America/Mexico_City"`, `LANGUAGE_CODE = "es-mx"`, `USE_TZ = True`.
- [ ] Crear las 6 apps vacías y registrarlas en `INSTALLED_APPS`, para que cada dueño empiece en su carpeta.
- [ ] App `cuentas` con `Usuario` y `AUTH_USER_MODEL = "cuentas.Usuario"`; primer `migrate` contra el MySQL de Docker.
- [ ] `EMAIL_BACKEND` de consola para desarrollo (CU-03).
- [ ] `templates/base.html` con Bootstrap 5, navbar según el rol y bloque de mensajes.
- [ ] Mixins de rol en `cuentas/mixins.py`.
- [ ] Sección "Instalación" del README: venv, requirements, `.env`, Docker, `migrate`, `runserver`.

**Documentación:**
- [ ] Descripción de sus 7 casos de uso con la plantilla.
- [ ] Diagrama de casos de uso del paquete "Usuarios y reportes".
- [ ] Clases de diseño de `cuentas` y `reportes`.
- [ ] **Wireframes** del sistema: coordina el estilo; cada dueño le pasa la lista de pantallas de su paquete.
- [ ] **Diagramas de estados** de Préstamo y de Ejemplar (sección 10.3), validados con C y B.

**Código:**
- [ ] Modelos `Usuario`, `Estudiante`, `Profesor` (uno a uno con `Usuario`), `Carrera`, `Departamento`, con `db_table` del esquema.
- [ ] Registro en Django Admin.
- [ ] Login, logout y recuperación de contraseña con las vistas de autenticación de Django.
- [ ] Un usuario `bloqueado` no puede operar préstamos (C lo revisa en la elegibilidad); mostrar el motivo al usuario.
- [ ] CRUD de usuarios para el bibliotecario, con vistas propias (no solo Admin).
- [ ] Importación CSV: validar columnas, reportar filas con error y guardar todo en una transacción.
- [ ] Bloquear / desbloquear con `motivo_bloqueo` obligatorio.
- [ ] **Reportes** (semana 6, cuando ya existan los datos de C y D): préstamos por periodo, libros más solicitados, préstamos vencidos, multas cobradas y pendientes.

**Pruebas:**
- [ ] Un estudiante no puede entrar a vistas de bibliotecario (RNF-01, RNF-02).
- [ ] Importación CSV con filas válidas e inválidas.
- [ ] Bloqueo y desbloqueo.

---

### 4.B · Administración del acervo — Diego

**App:** `catalogo` · **Tablas:** `autor`, `editorial`, `categoria`, `libro`, `libro_autor`, `ejemplar`, `sugerencia_adquisicion`
**Requerimientos:** RF-02, RF-10, RF-16 · RNF-05 · RN-15

**Casos de uso:**

| ID | Caso de uso |
|---|---|
| CU-04 | Buscar libros en el catálogo |
| CU-05 | Consultar detalle de libro |
| CU-16 | Sugerir adquisición de libro (profesor) |
| CU-17 | Gestionar libros |
| CU-18 | Gestionar ejemplares |
| CU-19 | Gestionar autores, editoriales y categorías |
| CU-33 | Atender sugerencias de adquisición |

**Documentación:**
- [ ] Descripción de sus 7 casos de uso con la plantilla.
- [ ] Diagrama de casos de uso del paquete "Administración del acervo".
- [ ] Clases de diseño de `catalogo`.
- [ ] **Diagrama ER físico en Visual Paradigm**, igual a las tablas que generen las migraciones.
- [ ] **Diccionario de datos** de todas las tablas (columna, tipo, restricciones, descripción).
- [ ] Lista de pantallas del paquete para los wireframes de A.

**Código:**
- [ ] Modelos `Autor`, `Editorial`, `Categoria`, `Libro`, `LibroAutor` (`ManyToManyField` con `through`), `Ejemplar`, `SugerenciaAdquisicion`, con `db_table`, índices y CHECKs del esquema.
- [ ] `Ejemplar.es_prestable()`: solo `DISPONIBLE` se presta (RN-15).
- [ ] `Libro.ejemplares_disponibles()`.
- [ ] Baja lógica: `Libro.activo = False` y ejemplar en estado `BAJA`; nunca borrado físico.
- [ ] Búsqueda por título, autor, ISBN, categoría y editorial, mostrando disponibilidad (RF-02).
- [ ] Listados paginados con `select_related` / `prefetch_related`; menos de 2 segundos con 10,000 libros (RNF-05).
- [ ] Detalle de libro con botones "Solicitar préstamo" o "Reservar" que llevan a las vistas de C (CU-05 → CU-06 / CU-11).
- [ ] CRUD de libros, ejemplares, autores, editoriales y categorías para el bibliotecario.
- [ ] Portada con `ImageField`: agregar `Pillow` a `requirements.txt` y configurar `MEDIA_ROOT` / `MEDIA_URL`.
- [ ] Sugerencias: el profesor las crea; el bibliotecario las aprueba o rechaza con respuesta.
- [ ] Comando `cargar_datos_prueba`: al menos 50 libros, 100 ejemplares, 20 estudiantes, 5 profesores y 2 bibliotecarios. Que acepte un parámetro para generar 10,000 libros y medir RNF-05.

**Pruebas:**
- [ ] `es_prestable()` con cada estado del ejemplar.
- [ ] Búsqueda por cada criterio.
- [ ] Unicidad de ISBN y de código de inventario.

---

### 4.C · Préstamos y reservas — Ricardo

**App:** `prestamos` · **Tablas:** `politica_prestamo`, `prestamo`, `reserva`
**Requerimientos:** RF-03, RF-04, RF-05 (entrega), RF-07, RF-08, RF-09, RF-13 · RNF-03 · RN-01, 02, 03, 06, 08, 09, 10, 11, 12

**Casos de uso:**

| ID | Caso de uso |
|---|---|
| CU-06 | Solicitar préstamo de libro |
| CU-07 | Verificar elegibilidad del usuario |
| CU-08 | Cancelar solicitud de préstamo |
| CU-09 | Consultar mis préstamos |
| CU-10 | Renovar préstamo |
| CU-11 | Reservar libro no disponible |
| CU-12 | Cancelar reserva |
| CU-13 | Consultar historial de préstamos |
| CU-23 | Entregar préstamo (atender solicitud) |
| CU-24 | Registrar préstamo en mostrador |
| CU-30 | Gestionar reservas |
| CU-31 | Configurar políticas de préstamo |

> Es el paquete más grande y el corazón del sistema. Los demás dependen de sus servicios (sección 3).

**Documentación:**
- [ ] Descripción de sus 12 casos de uso (CU-06 y CU-10 ya vienen como ejemplo del profesor).
- [ ] Diagrama de casos de uso del paquete "Préstamos y reservas".
- [ ] Clases de diseño de `prestamos`.
- [ ] **Secuencia CU-06** (con fragmento `alt` para usuario no elegible).
- [ ] **Secuencia CU-10** (renovar).
- [ ] **Secuencia CU-11** (reservar).
- [ ] **Actividades:** proceso completo de préstamo y devolución con carriles (Usuario lector, Sistema, Bibliotecario).
- [ ] Lista de pantallas del paquete para los wireframes de A.

**Código:**
- [ ] Modelos `PoliticaPrestamo`, `Prestamo`, `Reserva`, con `db_table` y estados del esquema.
- [ ] Migración de datos con las políticas predeterminadas: estudiante 7 días / 3 libros / 1 renovación; profesor 30 / 10 / 2; ambos $10 por día, tope $300 y 48 h para recoger.
- [ ] `verificar_elegibilidad(usuario)` (CU-07): cuenta activa y no bloqueada, sin multas pendientes ni préstamos vencidos (RN-08), debajo del máximo de libros (RN-02), sin el mismo título prestado (RN-11).
- [ ] Solicitar préstamo (CU-06) en transacción con `select_for_update()`: ejemplar → `RESERVADO`, préstamo `SOLICITADO`, `fecha_limite_recoger` según RN-06, notificación al usuario.
- [ ] Cancelar solicitud (CU-08): préstamo `CANCELADO`, ejemplar `DISPONIBLE`.
- [ ] Entregar (CU-23) y préstamo en mostrador (CU-24): estado `ACTIVO`, `fecha_vencimiento` según RN-01, `entregado_por`.
- [ ] Renovar (CU-10): RN-03, RN-09 y RN-10 (la nueva fecha cuenta desde el día de la renovación).
- [ ] Reservar y cancelar reserva (CU-11, CU-12) con cola FIFO por `fecha_reserva`.
- [ ] `asignar_siguiente_reserva(ejemplar)` (RN-12): reserva más antigua → `DISPONIBLE`, ejemplar apartado, `fecha_expiracion`, notificación.
- [ ] Métodos de estado de `Prestamo` que usará D (sección 3).
- [ ] Mis préstamos e historial (CU-09, CU-13): cada usuario ve solo lo suyo (RNF-02).
- [ ] Gestión de reservas y configuración de políticas para el bibliotecario (CU-30, CU-31).

**Pruebas (cubren la mayor parte de RNF-07):**
- [ ] RN-01: fecha de vencimiento por tipo de usuario.
- [ ] RN-02: máximo de libros.
- [ ] RN-03: máximo de renovaciones.
- [ ] RN-06: expiración de la solicitud.
- [ ] RN-08: rechazo con multas pendientes o préstamos vencidos.
- [ ] RN-09: no renovar vencidos ni títulos con reservas.
- [ ] RN-10: nueva fecha de vencimiento al renovar.
- [ ] RN-11: no dos préstamos del mismo título.

---

### 4.D · Multas, devoluciones y procesos automáticos — Samanta

**Apps:** `multas`, `notificaciones` · **Tablas:** `multa`, `pago`, `notificacion`
**Requerimientos:** RF-05 (devolución), RF-06, RF-07 (multas), RF-12, RF-15, RF-17 · RNF-03 · RN-04, 05, 07, 13, 14, 16

**Casos de uso:**

| ID | Caso de uso |
|---|---|
| CU-14 | Consultar mis multas |
| CU-15 | Consultar notificaciones |
| CU-25 | Registrar devolución |
| CU-26 | Generar multa por retraso |
| CU-27 | Registrar pérdida o daño de ejemplar |
| CU-28 | Registrar pago de multa |
| CU-29 | Condonar multa |
| CU-34 | Marcar préstamos vencidos |
| CU-35 | Expirar solicitudes y reservas no atendidas |
| CU-36 | Enviar recordatorios de vencimiento |

**Documentación:**
- [ ] Descripción de sus 10 casos de uso (CU-25 ya viene como ejemplo del profesor).
- [ ] Diagrama de casos de uso del paquete "Multas".
- [ ] Clases de diseño de `multas` y `notificaciones`.
- [ ] **Secuencia CU-25** (con fragmento `opt` para retraso).
- [ ] **Actividades:** cálculo y cobro de multas (retraso, tope, pago o condonación).
- [ ] **Actividades:** atención de reservas en cola FIFO al devolverse un ejemplar.
- [ ] Lista de pantallas del paquete para los wireframes de A.

**Código:**
- [ ] Modelos `Multa`, `Pago`, `Notificacion`, con `db_table` y estados del esquema.
- [ ] `notificar(usuario, tipo, mensaje)` y `tiene_multas_pendientes(usuario)` (sección 3). **Estos dos los necesita C pronto.**
- [ ] Registrar devolución (CU-25) en una sola transacción:
    - préstamo devuelto con el método de C;
    - multa por retraso si aplica (RN-07);
    - ejemplar `DISPONIBLE`, o apartado con `asignar_siguiente_reserva` si hay reservas (RN-12).
- [ ] Cálculo RN-07: `monto = min(días_retraso × multa_por_día, multa_máxima)`.
- [ ] Pérdida o daño (CU-27, RN-13): multa por el `costo_reposicion` del libro; ejemplar `PERDIDO` o `EN_REPARACION`.
- [ ] Pagos parciales (CU-28): la multa pasa a `PAGADA` cuando la suma de pagos cubre el monto; folio único.
- [ ] Condonar (CU-29, RN-14): solo bibliotecario, justificación obligatoria, guarda quién condonó.
- [ ] RN-16: multas y pagos nunca se borran (sin vistas de borrado y sin permiso de borrado en Admin).
- [ ] Mis multas y mis notificaciones (CU-14, CU-15), con contador de no leídas en la navbar (coordinar con A).
- [ ] Comando `procesar_vencimientos` (CU-34, 35, 36). Va en `prestamos/management/commands/`, como sugiere el profesor. Es la **única excepción** a "no tocar la app de otro": D es dueño de ese archivo y usa los métodos de C.
    - `ACTIVO` con fecha vencida → `VENCIDO`.
    - Solicitudes y reservas no recogidas a tiempo → `EXPIRADO` / `EXPIRADA`, liberando el ejemplar o pasándolo a la siguiente reserva.
    - Recordatorio `VENCE_PRONTO` antes del vencimiento (días a definir con el equipo).

**Pruebas:**
- [ ] RN-07 con casos límite: 0 días, 1 día, varios días y tope máximo (lo pide el profesor en CU-25).
- [ ] Pago parcial y pago completo.
- [ ] Condonación sin justificación rechazada.
- [ ] El comando marca vencidos y expira solicitudes y reservas.

---

## 5. Calendario por semana

Fechas tentativas; posiblemente solo haya una fecha de entrega final.

| Semana | A · Alvaro | B · Diego | C · Ricardo | D · Samanta |
|---|---|---|---|---|
| **2** · 26 oct–1 nov | **Esqueleto Django** + CU del paquete | CU del paquete | CU del paquete | CU del paquete |
| **3** · 2–8 nov | Modelos `cuentas`; diagramas de estados | Modelos `catalogo`; ER y diccionario | Modelos `prestamos`; secuencias | Modelos `multas` y `notificaciones`; secuencia CU-25 |
| **4** · 9–15 nov | Login, roles, usuarios; wireframes | Búsqueda y CRUD; datos de prueba | Solicitar, entregar, elegibilidad | `notificar`, multas pendientes; devolución |
| **5** · 16–22 nov | CSV y bloqueo | Sugerencias; rendimiento | Renovar y reservas | Pagos, condonación, pérdida o daño |
| **6** · 23–29 nov | **Reportes** | Pruebas + apoyo en integración | Pruebas RN-01 a RN-11 | Comando de vencimientos + pruebas |
| **7** · 30 nov–4 dic | Demo, PDF integrado y `.vpp` final (todos) | | | |

**Todos, semanas 2–3:** sesión del modelo de dominio y diagrama general de casos de uso.
