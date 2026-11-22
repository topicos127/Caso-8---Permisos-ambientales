-- Sprint 9 — plan B, solo si la app NO pudo agregar la columna al arrancar.
-- (En los logs de Render saldria "AVISO: no se pudo preparar la base para los Sprints 8 y 9".)
-- Correr en Aiven sobre la base que usa la app (defaultdb), despues del respaldo.

-- HU-15: baja logica de consultores. 1 = activo, 0 = desactivado.
-- Los usuarios que ya existen quedan activos.
ALTER TABLE usuarios ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1;

-- Verificacion
SHOW COLUMNS FROM usuarios LIKE 'activo';
SELECT id, nombre, email, rol, activo FROM usuarios ORDER BY rol, nombre;
