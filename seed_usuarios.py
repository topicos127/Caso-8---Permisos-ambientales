"""
Sistema de Permisos Ambientales - Seed de usuarios (HU-11)
Sprint 3 - Caso 8

Inserta los usuarios de prueba con la contrasena ya convertida a hash.
Ejecutar una sola vez, despues de crear la base de datos con schema.sql.
"""

import os
import pymysql
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "permisos123"),
    "database": os.environ.get("DB_NAME", "permisos_ambientales"),
}

# (nombre, email, contrasena_en_claro, rol)
# La contrasena en claro solo existe aqui, para generar el hash una vez.
USUARIOS_PRUEBA = [
    ("Consultor Uno", "consultor1@ejemplo.com", "clave123", "consultor"),
    ("Promotor Uno", "promotor1@ejemplo.com", "clave456", "promotor"),
]


def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            for nombre, email, password, rol in USUARIOS_PRUEBA:
                password_hash = generate_password_hash(password)
                cursor.execute(
                    """
                    INSERT INTO usuarios (nombre, email, password_hash, rol)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)
                    """,
                    (nombre, email, password_hash, rol),
                )
        conn.commit()
        print("Usuarios de prueba insertados/actualizados correctamente.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
