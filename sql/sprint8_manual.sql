-- Sprint 8 — plan B, solo si la app NO pudo crear la tabla al arrancar.
-- (En los logs del despliegue saldria "AVISO: no se pudo preparar la base para el Sprint 8".)
-- Correr en Aiven sobre la base que usa la app (defaultdb).

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

-- Usuario jefe: la contrasena va con hash. Generar el hash con:
--   python -c "from werkzeug.security import generate_password_hash as g; print(g('Jefe2026*'))"
-- y pegarlo abajo en lugar de <HASH>:
-- INSERT INTO usuarios (nombre, email, password_hash, rol)
-- VALUES ('Jefa de la Consultora', 'jefe1@ejemplo.com', '<HASH>', 'jefe');

-- Verificacion
SHOW TABLES LIKE 'historial_expediente';
SELECT id, nombre, email, rol FROM usuarios WHERE rol = 'jefe';
