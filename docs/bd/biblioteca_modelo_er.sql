-- =====================================================================
--  Proyecto Final · Ingeniería de Software
--  Sistema de Gestión de Biblioteca Escolar
--  Modelo entidad-relación (MySQL 8.x, InnoDB, utf8mb4)
--
--  Cómo abrirlo como diagrama en MySQL Workbench:
--    1. File > New Model
--    2. File > Import > Reverse Engineer MySQL Create Script...
--    3. Seleccionar este archivo y marcar
--       "Place imported objects on a diagram".
--    4. Execute > Next > Finish. Se genera el diagrama EER.
--    5. Guardar como biblioteca.mwb (File > Save Model As).
--
--  También puede ejecutarse directamente en el servidor MySQL
--  (File > Open SQL Script > ejecutar) para crear la base de datos.
--
--  Nota: en el proyecto Django las tablas se crean con las migraciones;
--  este script es la referencia del diseño y debe coincidir con ellas.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS biblioteca
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE biblioteca;

-- ---------------------------------------------------------------------
-- Catálogos de cuentas
-- ---------------------------------------------------------------------

CREATE TABLE carrera (
  id      BIGINT       NOT NULL AUTO_INCREMENT,
  clave   VARCHAR(10)  NOT NULL,
  nombre  VARCHAR(120) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_carrera_clave (clave)
) ENGINE=InnoDB COMMENT='Carreras de la escuela';

CREATE TABLE departamento (
  id      BIGINT       NOT NULL AUTO_INCREMENT,
  nombre  VARCHAR(120) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_departamento_nombre (nombre)
) ENGINE=InnoDB COMMENT='Departamentos académicos';

-- ---------------------------------------------------------------------
-- Usuarios (modelo personalizado de Django, hereda de AbstractUser)
-- ---------------------------------------------------------------------

CREATE TABLE usuario (
  id              BIGINT       NOT NULL AUTO_INCREMENT,
  password        VARCHAR(128) NOT NULL,
  last_login      DATETIME(6)  NULL,
  is_superuser    TINYINT(1)   NOT NULL DEFAULT 0,
  username        VARCHAR(150) NOT NULL,
  first_name      VARCHAR(150) NOT NULL,
  last_name       VARCHAR(150) NOT NULL,
  email           VARCHAR(254) NOT NULL,
  is_staff        TINYINT(1)   NOT NULL DEFAULT 0,
  is_active       TINYINT(1)   NOT NULL DEFAULT 1,
  date_joined     DATETIME(6)  NOT NULL,
  tipo_usuario    VARCHAR(15)  NOT NULL,
  telefono        VARCHAR(20)  NULL,
  bloqueado       TINYINT(1)   NOT NULL DEFAULT 0,
  motivo_bloqueo  VARCHAR(255) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_usuario_username (username),
  UNIQUE KEY uq_usuario_email (email),
  KEY idx_usuario_tipo (tipo_usuario),
  CONSTRAINT ck_usuario_tipo
    CHECK (tipo_usuario IN ('ESTUDIANTE','PROFESOR','BIBLIOTECARIO'))
) ENGINE=InnoDB COMMENT='Usuarios del sistema: estudiantes, profesores y bibliotecarios';

CREATE TABLE estudiante (
  usuario_id  BIGINT           NOT NULL,
  matricula   VARCHAR(20)      NOT NULL,
  carrera_id  BIGINT           NOT NULL,
  semestre    TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (usuario_id),
  UNIQUE KEY uq_estudiante_matricula (matricula),
  KEY idx_estudiante_carrera (carrera_id),
  CONSTRAINT fk_estudiante_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario (id) ON DELETE CASCADE,
  CONSTRAINT fk_estudiante_carrera FOREIGN KEY (carrera_id)
    REFERENCES carrera (id) ON DELETE RESTRICT,
  CONSTRAINT ck_estudiante_semestre CHECK (semestre BETWEEN 1 AND 12)
) ENGINE=InnoDB COMMENT='Perfil de estudiante (1 a 1 con usuario)';

