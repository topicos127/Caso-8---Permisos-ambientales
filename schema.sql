-- Sistema de Permisos Ambientales — Esquema (plataforma multiempresa)
CREATE DATABASE IF NOT EXISTS permisos_ambientales;
USE permisos_ambientales;

-- Cada consultora es una empresa: sus usuarios y expedientes no se mezclan con los de otra.
CREATE TABLE IF NOT EXISTS organizaciones (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(150) NOT NULL,
    color VARCHAR(7) NOT NULL DEFAULT '#17805a',
    logo_ruta VARCHAR(500) NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Mi consultora: datos de la empresa (salen en el PDF y en la consulta publica)
    razon_social VARCHAR(200) NULL,
    ruc VARCHAR(40) NULL,
    direccion VARCHAR(300) NULL,
    telefono VARCHAR(40) NULL,
    email_contacto VARCHAR(255) NULL,
    pie_documento VARCHAR(300) NULL,
    -- Politica de seguridad de la empresa
    exigir_2fa BOOLEAN NOT NULL DEFAULT FALSE,
    sesion_minutos INT NULL,
    aviso_defecto INT NULL,
    -- Titular de la cuenta (unico que invita a otros directores y cambia roles)
    titular_id INT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_organizacion_nombre (nombre)
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(50) NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Sprint 9: contrasena temporal del promotor; debe cambiarla al entrar.
    -- La app la agrega sola a las bases anteriores al arrancar.
    debe_cambiar_clave BOOLEAN NOT NULL DEFAULT FALSE,
    -- Sprint 9: baja logica de consultores (el jefe los desactiva, no se borran).
    -- La app la agrega sola a las bases anteriores al arrancar.
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    -- Sprint 10 (HU-05): con cuantos dias de anticipacion se avisa el vencimiento (15, 30 o 45).
    aviso_vencimiento_dias INT NOT NULL DEFAULT 30,
    -- Empresa a la que pertenece (NULL solo para el administrador de la plataforma).
    organizacion_id INT NULL,
    -- Verificacion en dos pasos (TOTP). El secreto se guarda cifrado.
    totp_secreto VARCHAR(255) NULL,
    totp_activo BOOLEAN NOT NULL DEFAULT FALSE,
    totp_ultimo_paso BIGINT NOT NULL DEFAULT 0,
    -- Sube con cada cambio de contrasena o "cerrar sesiones": invalida las sesiones abiertas.
    sesion_version INT NOT NULL DEFAULT 0,
    terminos_aceptados_en DATETIME NULL,
    -- Recorrido de bienvenida: se muestra una sola vez por cuenta.
    tour_visto_en DATETIME NULL,
    CONSTRAINT fk_usuarios_organizacion FOREIGN KEY (organizacion_id) REFERENCES organizaciones (id)
);

CREATE TABLE IF NOT EXISTS expedientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    proyecto VARCHAR(150) NOT NULL,
    promotor VARCHAR(150) NOT NULL,
    promotor_email VARCHAR(255) NULL,
    categoria ENUM('I','II','III') NOT NULL,
    estado ENUM('pendiente','aprobado_interno','evaluacion','aprobado','rechazado') NOT NULL DEFAULT 'pendiente',
    fecha_ingreso DATE NOT NULL,
    usuario_id INT NOT NULL,
    acceso_publico BOOLEAN NOT NULL DEFAULT TRUE,
    -- Sprint 10 (HU-08): desde esta fecha corre el plazo de MiAmbiente en dias habiles.
    fecha_sometimiento DATE NULL,
    organizacion_id INT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_expedientes_organizacion FOREIGN KEY (organizacion_id) REFERENCES organizaciones (id)
);

CREATE TABLE IF NOT EXISTS documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    carpeta VARCHAR(100) NOT NULL,
    estado ENUM('recibido','pendiente') NOT NULL DEFAULT 'pendiente',
    archivo_nombre VARCHAR(255) NULL,
    archivo_ruta VARCHAR(500) NULL,
    archivo_tamano INT NULL,
    fecha_subida TIMESTAMP NULL,
    -- Sprint 10 (HU-05): vencimiento real del documento; si es NULL, vence al ano de subido.
    fecha_vencimiento DATE NULL,
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id)
);

CREATE TABLE IF NOT EXISTS aprobaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    motivo TEXT NOT NULL,
    aprobado_por INT NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id),
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS alertas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    descripcion VARCHAR(200) NOT NULL,
    dias_restantes INT NOT NULL,
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id)
);

