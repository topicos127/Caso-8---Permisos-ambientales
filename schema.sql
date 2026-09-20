-- Sistema de Permisos Ambientales - Esquema de usuarios (HU-11)
-- Sprint 3 - Caso 8

CREATE DATABASE IF NOT EXISTS permisos_ambientales
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE permisos_ambientales;

CREATE TABLE IF NOT EXISTS usuarios (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    nombre         VARCHAR(150) NOT NULL,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    rol            VARCHAR(20)  NOT NULL,
    creado_en      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
