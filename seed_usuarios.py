"""
Sistema de Permisos Ambientales - Seed completo (Sprint 5)
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

USUARIOS = [
    ("Consultor Uno", "consultor1@ejemplo.com", "clave123", "consultor"),
    ("Promotor Uno", "promotor1@ejemplo.com", "clave456", "promotor"),
    # Sprint 8: segundo consultor, para probar que cada consultor ve solo lo
    # suyo y el jefe ve todo. El jefe lo crea la app al arrancar (app.py).
    ("Consultor Dos", "consultor2@ejemplo.com", "Clave2026", "consultor"),
]

# codigo, proyecto, promotor, promotor_email, categoria, estado, fecha, email_consultor
EXPEDIENTES = [
    ("SP-A8-2026-001", "Planta Solar Azuero",  "Energía Verde S.A.",     "promotor1@ejemplo.com", "II",  "pendiente",        "2026-09-10", "consultor1@ejemplo.com"),
    ("SP-A8-2026-002", "Hotel Costero Bocas",  "Inversiones del Caribe", "promotor1@ejemplo.com", "III", "pendiente",        "2026-09-05", "consultor1@ejemplo.com"),
    ("SP-A8-2026-003", "Reforestación Darién", "ONG Ambiental",          None,                    "I",   "aprobado",         "2026-08-28", "consultor1@ejemplo.com"),
]

DOCS_POR_CAT = {
    "I":   ["Línea Base", "Plan de Manejo", "Anexos Legales"],
    "II":  ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía"],
    "III": ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía", "Evidencia Foro Público"],
}

ALERTAS = [
    ("SP-A8-2026-001", "Paz y salvo del Municipio vence en 12 días", 12),
    ("SP-A8-2026-001", "Certificado de registro vence en 28 días", 28),
]


def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # Usuarios
            for nombre, email, password, rol in USUARIOS:
                cur.execute(
                    """INSERT INTO usuarios (nombre, email, password_hash, rol)
                       VALUES (%s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash)""",
                    (nombre, email, generate_password_hash(password), rol),
                )

            # Expedientes + documentos
            for codigo, proyecto, promotor, prom_email, categoria, estado, fecha, email_consultor in EXPEDIENTES:
                cur.execute("SELECT id FROM usuarios WHERE email=%s", (email_consultor,))
                row = cur.fetchone()
                uid = row[0] if row else None

                cur.execute(
                    """INSERT INTO expedientes
                       (codigo, proyecto, promotor, promotor_email, categoria, estado, fecha_ingreso, usuario_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                         proyecto=VALUES(proyecto), promotor=VALUES(promotor),
                         promotor_email=VALUES(promotor_email),
                         categoria=VALUES(categoria), estado=VALUES(estado),
                         fecha_ingreso=VALUES(fecha_ingreso), usuario_id=VALUES(usuario_id)""",
                    (codigo, proyecto, promotor, prom_email, categoria, estado, fecha, uid),
                )

                cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
                exp_id = cur.fetchone()[0]

                cur.execute("DELETE FROM documentos WHERE expediente_id=%s", (exp_id,))
                docs = DOCS_POR_CAT[categoria]
                for i, carpeta in enumerate(docs):
                    estado_doc = "pendiente" if i == len(docs) - 1 else "recibido"
                    cur.execute(
                        "INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, %s)",
                        (exp_id, carpeta, estado_doc),
                    )

            # Alertas
            cur.execute("DELETE FROM alertas")
            for codigo, descripcion, dias in ALERTAS:
                cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "INSERT INTO alertas (expediente_id, descripcion, dias_restantes) VALUES (%s, %s, %s)",
                        (row[0], descripcion, dias),
                    )

        conn.commit()
        print("Seed completo: usuarios, expedientes, documentos y alertas.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()