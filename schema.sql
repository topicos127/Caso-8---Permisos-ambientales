-- Sistema de Permisos Ambientales — Esquema Sprint 3
CREATE DATABASE IF NOT EXISTS permisos_ambientales;
USE permisos_ambientales;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(50) NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expedientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    proyecto VARCHAR(255) NOT NULL,
    promotor VARCHAR(255) NOT NULL,
    categoria CHAR(3) NOT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'evaluacion',
    fecha_ingreso DATE NOT NULL,
    usuario_id INT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    carpeta VARCHAR(80) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alertas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    descripcion VARCHAR(255) NOT NULL,
    dias_restantes INT NOT NULL,
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aprobaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    motivo TEXT,
    aprobado_por INT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE,
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    carpeta VARCHAR(80) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    nombre_archivo VARCHAR(255) NULL,
    contenido LONGBLOB NULL,
    fecha_subida TIMESTAMP NULL,
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS expedientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    proyecto VARCHAR(150) NOT NULL,
    promotor VARCHAR(150) NOT NULL,
    categoria ENUM('I', 'II', 'III') NOT NULL,
    estado ENUM('evaluacion', 'pendiente', 'aprobado', 'rechazado') NOT NULL DEFAULT 'evaluacion',
    creado_por INT NOT NULL,
    fecha_ingreso DATE NOT NULL,
    aprobacion_motivo TEXT NULL,
    aprobacion_fecha DATETIME NULL,
    aprobacion_usuario_id INT NULL,
    FOREIGN KEY (creado_por) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expediente_id INT NOT NULL,
    carpeta VARCHAR(100) NOT NULL,
    estado ENUM('recibido', 'pendiente') NOT NULL DEFAULT 'pendiente',
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id)
);