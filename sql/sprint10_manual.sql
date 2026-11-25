-- Sprint 10 — plan B, solo si la app NO pudo preparar la base al arrancar.
-- (En los logs saldria "AVISO: no se pudo agregar <tabla>.<columna>".)
-- Correr en Aiven sobre la base que usa la app (defaultdb), despues del respaldo.
-- Si una columna ya existe, MySQL responde "Duplicate column name": se salta esa linea.

-- HU-08: fecha de sometimiento; desde ella corre el plazo de MiAmbiente en dias habiles.
ALTER TABLE expedientes ADD COLUMN fecha_sometimiento DATE NULL;

-- HU-05: vencimiento real de cada documento y aviso que elige cada usuario.
ALTER TABLE documentos ADD COLUMN fecha_vencimiento DATE NULL;
ALTER TABLE usuarios ADD COLUMN aviso_vencimiento_dias INT NOT NULL DEFAULT 30;

-- Resolucion de MiAmbiente y observaciones del jefe.
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

-- Verificacion
SHOW COLUMNS FROM expedientes WHERE Field = 'fecha_sometimiento';
SHOW COLUMNS FROM documentos WHERE Field = 'fecha_vencimiento';
SHOW COLUMNS FROM usuarios WHERE Field = 'aviso_vencimiento_dias';
SHOW TABLES LIKE 'resoluciones';
SHOW TABLES LIKE 'observaciones';
