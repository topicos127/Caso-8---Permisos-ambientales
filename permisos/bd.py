"""Conexion a MySQL, consultas compartidas y preparacion de la base al arrancar."""
import time
from contextlib import contextmanager

import pymysql
from werkzeug.security import generate_password_hash

from .config import (ADMIN_EMAIL, ADMIN_NOMBRE, ADMIN_PASSWORD, DB_CONFIG, JEFE_EMAIL, JEFE_INICIAL, JEFE_NOMBRE,
                     JEFE_PASSWORD, ORG_POR_DEFECTO)
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
    """Con la fecha de sometimiento y la empresa, si esas columnas existen."""
    return f"{COLUMNAS_EXPEDIENTE}, {col_sometimiento('')}, {col_org('')}"


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


# Separacion por empresa, invitaciones, recuperacion de acceso, comentarios y vistas guardadas.
DDL_EMPRESAS = [
    """CREATE TABLE IF NOT EXISTS organizaciones (
        id INT NOT NULL AUTO_INCREMENT,
        nombre VARCHAR(150) NOT NULL,
        color VARCHAR(7) NOT NULL DEFAULT '#17805a',
        logo_ruta VARCHAR(500) NULL,
        activa BOOLEAN NOT NULL DEFAULT TRUE,
        fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_organizacion_nombre (nombre)
    )""",
    """CREATE TABLE IF NOT EXISTS invitaciones (
        id INT NOT NULL AUTO_INCREMENT,
        token_hash CHAR(64) NOT NULL,
        organizacion_id INT NOT NULL,
        rol VARCHAR(20) NOT NULL,
        email VARCHAR(255) NULL,
        creada_por INT NOT NULL,
        fecha_creacion DATETIME NOT NULL,
        expira DATETIME NOT NULL,
        usada_en DATETIME NULL,
        usada_por INT NULL,
        revocada BOOLEAN NOT NULL DEFAULT FALSE,
        PRIMARY KEY (id),
        UNIQUE KEY uq_invitacion_token (token_hash),
        FOREIGN KEY (organizacion_id) REFERENCES organizaciones (id),
        FOREIGN KEY (creada_por) REFERENCES usuarios (id)
    )""",
    """CREATE TABLE IF NOT EXISTS codigos_recuperacion (
        id INT NOT NULL AUTO_INCREMENT,
        usuario_id INT NOT NULL,
        codigo_hash CHAR(64) NOT NULL,
        fecha_creacion DATETIME NOT NULL,
        usado_en DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_codigo_recuperacion (codigo_hash),
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )""",
    """CREATE TABLE IF NOT EXISTS comentarios (
        id INT NOT NULL AUTO_INCREMENT,
        expediente_id INT NOT NULL,
        usuario_id INT NOT NULL,
        texto TEXT NOT NULL,
        fecha DATETIME NOT NULL,
        PRIMARY KEY (id),
        KEY ix_comentarios_expediente (expediente_id),
        FOREIGN KEY (expediente_id) REFERENCES expedientes (id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )""",
    """CREATE TABLE IF NOT EXISTS eventos_cuenta (
        id BIGINT NOT NULL AUTO_INCREMENT,
        organizacion_id INT NULL,
        usuario_id INT NULL,
        email VARCHAR(255) NULL,
        tipo VARCHAR(40) NOT NULL,
        detalle VARCHAR(300) NULL,
        ip VARCHAR(64) NULL,
        fecha DATETIME NOT NULL,
        PRIMARY KEY (id),
        KEY ix_eventos_org_fecha (organizacion_id, fecha),
        KEY ix_eventos_usuario (usuario_id, tipo, fecha)
    )""",
    """CREATE TABLE IF NOT EXISTS vistas_guardadas (
        id INT NOT NULL AUTO_INCREMENT,
        usuario_id INT NOT NULL,
        nombre VARCHAR(60) NOT NULL,
        filtros VARCHAR(1000) NOT NULL,
        fecha DATETIME NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )""",
]

# Sprint 9: el promotor recibe una contrasena temporal y debe cambiarla. La
# columna se agrega al arrancar si la base es anterior; mientras no exista, las
# consultas la reemplazan por un 0 constante y la regla simplemente no aplica.
# Sprint 10: lo mismo con la fecha de sometimiento (HU-08), la fecha de
# vencimiento de cada documento y el aviso que elige cada usuario (HU-05).
_esquema = {"cambio_clave": False, "activo": False, "sometimiento": False, "vencimiento": False,
            "aviso": False, "org": False, "totp": False, "sesion": False, "terminos": False,
            "org_perfil": False, "org_politica": False, "titular": False, "tour": False}
_columnas_ok = set()

