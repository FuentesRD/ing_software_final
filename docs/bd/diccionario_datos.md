# Diccionario de datos

Generado con `python manage.py diccionario_datos` a partir de los modelos de Django (tipos de MySQL).

## `usuario`

Modelo: `cuentas.Usuario`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `password` | varchar(128) | No |  |  | Contraseña |
| `last_login` | datetime(6) | Sí |  |  | Último ingreso |
| `is_superuser` | tinyint(1) | No |  | False | Es superusuario |
| `username` | varchar(150) | No | UQ |  | Nombre de usuario |
| `first_name` | varchar(150) | No |  |  | Nombre |
| `last_name` | varchar(150) | No |  |  | Apellido |
| `is_staff` | tinyint(1) | No |  | False | Es staff |
| `is_active` | tinyint(1) | No |  | True | Activo |
| `date_joined` | datetime(6) | No |  | now() | Fecha de creación |
| `email` | varchar(254) | No | UQ |  | Email |
| `tipo_usuario` | varchar(15) | No | Índice |  | Tipo usuario. Valores: ESTUDIANTE · PROFESOR · BIBLIOTECARIO |
| `telefono` | varchar(20) | Sí |  |  | Telefono |
| `bloqueado` | tinyint(1) | No |  | False | Bloqueado |
| `motivo_bloqueo` | varchar(255) | Sí |  |  | Motivo bloqueo |

Restricciones:

- `ck_usuario_tipo`: CHECK (tipo_usuario IN ('ESTUDIANTE', 'PROFESOR', 'BIBLIOTECARIO'))

## `carrera`

Modelo: `cuentas.Carrera`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `clave` | varchar(10) | No | UQ |  | Clave |
| `nombre` | varchar(120) | No |  |  | Nombre |

## `departamento`

Modelo: `cuentas.Departamento`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `nombre` | varchar(120) | No | UQ |  | Nombre |

## `estudiante`

Modelo: `cuentas.Estudiante`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `usuario_id` | bigint | No | PK, FK → usuario |  | Usuario |
| `matricula` | varchar(20) | No | UQ |  | Matricula |
| `semestre` | smallint unsigned | No |  |  | Semestre |
| `carrera_id` | bigint | No | FK → carrera |  | Carrera |

Restricciones:

- `ck_estudiante_semestre`: CHECK (semestre >= 1 AND semestre <= 12)

## `profesor`

Modelo: `cuentas.Profesor`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `usuario_id` | bigint | No | PK, FK → usuario |  | Usuario |
| `num_empleado` | varchar(20) | No | UQ |  | Num empleado |
| `departamento_id` | bigint | No | FK → departamento |  | Departamento |

## `categoria`

Clasificación temática de los libros (CU-04, CU-19).

Modelo: `catalogo.Categoria`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `nombre` | varchar(100) | No | UQ |  | Nombre |
| `descripcion` | varchar(255) | Sí |  |  | Descripción |

## `editorial`

Editoriales de los libros del acervo (CU-19).

Modelo: `catalogo.Editorial`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `nombre` | varchar(150) | No | UQ |  | Nombre |
| `pais` | varchar(60) | Sí |  |  | País |

## `autor`

Autores. Un autor puede tener varios libros (ver LibroAutor).

Modelo: `catalogo.Autor`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `nombre` | varchar(100) | No |  |  | Nombre(s) |
| `apellidos` | varchar(150) | No | Índice |  | Apellidos |
| `nacionalidad` | varchar(60) | Sí |  |  | Nacionalidad |

## `libro`

Título del catálogo. Las copias físicas son Ejemplar (CU-04, CU-05, CU-17).

Modelo: `catalogo.Libro`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `isbn` | varchar(13) | No | UQ |  | Isbn |
| `titulo` | varchar(255) | No | Índice |  | Título |
| `subtitulo` | varchar(255) | Sí |  |  | Subtítulo |
| `anio_publicacion` | smallint unsigned | Sí |  |  | Año de publicación |
| `edicion` | varchar(30) | Sí |  |  | Edición |
| `idioma` | varchar(30) | No |  | 'Español' | Idioma |
| `num_paginas` | smallint unsigned | Sí |  |  | Número de páginas |
| `descripcion` | longtext | Sí |  |  | Descripción |
| `portada` | varchar(100) | Sí |  |  | Portada |
| `costo_reposicion` | decimal(10,2) | No |  | 0 | Costo de reposición |
| `activo` | tinyint(1) | No |  | True | Activo |
| `categoria_id` | bigint | No | FK → categoria |  | Categoría |
| `editorial_id` | bigint | No | FK → editorial |  | Editorial |

