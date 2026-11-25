"""Conexion a MySQL, consultas compartidas y preparacion de la base al arrancar."""
import time
from contextlib import contextmanager

import pymysql
from werkzeug.security import generate_password_hash

from .config import DB_CONFIG, JEFE_EMAIL, JEFE_NOMBRE, JEFE_PASSWORD
from .errores import ApiError
from .reglas import ahora, problema_de_password


@contextmanager
def cursor():
    """Una conexion por bloque: commit si todo sale bien, rollback si no."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- Consultas compartidas ----------

COLUMNAS_EXPEDIENTE = ("id, codigo, proyecto, promotor, promotor_email, categoria, estado, "
                       "fecha_ingreso, usuario_id, acceso_publico")


def columnas_expediente():
    """Sprint 10 (HU-08): con la fecha de sometimiento si la columna existe."""
    return f"{COLUMNAS_EXPEDIENTE}, {col_sometimiento('')}"


def cargar_expediente(cur, codigo):
    cur.execute(f"SELECT {columnas_expediente()} FROM expedientes WHERE codigo=%s", (codigo,))
    exp = cur.fetchone()
    if not exp:
        raise ApiError(404, "Expediente no encontrado.")
    return exp


# Ultima version de cada documento (alias d), para las consultas de documentos.
SQL_ULTIMA_VERSION = ("(SELECT MAX(v.version) FROM documento_versiones v WHERE v.documento_id = d.id) AS version, "
                      "(SELECT v.codigo_trazabilidad FROM documento_versiones v WHERE v.documento_id = d.id "
                      "ORDER BY v.version DESC LIMIT 1) AS codigo_trazabilidad")


def documentos_de(cur, expediente_ids):
    """Documentos de varios expedientes en una sola consulta: {id: [docs]}."""
    por_expediente = {i: [] for i in expediente_ids}
    if not expediente_ids:
        return por_expediente
    marcas = ", ".join(["%s"] * len(expediente_ids))
    cur.execute(f"SELECT expediente_id, carpeta, estado, fecha_subida, {col_vencimiento('')} FROM documentos "
                f"WHERE expediente_id IN ({marcas})", list(expediente_ids))
    for d in cur.fetchall():
        por_expediente[d["expediente_id"]].append(d)
    return por_expediente


def registrar_historial(cur, expediente_id, usuario_id, accion):
    """HU-14. Va en la misma transaccion que la accion: si una falla, no
    queda ninguna."""
    cur.execute("INSERT INTO historial_expediente (expediente_id, usuario_id, accion, fecha) "
                "VALUES (%s, %s, %s, %s)", (expediente_id, usuario_id, accion, ahora()))


# ---------- Arranque: tabla del historial y usuario jefe ----------

# HU-14: misma estructura de la revision de tablas del Sprint 8.
DDL_HISTORIAL = """
CREATE TABLE IF NOT EXISTS historial_expediente (
    id INT NOT NULL AUTO_INCREMENT,
    expediente_id INT NOT NULL,
    usuario_id INT NOT NULL,
    accion VARCHAR(50) NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
)
"""


# Sprint 9 (HU-01): versiones de cada documento. Nunca se modifican ni se
# eliminan; documentos.archivo_ruta apunta siempre a la ultima.
DDL_VERSIONES = """
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
)
"""


# Sprint 10: resolucion de MiAmbiente (aprobado o rechazado, con numero y fecha)
# y observaciones con las que el jefe devuelve un expediente al consultor.
DDL_RESOLUCIONES = """
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
)
"""

DDL_OBSERVACIONES = """
CREATE TABLE IF NOT EXISTS observaciones (
    id INT NOT NULL AUTO_INCREMENT,
    expediente_id INT NOT NULL,
    texto TEXT NOT NULL,
    autor_id INT NOT NULL,
    fecha DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
    FOREIGN KEY (autor_id) REFERENCES usuarios (id)
)
"""


# Sprint 9: el promotor recibe una contrasena temporal y debe cambiarla. La
# columna se agrega al arrancar si la base es anterior; mientras no exista, las
# consultas la reemplazan por un 0 constante y la regla simplemente no aplica.
# Sprint 10: lo mismo con la fecha de sometimiento (HU-08), la fecha de
# vencimiento de cada documento y el aviso que elige cada usuario (HU-05).
_esquema = {"cambio_clave": False, "activo": False, "sometimiento": False, "vencimiento": False,
            "aviso": False}

# (tabla, columna, definicion, clave en _esquema)
COLUMNAS_SPRINT10 = (
    ("expedientes", "fecha_sometimiento", "DATE NULL", "sometimiento"),
    ("documentos", "fecha_vencimiento", "DATE NULL", "vencimiento"),
    ("usuarios", "aviso_vencimiento_dias", "INT NOT NULL DEFAULT 30", "aviso"),
)


def _pref(alias):
    return f"{alias}." if alias else ""


def col_sometimiento(alias="e"):
    return f"{_pref(alias)}fecha_sometimiento" if _esquema["sometimiento"] else "NULL AS fecha_sometimiento"


def col_vencimiento(alias="d"):
    return f"{_pref(alias)}fecha_vencimiento" if _esquema["vencimiento"] else "NULL AS fecha_vencimiento"


def col_aviso(alias=""):
    return f"{_pref(alias)}aviso_vencimiento_dias" if _esquema["aviso"] else "30 AS aviso_vencimiento_dias"


def _asegurar_columna(cur, tabla, columna, definicion, clave):
    cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = %s AND COLUMN_NAME = %s", (tabla, columna))
    if cur.fetchone()["n"] == 0:
        cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
        print(f"Sprint 10: columna {tabla}.{columna} agregada.", flush=True)
    _esquema[clave] = True


def col_cambio_clave():
    return "debe_cambiar_clave" if _esquema["cambio_clave"] else "0 AS debe_cambiar_clave"


def col_activo():
    """Sprint 9 (equipo de consultores): baja logica. Mientras la columna no
    exista, todos los usuarios cuentan como activos."""
    return "activo" if _esquema["activo"] else "1 AS activo"


def _asegurar_columna_activo(cur):
    cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'activo'")
    if cur.fetchone()["n"] == 0:
        cur.execute("ALTER TABLE usuarios ADD COLUMN activo BOOLEAN NOT NULL DEFAULT TRUE")
        print("Sprint 9: columna usuarios.activo agregada.", flush=True)
    _esquema["activo"] = True


def _asegurar_columna_cambio_clave(cur):
    cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'debe_cambiar_clave'")
    if cur.fetchone()["n"] == 0:
        cur.execute("ALTER TABLE usuarios ADD COLUMN debe_cambiar_clave BOOLEAN NOT NULL DEFAULT FALSE")
        print("Sprint 9: columna usuarios.debe_cambiar_clave agregada.", flush=True)
    _esquema["cambio_clave"] = True


def inicializar_bd():
    """Crea lo que los Sprints 8 y 9 necesitan si no existe. Se puede correr
    muchas veces: no cambia nada si ya esta."""
    problema = problema_de_password(JEFE_PASSWORD)
    if problema:
        raise ValueError(f"JEFE_PASSWORD no cumple la politica: {problema}")
    with cursor() as cur:
        cur.execute(DDL_HISTORIAL)
        cur.execute(DDL_VERSIONES)
        cur.execute(DDL_RESOLUCIONES)
        cur.execute(DDL_OBSERVACIONES)
    for tabla, columna, definicion, clave in COLUMNAS_SPRINT10:
        try:
            with cursor() as cur:
                _asegurar_columna(cur, tabla, columna, definicion, clave)
        except pymysql.MySQLError as e:
            # Sin la columna la app sigue con la regla anterior (plan B:
            # sql/sprint10_manual.sql).
            print(f"AVISO: no se pudo agregar {tabla}.{columna} ({e!r}); se usa la regla del Sprint 9 "
                  "hasta que exista.", flush=True)
    try:
        with cursor() as cur:
            _asegurar_columna_cambio_clave(cur)
    except pymysql.MySQLError as e:
        # Por ejemplo, un usuario de la base sin permiso ALTER. No debe impedir el
        # resto del arranque: la regla de contrasena temporal queda inactiva.
        print(f"AVISO: no se pudo agregar usuarios.debe_cambiar_clave ({e!r}); "
              "la contrasena temporal no se exigira hasta que exista la columna.", flush=True)
    try:
        with cursor() as cur:
            _asegurar_columna_activo(cur)
    except pymysql.MySQLError as e:
        # Igual que la columna anterior: sin ella, nadie queda desactivado y
        # desactivar responde 503 hasta que exista (plan B: sql/sprint9_manual.sql).
        print(f"AVISO: no se pudo agregar usuarios.activo ({e!r}); "
              "no se podra desactivar consultores hasta que exista la columna.", flush=True)
    with cursor() as cur:
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (JEFE_EMAIL,))
        if not cur.fetchone():
            try:
                cur.execute("INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, 'jefe')",
                            (JEFE_NOMBRE, JEFE_EMAIL, generate_password_hash(JEFE_PASSWORD)))
                print(f"Sprint 8: usuario jefe creado ({JEFE_EMAIL}).", flush=True)
            except pymysql.err.IntegrityError:
                pass  # otro proceso lo creo al mismo tiempo


_estado_bd = {"lista": False, "ultimo_intento": 0.0}


def asegurar_bd():
    """Si la base aun no tiene las tablas (por ejemplo, start.ps1 aplica el
    schema despues de levantar la app), se reintenta cada 30 s."""
    if _estado_bd["lista"] or time.time() - _estado_bd["ultimo_intento"] < 30:
        return
    _estado_bd["ultimo_intento"] = time.time()
    try:
        inicializar_bd()
        _estado_bd["lista"] = True
        print("Sprints 8 a 10: historial, versiones, resoluciones, observaciones, usuario jefe y columnas "
              "nuevas verificados.", flush=True)
    except Exception as e:  # noqa: BLE001 - la app sigue; se reintenta luego
        print(f"AVISO: no se pudo preparar la base para el Sprint 8: {e!r}", flush=True)