# (tabla, columna, definicion, clave en _esquema)
COLUMNAS_SPRINT10 = (
    ("expedientes", "fecha_sometimiento", "DATE NULL", "sometimiento"),
    ("documentos", "fecha_vencimiento", "DATE NULL", "vencimiento"),
    ("usuarios", "aviso_vencimiento_dias", "INT NOT NULL DEFAULT 30", "aviso"),
    # Separacion por empresa
    ("usuarios", "organizacion_id", "INT NULL", "org_usuarios"),
    ("expedientes", "organizacion_id", "INT NULL", "org_expedientes"),
    # Verificacion en dos pasos y control de sesiones
    ("usuarios", "totp_secreto", "VARCHAR(255) NULL", "totp_secreto"),
    ("usuarios", "totp_activo", "BOOLEAN NOT NULL DEFAULT FALSE", "totp_activo"),
    ("usuarios", "totp_ultimo_paso", "BIGINT NOT NULL DEFAULT 0", "totp_paso"),
    ("usuarios", "sesion_version", "INT NOT NULL DEFAULT 0", "sesion"),
    ("usuarios", "terminos_aceptados_en", "DATETIME NULL", "terminos"),
    # Mi consultora: datos de la empresa, politica de seguridad y titular
    # Recorrido de bienvenida: se muestra una sola vez por cuenta
    ("usuarios", "tour_visto_en", "DATETIME NULL", "tour"),
    ("organizaciones", "razon_social", "VARCHAR(200) NULL", "org_razon"),
    ("organizaciones", "ruc", "VARCHAR(40) NULL", "org_ruc"),
    ("organizaciones", "direccion", "VARCHAR(300) NULL", "org_direccion"),
    ("organizaciones", "telefono", "VARCHAR(40) NULL", "org_telefono"),
    ("organizaciones", "email_contacto", "VARCHAR(255) NULL", "org_email"),
    ("organizaciones", "pie_documento", "VARCHAR(300) NULL", "org_pie"),
    ("organizaciones", "exigir_2fa", "BOOLEAN NOT NULL DEFAULT FALSE", "org_2fa"),
    ("organizaciones", "sesion_minutos", "INT NULL", "org_sesion"),
    ("organizaciones", "aviso_defecto", "INT NULL", "org_aviso"),
    ("organizaciones", "titular_id", "INT NULL", "org_titular"),
)


def _pref(alias):
    return f"{alias}." if alias else ""


def col_sometimiento(alias="e"):
    return f"{_pref(alias)}fecha_sometimiento" if _esquema["sometimiento"] else "NULL AS fecha_sometimiento"


def col_vencimiento(alias="d"):
    return f"{_pref(alias)}fecha_vencimiento" if _esquema["vencimiento"] else "NULL AS fecha_vencimiento"


def col_aviso(alias=""):
    return f"{_pref(alias)}aviso_vencimiento_dias" if _esquema["aviso"] else "30 AS aviso_vencimiento_dias"


def col_org(alias="e"):
    """Empresa a la que pertenece la fila (usuario o expediente)."""
    return f"{_pref(alias)}organizacion_id" if _esquema["org"] else "NULL AS organizacion_id"


def col_sesion(alias=""):
    return f"{_pref(alias)}sesion_version" if _esquema["sesion"] else "0 AS sesion_version"


def col_totp(alias=""):
    if _esquema["totp"]:
        p = _pref(alias)
        return f"{p}totp_activo, {p}totp_secreto, {p}totp_ultimo_paso"
    return "0 AS totp_activo, NULL AS totp_secreto, 0 AS totp_ultimo_paso"


def _asegurar_columna(cur, tabla, columna, definicion, clave):
    cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = %s AND COLUMN_NAME = %s", (tabla, columna))
    if cur.fetchone()["n"] == 0:
        cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
        print(f"Base de datos: columna {tabla}.{columna} agregada.", flush=True)
    _columnas_ok.add(clave)
    if clave in _esquema:
        _esquema[clave] = True


def _asegurar_fk(cur, tabla, nombre, columna, referencia):
    cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s", (tabla, nombre))
    if cur.fetchone()["n"] == 0:
        cur.execute(f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} FOREIGN KEY ({columna}) REFERENCES {referencia}")