## `libro_autor`

Tabla puente libro ↔ autor; guarda el orden del autor en la portada.

Modelo: `catalogo.LibroAutor`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `orden` | smallint unsigned | No |  | 1 | Orden |
| `autor_id` | bigint | No | FK → autor |  | Autor |
| `libro_id` | bigint | No | FK → libro |  | Libro |

Restricciones:

- `uq_libro_autor`: UNIQUE (libro, autor)

## `ejemplar`

Copia física de un libro (CU-18). Su estado dice si se puede prestar.

Modelo: `catalogo.Ejemplar`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `codigo_inventario` | varchar(30) | No | UQ |  | Código de inventario |
| `ubicacion` | varchar(50) | Sí |  |  | Ubicación |
| `estado` | varchar(15) | No | Índice | Ejemplar.Estado.DISPONIBLE | Estado. Valores: DISPONIBLE · RESERVADO · PRESTADO · EN_REPARACION · PERDIDO · BAJA |
| `fecha_adquisicion` | date | Sí |  |  | Fecha de adquisición |
| `observaciones` | varchar(255) | Sí |  |  | Observaciones |
| `libro_id` | bigint | No | FK → libro |  | Libro |

Restricciones:

- `ck_ejemplar_estado`: CHECK (estado IN ('DISPONIBLE', 'RESERVADO', 'PRESTADO', 'EN_REPARACION', 'PERDIDO', 'BAJA'))

## `sugerencia_adquisicion`

Sugerencia de compra de un profesor y su respuesta (CU-16, CU-33).

Modelo: `catalogo.SugerenciaAdquisicion`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `titulo` | varchar(255) | No |  |  | Título |
| `autores` | varchar(255) | No |  |  | Autores |
| `isbn` | varchar(13) | Sí |  |  | Isbn |
| `justificacion` | longtext | No |  |  | Justificación |
| `estado` | varchar(10) | No |  | SugerenciaAdquisicion.Estado.PENDIENTE | Estado. Valores: PENDIENTE · APROBADA · RECHAZADA |
| `respuesta` | varchar(255) | Sí |  |  | Respuesta |
| `fecha` | datetime(6) | No |  | fecha y hora al crear | Fecha |
| `profesor_id` | bigint | No | FK → profesor |  | Profesor |

Restricciones:

