-- Sprint 9 — plan B, solo si la app NO pudo agregar las columnas al arrancar.
-- (En los logs saldria "AVISO: no se pudo agregar usuarios.<columna>".)
-- Correr en Aiven sobre la base que usa la app (defaultdb), despues del respaldo.
-- Si una columna ya existe, MySQL responde "Duplicate column name": se salta esa linea.

-- Contrasena temporal del promotor y del consultor dado de alta por el jefe.
ALTER TABLE usuarios ADD COLUMN debe_cambiar_clave BOOLEAN NOT NULL DEFAULT FALSE;

-- Equipo de consultores: baja logica. TRUE = activo; los usuarios que ya existen quedan activos.
ALTER TABLE usuarios ADD COLUMN activo BOOLEAN NOT NULL DEFAULT TRUE;

-- Verificacion
SHOW COLUMNS FROM usuarios WHERE Field IN ('debe_cambiar_clave', 'activo');
SELECT id, nombre, email, rol, activo FROM usuarios ORDER BY rol, nombre;