-- Sprint 8 (HU-14): historial del expediente. La app tambien la crea al
-- arrancar si no existe, para la base de Aiven.
CREATE TABLE IF NOT EXISTS historial_expediente (
    id INT NOT NULL AUTO_INCREMENT,
    expediente_id INT NOT NULL,
    usuario_id INT NOT NULL,
    accion VARCHAR(50) NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);

-- Sprint 9 (HU-01): cada subida es una version nueva con codigo de trazabilidad
-- y huella SHA-256. Las versiones no se modifican ni se eliminan.
CREATE TABLE IF NOT EXISTS documento_versiones (
    id INT NOT NULL AUTO_INCREMENT,
    documento_id INT NOT NULL,
    version INT NOT NULL,
    codigo_trazabilidad VARCHAR(80) NOT NULL,
    archivo_nombre VARCHAR(255) NOT NULL,
    archivo_ruta VARCHAR(500) NULL,
    archivo_tamano INT NULL,
    sha256 CHAR(64) NULL,
    subido_por INT NULL,
    fecha_subida DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_version_codigo (codigo_trazabilidad),
    UNIQUE KEY uq_version_documento (documento_id, version),
    FOREIGN KEY (documento_id) REFERENCES documentos (id),
    FOREIGN KEY (subido_por) REFERENCES usuarios (id)
);

-- Sprint 10: resolucion de MiAmbiente (aprobado o rechazado, con numero y fecha).
CREATE TABLE IF NOT EXISTS resoluciones (
    id INT NOT NULL AUTO_INCREMENT,
    expediente_id INT NOT NULL,
    resultado ENUM('aprobado','rechazado') NOT NULL,
    numero VARCHAR(60) NOT NULL,
    fecha_resolucion DATE NOT NULL,
    registrado_por INT NOT NULL,
    fecha_registro DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
    FOREIGN KEY (registrado_por) REFERENCES usuarios (id)
);

-- Sprint 10: observaciones con las que el jefe devuelve un expediente al consultor.
CREATE TABLE IF NOT EXISTS observaciones (
    id INT NOT NULL AUTO_INCREMENT,
    expediente_id INT NOT NULL,
    texto TEXT NOT NULL,
    autor_id INT NOT NULL,
    fecha DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
    FOREIGN KEY (autor_id) REFERENCES usuarios (id)
);

-- Invitaciones: la unica forma de crear una cuenta nueva. Solo se guarda el SHA-256 del enlace.
CREATE TABLE IF NOT EXISTS invitaciones (
    id INT NOT NULL AUTO_INCREMENT,
    token_hash CHAR(64) NOT NULL,
    organizacion_id INT NOT NULL,
    rol VARCHAR(20) NOT NULL,
    email VARCHAR(255) NULL,
    creada_por INT NOT NULL,
    fecha_creacion DATETIME NOT NULL,
    expira DATETIME NOT NULL,
    usada_en DATETIME NULL,
    usada_por INT NULL,
    revocada BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    UNIQUE KEY uq_invitacion_token (token_hash),
    FOREIGN KEY (organizacion_id) REFERENCES organizaciones (id),
    FOREIGN KEY (creada_por) REFERENCES usuarios (id)
);

-- Codigos de recuperacion (un solo uso): sirven para entrar sin el telefono o fijar una contrasena nueva.
CREATE TABLE IF NOT EXISTS codigos_recuperacion (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    codigo_hash CHAR(64) NOT NULL,
    fecha_creacion DATETIME NOT NULL,
    usado_en DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_codigo_recuperacion (codigo_hash),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);

-- Comentarios internos de cada expediente (el promotor no los ve).
CREATE TABLE IF NOT EXISTS comentarios (
    id INT NOT NULL AUTO_INCREMENT,
    expediente_id INT NOT NULL,
    usuario_id INT NOT NULL,
    texto TEXT NOT NULL,
    fecha DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_comentarios_expediente (expediente_id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);

-- Filtros guardados de cada usuario.
CREATE TABLE IF NOT EXISTS vistas_guardadas (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    nombre VARCHAR(60) NOT NULL,
    filtros VARCHAR(1000) NOT NULL,
    fecha DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);

-- Registro de accesos y cambios de cada empresa (sin llaves foraneas: sobrevive a las bajas de cuentas).
CREATE TABLE IF NOT EXISTS eventos_cuenta (
    id BIGINT NOT NULL AUTO_INCREMENT,
    organizacion_id INT NULL,
    usuario_id INT NULL,
    email VARCHAR(255) NULL,
    tipo VARCHAR(40) NOT NULL,
    detalle VARCHAR(300) NULL,
    ip VARCHAR(64) NULL,
    fecha DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_eventos_org_fecha (organizacion_id, fecha),
    KEY ix_eventos_usuario (usuario_id, tipo, fecha)
);
