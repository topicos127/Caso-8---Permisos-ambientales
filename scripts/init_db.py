"""Prepara la base de datos antes de arrancar la app (Railway: Pre-Deploy Command).

- Aplica schema.sql sobre la base configurada en DB_NAME. Las sentencias
  CREATE DATABASE y USE se saltan: en la nube la base ya existe y puede tener
  otro nombre (en Aiven, por ejemplo, "defaultdb").
- Es idempotente: todas las tablas usan CREATE TABLE IF NOT EXISTS.
- Con SEED_DEMO=true corre ademas seed_usuarios.py (usuarios y expedientes de
  prueba). OJO: el seed reinicia los documentos de los expedientes de ejemplo,
  asi que conviene activarlo una sola vez y luego quitar la variable.

Uso:  python scripts/init_db.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import pymysql  # noqa: E402

from permisos.config import DB_CONFIG  # noqa: E402  (misma conexion y SSL que la app)


def sentencias(sql):
    """Separa schema.sql en sentencias, sin comentarios, CREATE DATABASE ni USE."""
    limpio = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    for s in limpio.split(";"):
        s = s.strip()
        if not s:
            continue
        cabeza = s.split(None, 2)
        if cabeza[0].upper() == "USE" or (cabeza[0].upper() == "CREATE" and cabeza[1].upper() == "DATABASE"):
            continue
        yield s


def aplicar_schema():
    with open(os.path.join(RAIZ, "schema.sql"), encoding="utf-8") as f:
        lista = list(sentencias(f.read()))
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            for s in lista:
                cur.execute(s)
        conn.commit()
    finally:
        conn.close()
    print(f"init_db: {len(lista)} sentencias de schema.sql aplicadas en '{DB_CONFIG['database']}'.", flush=True)


def sembrar():
    import seed_usuarios
    # El seed lee filas como tuplas: misma conexion (y SSL) sin DictCursor.
    seed_usuarios.DB_CONFIG = {k: v for k, v in DB_CONFIG.items() if k != "cursorclass"}
    seed_usuarios.main()


if __name__ == "__main__":
    aplicar_schema()
    if os.environ.get("SEED_DEMO", "false").lower() == "true":
        sembrar()
    else:
        print("init_db: SEED_DEMO no esta activo; no se cargan datos de prueba.", flush=True)
