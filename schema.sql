-- Sistema de Permisos Ambientales — Esquema Sprint 8
CREATE DATABASE IF NOT EXISTS permisos_ambientales;
USE permisos_ambientales;

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
    activo BOOLEAN NOT NULL DEFAULT TRUE
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
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
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