CREATE TABLE profesor (
  usuario_id       BIGINT      NOT NULL,
  num_empleado     VARCHAR(20) NOT NULL,
  departamento_id  BIGINT      NOT NULL,
  PRIMARY KEY (usuario_id),
  UNIQUE KEY uq_profesor_num_empleado (num_empleado),
  KEY idx_profesor_departamento (departamento_id),
  CONSTRAINT fk_profesor_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario (id) ON DELETE CASCADE,
  CONSTRAINT fk_profesor_departamento FOREIGN KEY (departamento_id)
    REFERENCES departamento (id) ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Perfil de profesor (1 a 1 con usuario)';

-- ---------------------------------------------------------------------
-- Políticas de préstamo (RN-01 a RN-06)
-- ---------------------------------------------------------------------

CREATE TABLE politica_prestamo (
  id                  BIGINT            NOT NULL AUTO_INCREMENT,
  tipo_usuario        VARCHAR(15)       NOT NULL,
  dias_prestamo       SMALLINT UNSIGNED NOT NULL,
  max_libros          SMALLINT UNSIGNED NOT NULL,
  max_renovaciones    SMALLINT UNSIGNED NOT NULL,
  multa_por_dia       DECIMAL(8,2)      NOT NULL,
  multa_maxima        DECIMAL(8,2)      NOT NULL,
  horas_para_recoger  SMALLINT UNSIGNED NOT NULL,
  actualizado_en      DATETIME(6)       NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_politica_tipo (tipo_usuario),
  CONSTRAINT ck_politica_tipo CHECK (tipo_usuario IN ('ESTUDIANTE','PROFESOR')),
  CONSTRAINT ck_politica_multas CHECK (multa_por_dia >= 0 AND multa_maxima >= 0)
) ENGINE=InnoDB COMMENT='Parámetros de préstamo por tipo de usuario';

-- ---------------------------------------------------------------------
-- Catálogo bibliográfico
-- ---------------------------------------------------------------------

CREATE TABLE autor (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  nombre        VARCHAR(100) NOT NULL,
  apellidos     VARCHAR(150) NOT NULL,
  nacionalidad  VARCHAR(60)  NULL,
  PRIMARY KEY (id),
  KEY idx_autor_apellidos (apellidos)
) ENGINE=InnoDB;

CREATE TABLE editorial (
  id      BIGINT       NOT NULL AUTO_INCREMENT,
  nombre  VARCHAR(150) NOT NULL,
  pais    VARCHAR(60)  NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_editorial_nombre (nombre)
) ENGINE=InnoDB;

CREATE TABLE categoria (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  nombre       VARCHAR(100) NOT NULL,
  descripcion  VARCHAR(255) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_categoria_nombre (nombre)
) ENGINE=InnoDB;

CREATE TABLE libro (
  id                BIGINT            NOT NULL AUTO_INCREMENT,
  isbn              VARCHAR(13)       NOT NULL,
  titulo            VARCHAR(255)      NOT NULL,
  subtitulo         VARCHAR(255)      NULL,
  editorial_id      BIGINT            NOT NULL,
  categoria_id      BIGINT            NOT NULL,
  anio_publicacion  SMALLINT UNSIGNED NULL,
  edicion           VARCHAR(30)       NULL,
  idioma            VARCHAR(30)       NOT NULL DEFAULT 'Español',
  num_paginas       SMALLINT UNSIGNED NULL,
  descripcion       TEXT              NULL,
  portada           VARCHAR(255)      NULL,
  costo_reposicion  DECIMAL(10,2)     NOT NULL DEFAULT 0.00,
  activo            TINYINT(1)        NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_libro_isbn (isbn),
  KEY idx_libro_titulo (titulo),
  KEY idx_libro_editorial (editorial_id),
  KEY idx_libro_categoria (categoria_id),
  CONSTRAINT fk_libro_editorial FOREIGN KEY (editorial_id)
    REFERENCES editorial (id) ON DELETE RESTRICT,
  CONSTRAINT fk_libro_categoria FOREIGN KEY (categoria_id)
    REFERENCES categoria (id) ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Título u obra; los objetos físicos están en ejemplar';

CREATE TABLE libro_autor (
  id        BIGINT           NOT NULL AUTO_INCREMENT,
  libro_id  BIGINT           NOT NULL,
  autor_id  BIGINT           NOT NULL,
  orden     TINYINT UNSIGNED NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_libro_autor (libro_id, autor_id),
  KEY idx_libro_autor_autor (autor_id),
  CONSTRAINT fk_libro_autor_libro FOREIGN KEY (libro_id)
    REFERENCES libro (id) ON DELETE CASCADE,
  CONSTRAINT fk_libro_autor_autor FOREIGN KEY (autor_id)
    REFERENCES autor (id) ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Relación muchos a muchos entre libro y autor';

CREATE TABLE ejemplar (
  id                 BIGINT       NOT NULL AUTO_INCREMENT,
  libro_id           BIGINT       NOT NULL,
  codigo_inventario  VARCHAR(30)  NOT NULL,
  ubicacion          VARCHAR(50)  NULL,
  estado             VARCHAR(15)  NOT NULL DEFAULT 'DISPONIBLE',
  fecha_adquisicion  DATE         NULL,
  observaciones      VARCHAR(255) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_ejemplar_codigo (codigo_inventario),
  KEY idx_ejemplar_libro (libro_id),
  KEY idx_ejemplar_estado (estado),
  CONSTRAINT fk_ejemplar_libro FOREIGN KEY (libro_id)
    REFERENCES libro (id) ON DELETE RESTRICT,
  CONSTRAINT ck_ejemplar_estado CHECK (estado IN
    ('DISPONIBLE','RESERVADO','PRESTADO','EN_REPARACION','PERDIDO','BAJA'))
) ENGINE=InnoDB COMMENT='Copia física de un libro';

-- ---------------------------------------------------------------------
-- Préstamos y reservas
-- ---------------------------------------------------------------------

CREATE TABLE prestamo (
  id                    BIGINT            NOT NULL AUTO_INCREMENT,
  usuario_id            BIGINT            NOT NULL,
  ejemplar_id           BIGINT            NOT NULL,
  estado                VARCHAR(12)       NOT NULL DEFAULT 'SOLICITADO',
  fecha_solicitud       DATETIME(6)       NOT NULL,
  fecha_limite_recoger  DATETIME(6)       NULL,
  fecha_prestamo        DATETIME(6)       NULL,
  fecha_vencimiento     DATE              NULL,
  fecha_devolucion      DATETIME(6)       NULL,
  num_renovaciones      SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  entregado_por_id      BIGINT            NULL,
  recibido_por_id       BIGINT            NULL,
  observaciones         VARCHAR(255)      NULL,
  PRIMARY KEY (id),
  KEY idx_prestamo_usuario (usuario_id),
  KEY idx_prestamo_ejemplar (ejemplar_id),
  KEY idx_prestamo_estado (estado),
  KEY idx_prestamo_vencimiento (fecha_vencimiento),
  KEY idx_prestamo_entregado_por (entregado_por_id),
  KEY idx_prestamo_recibido_por (recibido_por_id),
  CONSTRAINT fk_prestamo_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT fk_prestamo_ejemplar FOREIGN KEY (ejemplar_id)
    REFERENCES ejemplar (id) ON DELETE RESTRICT,
  CONSTRAINT fk_prestamo_entregado_por FOREIGN KEY (entregado_por_id)
    REFERENCES usuario (id) ON DELETE SET NULL,
  CONSTRAINT fk_prestamo_recibido_por FOREIGN KEY (recibido_por_id)
    REFERENCES usuario (id) ON DELETE SET NULL,
  CONSTRAINT ck_prestamo_estado CHECK (estado IN
    ('SOLICITADO','ACTIVO','VENCIDO','DEVUELTO','CANCELADO','EXPIRADO','PERDIDO'))
) ENGINE=InnoDB COMMENT='Préstamo de un ejemplar a un usuario lector';

CREATE TABLE reserva (
  id                    BIGINT      NOT NULL AUTO_INCREMENT,
  usuario_id            BIGINT      NOT NULL,
  libro_id              BIGINT      NOT NULL,
  ejemplar_asignado_id  BIGINT      NULL,
  estado                VARCHAR(12) NOT NULL DEFAULT 'PENDIENTE',
  fecha_reserva         DATETIME(6) NOT NULL,
  fecha_expiracion      DATETIME(6) NULL,
  PRIMARY KEY (id),
  KEY idx_reserva_usuario (usuario_id),
  KEY idx_reserva_libro_fecha (libro_id, fecha_reserva),
  KEY idx_reserva_ejemplar (ejemplar_asignado_id),
  KEY idx_reserva_estado (estado),
  CONSTRAINT fk_reserva_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_libro FOREIGN KEY (libro_id)
    REFERENCES libro (id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_ejemplar FOREIGN KEY (ejemplar_asignado_id)
    REFERENCES ejemplar (id) ON DELETE SET NULL,
  CONSTRAINT ck_reserva_estado CHECK (estado IN
    ('PENDIENTE','DISPONIBLE','ATENDIDA','CANCELADA','EXPIRADA'))
) ENGINE=InnoDB COMMENT='Reserva de un título sin ejemplares disponibles (cola FIFO)';

-- ---------------------------------------------------------------------
-- Multas y pagos
-- ---------------------------------------------------------------------

CREATE TABLE multa (
  id                         BIGINT            NOT NULL AUTO_INCREMENT,
  prestamo_id                BIGINT            NOT NULL,
  usuario_id                 BIGINT            NOT NULL,
  motivo                     VARCHAR(10)       NOT NULL,
  dias_retraso               SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  monto                      DECIMAL(10,2)     NOT NULL,
  estado                     VARCHAR(10)       NOT NULL DEFAULT 'PENDIENTE',
  fecha_generacion           DATETIME(6)       NOT NULL,
  justificacion_condonacion  VARCHAR(255)      NULL,
  condonada_por_id           BIGINT            NULL,
  PRIMARY KEY (id),
  KEY idx_multa_prestamo (prestamo_id),
  KEY idx_multa_usuario_estado (usuario_id, estado),
  KEY idx_multa_condonada_por (condonada_por_id),
  CONSTRAINT fk_multa_prestamo FOREIGN KEY (prestamo_id)
    REFERENCES prestamo (id) ON DELETE RESTRICT,
  CONSTRAINT fk_multa_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT fk_multa_condonada_por FOREIGN KEY (condonada_por_id)
    REFERENCES usuario (id) ON DELETE SET NULL,
  CONSTRAINT ck_multa_motivo CHECK (motivo IN ('RETRASO','DANIO','PERDIDA')),
  CONSTRAINT ck_multa_estado CHECK (estado IN ('PENDIENTE','PAGADA','CONDONADA')),
  CONSTRAINT ck_multa_monto CHECK (monto > 0)
) ENGINE=InnoDB COMMENT='Multa por retraso, daño o pérdida de un ejemplar';

CREATE TABLE pago (
  id                 BIGINT        NOT NULL AUTO_INCREMENT,
  multa_id           BIGINT        NOT NULL,
  monto              DECIMAL(10,2) NOT NULL,
  metodo             VARCHAR(15)   NOT NULL,
  folio_recibo       VARCHAR(30)   NOT NULL,
  fecha_pago         DATETIME(6)   NOT NULL,
  registrado_por_id  BIGINT        NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_pago_folio (folio_recibo),
  KEY idx_pago_multa (multa_id),
  KEY idx_pago_registrado_por (registrado_por_id),
  CONSTRAINT fk_pago_multa FOREIGN KEY (multa_id)
    REFERENCES multa (id) ON DELETE RESTRICT,
  CONSTRAINT fk_pago_registrado_por FOREIGN KEY (registrado_por_id)
    REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT ck_pago_metodo CHECK (metodo IN ('EFECTIVO','TARJETA','TRANSFERENCIA')),
  CONSTRAINT ck_pago_monto CHECK (monto > 0)
) ENGINE=InnoDB COMMENT='Pago (total o parcial) de una multa';

-- ---------------------------------------------------------------------
-- Notificaciones y sugerencias
-- ---------------------------------------------------------------------

CREATE TABLE notificacion (
  id          BIGINT       NOT NULL AUTO_INCREMENT,
  usuario_id  BIGINT       NOT NULL,
  tipo        VARCHAR(20)  NOT NULL,
  mensaje     VARCHAR(500) NOT NULL,
  leida       TINYINT(1)   NOT NULL DEFAULT 0,
  fecha       DATETIME(6)  NOT NULL,
  PRIMARY KEY (id),
  KEY idx_notificacion_usuario_leida (usuario_id, leida),
  CONSTRAINT fk_notificacion_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario (id) ON DELETE CASCADE,
  CONSTRAINT ck_notificacion_tipo CHECK (tipo IN
    ('VENCE_PRONTO','VENCIDO','RESERVA_DISPONIBLE','MULTA','GENERAL'))
) ENGINE=InnoDB;

CREATE TABLE sugerencia_adquisicion (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  profesor_id    BIGINT       NOT NULL,
  titulo         VARCHAR(255) NOT NULL,
  autores        VARCHAR(255) NOT NULL,
  isbn           VARCHAR(13)  NULL,
  justificacion  TEXT         NOT NULL,
  estado         VARCHAR(10)  NOT NULL DEFAULT 'PENDIENTE',
  respuesta      VARCHAR(255) NULL,
  fecha          DATETIME(6)  NOT NULL,
  PRIMARY KEY (id),
  KEY idx_sugerencia_profesor (profesor_id),
  CONSTRAINT fk_sugerencia_profesor FOREIGN KEY (profesor_id)
    REFERENCES profesor (usuario_id) ON DELETE CASCADE,
  CONSTRAINT ck_sugerencia_estado CHECK (estado IN ('PENDIENTE','APROBADA','RECHAZADA'))
) ENGINE=InnoDB COMMENT='Sugerencias de compra de libros hechas por profesores';

-- ---------------------------------------------------------------------
-- Datos iniciales: políticas de préstamo predeterminadas
-- ---------------------------------------------------------------------

INSERT INTO politica_prestamo
  (tipo_usuario, dias_prestamo, max_libros, max_renovaciones,
   multa_por_dia, multa_maxima, horas_para_recoger, actualizado_en)
VALUES
  ('ESTUDIANTE',  7,  3, 1, 10.00, 300.00, 48, NOW(6)),
  ('PROFESOR',   30, 10, 2, 10.00, 300.00, 48, NOW(6));