- `ck_sugerencia_estado`: CHECK (estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA'))

## `politica_prestamo`

Parámetros de préstamo por tipo de usuario lector (RN-01 a RN-06).

Modelo: `prestamos.PoliticaPrestamo`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `tipo_usuario` | varchar(15) | No | UQ |  | Tipo de usuario. Valores: ESTUDIANTE · PROFESOR |
| `dias_prestamo` | smallint unsigned | No |  |  | Días de préstamo |
| `max_libros` | smallint unsigned | No |  |  | Máximo de libros |
| `max_renovaciones` | smallint unsigned | No |  |  | Máximo de renovaciones |
| `multa_por_dia` | decimal(8,2) | No |  |  | Multa por día |
| `multa_maxima` | decimal(8,2) | No |  |  | Multa máxima |
| `horas_para_recoger` | smallint unsigned | No |  |  | Horas para recoger |
| `actualizado_en` | datetime(6) | No |  | fecha y hora al guardar | Actualizado en |

Restricciones:

- `ck_politica_multas`: CHECK (multa_maxima >= 0 AND multa_por_dia >= 0)
- `ck_politica_tipo`: CHECK (tipo_usuario IN ('ESTUDIANTE', 'PROFESOR'))

## `prestamo`

Préstamo de un ejemplar a un usuario lector, de la solicitud a la devolución.

Modelo: `prestamos.Prestamo`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `estado` | varchar(12) | No | Índice | Prestamo.Estado.SOLICITADO | Estado. Valores: SOLICITADO · ACTIVO · VENCIDO · DEVUELTO · CANCELADO · EXPIRADO · PERDIDO |
| `fecha_solicitud` | datetime(6) | No |  | now() | Fecha de solicitud |
| `fecha_limite_recoger` | datetime(6) | Sí |  |  | Límite para recoger |
| `fecha_prestamo` | datetime(6) | Sí |  |  | Fecha de préstamo |
| `fecha_vencimiento` | date | Sí | Índice |  | Fecha de vencimiento |
| `fecha_devolucion` | datetime(6) | Sí |  |  | Fecha de devolución |
| `num_renovaciones` | smallint unsigned | No |  | 0 | Renovaciones |
| `observaciones` | varchar(255) | Sí |  |  | Observaciones |
| `ejemplar_id` | bigint | No | FK → ejemplar |  | Ejemplar |
| `entregado_por_id` | bigint | Sí | FK → usuario |  | Entregado por |
| `recibido_por_id` | bigint | Sí | FK → usuario |  | Recibido por |
| `usuario_id` | bigint | No | FK → usuario |  | Usuario |

Restricciones:

- `ck_prestamo_estado`: CHECK (estado IN ('SOLICITADO', 'ACTIVO', 'VENCIDO', 'DEVUELTO', 'CANCELADO', 'EXPIRADO', 'PERDIDO'))

## `reserva`

Reserva de un libro sin ejemplares disponibles; cola FIFO por fecha_reserva (RN-12).

Modelo: `prestamos.Reserva`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `estado` | varchar(12) | No | Índice | Reserva.Estado.PENDIENTE | Estado. Valores: PENDIENTE · DISPONIBLE · ATENDIDA · CANCELADA · EXPIRADA |
| `fecha_reserva` | datetime(6) | No |  | now() | Fecha de reserva |
| `fecha_expiracion` | datetime(6) | Sí |  |  | Fecha de expiración |
| `ejemplar_asignado_id` | bigint | Sí | FK → ejemplar |  | Ejemplar asignado |
| `libro_id` | bigint | No | FK → libro |  | Libro |
| `usuario_id` | bigint | No | FK → usuario |  | Usuario |

Restricciones:

- `ck_reserva_estado`: CHECK (estado IN ('PENDIENTE', 'DISPONIBLE', 'ATENDIDA', 'CANCELADA', 'EXPIRADA'))

Índices compuestos:

- `idx_reserva_libro_fecha`: (libro, fecha_reserva)

## `multa`

Modelo: `multas.Multa`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `prestamo_id` | bigint | No | FK → prestamo |  | Prestamo |
| `usuario_id` | bigint | No | FK → usuario |  | Usuario |
| `motivo` | varchar(10) | No |  |  | Motivo. Valores: RETRASO · DANIO · PERDIDA |
| `dias_retraso` | smallint unsigned | No |  | 0 | Dias retraso |
| `monto` | decimal(10,2) | No |  |  | Monto |
| `estado` | varchar(10) | No | Índice | Multa.Estado.PENDIENTE | Estado. Valores: PENDIENTE · PAGADA · CONDONADA |
| `fecha_generacion` | datetime(6) | No |  | now() | Fecha generacion |
| `justificacion_condonacion` | varchar(255) | Sí |  |  | Justificacion condonacion |
| `condonada_por_id` | bigint | Sí | FK → usuario |  | Condonada por |

Restricciones:

- `ck_multa_monto`: CHECK (monto > 0)
- `ck_multa_motivo`: CHECK (motivo IN ('RETRASO', 'DANIO', 'PERDIDA'))
- `ck_multa_estado`: CHECK (estado IN ('PENDIENTE', 'PAGADA', 'CONDONADA'))

## `pago`

Modelo: `multas.Pago`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `multa_id` | bigint | No | FK → multa |  | Multa |
| `monto` | decimal(10,2) | No |  |  | Monto |
| `metodo` | varchar(15) | No |  |  | Metodo. Valores: EFECTIVO · TARJETA · TRANSFERENCIA |
| `folio_recibo` | varchar(30) | No | UQ |  | Folio recibo |
| `fecha_pago` | datetime(6) | No |  | now() | Fecha pago |
| `registrado_por_id` | bigint | No | FK → usuario |  | Registrado por |

Restricciones:

- `ck_pago_monto`: CHECK (monto > 0)
- `ck_pago_metodo`: CHECK (metodo IN ('EFECTIVO', 'TARJETA', 'TRANSFERENCIA'))

## `notificacion`

Modelo: `notificaciones.Notificacion`

| Columna | Tipo | Nulo | Llave | Valor por defecto | Descripción |
|---|---|---|---|---|---|
| `id` | bigint auto_increment | No | PK |  | Identificador |
| `usuario_id` | bigint | No | FK → usuario |  | Usuario |
| `tipo` | varchar(20) | No |  |  | Tipo. Valores: VENCE_PRONTO · VENCIDO · RESERVA_DISPONIBLE · MULTA · GENERAL |
| `mensaje` | varchar(500) | No |  |  | Mensaje |
| `leida` | tinyint(1) | No |  | False | Leida |
| `fecha` | datetime(6) | No |  | now() | Fecha |

Restricciones:

- `ck_notificacion_tipo`: CHECK (tipo IN ('VENCE_PRONTO', 'VENCIDO', 'RESERVA_DISPONIBLE', 'MULTA', 'GENERAL'))