def _derivar_banderas():
    """Las funciones que usan varias columnas solo se activan si estan todas."""
    _esquema["org"] = {"org_usuarios", "org_expedientes"} <= _columnas_ok
    _esquema["totp"] = {"totp_secreto", "totp_activo", "totp_paso"} <= _columnas_ok
    _esquema["org_perfil"] = {"org_razon", "org_ruc", "org_direccion", "org_telefono", "org_email", "org_pie"} <= _columnas_ok
    _esquema["org_politica"] = {"org_2fa", "org_sesion", "org_aviso"} <= _columnas_ok
    _esquema["titular"] = "org_titular" in _columnas_ok


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
    problema = problema_de_password(JEFE_PASSWORD) if JEFE_INICIAL else None
    if problema:
        raise ValueError(f"JEFE_PASSWORD no cumple la politica: {problema}")
    with cursor() as cur:
        cur.execute(DDL_HISTORIAL)
        cur.execute(DDL_VERSIONES)
        cur.execute(DDL_RESOLUCIONES)
        cur.execute(DDL_OBSERVACIONES)
        for ddl in DDL_EMPRESAS:
            cur.execute(ddl)
    for tabla, columna, definicion, clave in COLUMNAS_SPRINT10:
        try:
            with cursor() as cur:
                _asegurar_columna(cur, tabla, columna, definicion, clave)
        except pymysql.MySQLError as e:
            # Sin la columna la app sigue con la regla anterior (plan B:
            # sql/sprint10_manual.sql).
            print(f"AVISO: no se pudo agregar {tabla}.{columna} ({e!r}); la funcion que la usa queda "
                  "inactiva hasta que exista.", flush=True)
    _derivar_banderas()
    if _esquema["org"]:
        with cursor() as cur:
            _asegurar_fk(cur, "usuarios", "fk_usuarios_organizacion", "organizacion_id", "organizaciones (id)")
            _asegurar_fk(cur, "expedientes", "fk_expedientes_organizacion", "organizacion_id", "organizaciones (id)")
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
    org_defecto = _preparar_empresa_por_defecto()
    if _esquema["titular"]:
        with cursor() as cur:
            # El titular de cada empresa es su primer director de proyectos (si aun no se definio).
            cur.execute("UPDATE organizaciones o SET o.titular_id = (SELECT MIN(u.id) FROM usuarios u "
                        "WHERE u.organizacion_id = o.id AND u.rol = 'jefe') WHERE o.titular_id IS NULL")
    with cursor() as cur:
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (JEFE_EMAIL,))
        if JEFE_INICIAL and not cur.fetchone():
            try:
                columna, marca, valor = (", organizacion_id", ", %s", (org_defecto,)) if org_defecto else ("", "", ())
                cur.execute(f"INSERT INTO usuarios (nombre, email, password_hash, rol{columna}) "
                            f"VALUES (%s, %s, %s, 'jefe'{marca})",
                            (JEFE_NOMBRE, JEFE_EMAIL, generate_password_hash(JEFE_PASSWORD), *valor))
                print(f"Usuario jefe creado ({JEFE_EMAIL}).", flush=True)
            except pymysql.err.IntegrityError:
                pass  # otro proceso lo creo al mismo tiempo
    _crear_administrador()


def _hay_datos_sin_empresa(cur):
    """Hay usuarios (salvo el administrador) o expedientes de antes de la separacion por empresa."""
    cur.execute("SELECT (SELECT COUNT(*) FROM usuarios WHERE rol <> 'admin' AND organizacion_id IS NULL) + "
                "(SELECT COUNT(*) FROM expedientes WHERE organizacion_id IS NULL) AS n")
    return (cur.fetchone()["n"] or 0) > 0


def _preparar_empresa_por_defecto():
    """Empresa que recibe lo anterior a la separacion por empresa: los usuarios y
    expedientes sin empresa pasan a ella. Devuelve su id (None sin la columna)."""
    if not _esquema["org"]:
        return None
    with cursor() as cur:
        cur.execute("SELECT id FROM organizaciones ORDER BY id LIMIT 1")
        fila = cur.fetchone()
        if fila:
            org_id = fila["id"]
        else:
            if not JEFE_INICIAL and not _hay_datos_sin_empresa(cur):
                return None  # base nueva en produccion: las empresas las crea el administrador
            cur.execute("INSERT INTO organizaciones (nombre) VALUES (%s)", (ORG_POR_DEFECTO,))
            org_id = cur.lastrowid
            print(f"Empresa por defecto creada: {ORG_POR_DEFECTO}.", flush=True)
        cur.execute("UPDATE usuarios SET organizacion_id=%s WHERE organizacion_id IS NULL AND rol <> 'admin'", (org_id,))
        cur.execute("UPDATE expedientes SET organizacion_id=%s WHERE organizacion_id IS NULL", (org_id,))
    return org_id


def _crear_administrador():
    problema = problema_de_password(ADMIN_PASSWORD)
    if problema:
        raise ValueError(f"ADMIN_PASSWORD no cumple la politica: {problema}")
    with cursor() as cur:
        cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (ADMIN_EMAIL,))
        existente = cur.fetchone()
        if existente:
            if existente["rol"] != "admin":
                print(f"AVISO: ADMIN_EMAIL ({ADMIN_EMAIL}) ya pertenece a una cuenta que no es de administrador.",
                      flush=True)
            return
        try:
            cur.execute("INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, 'admin')",
                        (ADMIN_NOMBRE, ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)))
            print(f"Administrador de la plataforma creado ({ADMIN_EMAIL}).", flush=True)
        except pymysql.err.IntegrityError:
            pass


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
        print("Base de datos verificada: tablas, columnas, empresa por defecto y cuentas base.", flush=True)
    except Exception as e:  # noqa: BLE001 - la app sigue; se reintenta luego
        print(f"AVISO: no se pudo preparar la base: {e!r}", flush=True)
