"""
Sistema de Permisos Ambientales - API (Sprint 8)

Sprint 8:
- HU-13: rol "jefe". Ve todos los expedientes (se asume una sola consultora) y
  es el unico que aprueba internamente (HU-10). El usuario jefe de prueba se
  crea al arrancar si no existe.
- HU-14: tabla historial_expediente (se crea al arrancar si no existe). Se
  registra quien crea un expediente, sube un documento o lo aprueba. Es de
  solo lectura: no hay rutas para editar ni borrar entradas.

Sprint 7:
- La sesion vive en una cookie firmada de Flask (SECRET_KEY). Antes el usuario
  se identificaba con la cabecera X-Usuario-Email, que cualquiera podia inventar.
- Cada endpoint de un expediente revisa que el usuario sea su consultor o su
  promotor. El ZIP, el PDF y las alertas ya no son publicos.
- HU-07: el semaforo de plazos deja de correr cuando el expediente se resuelve,
  el umbral de "por vencer" es proporcional a la categoria y el limite lo da
  el backend.
"""
import io
import math
import time
import os
import re
import secrets
import ssl
import uuid
import zipfile
from contextlib import contextmanager
from datetime import date, datetime
from functools import wraps
from zoneinfo import ZoneInfo

import pymysql
from flask import Flask, g, jsonify, request, send_file, send_from_directory, session
from fpdf import FPDF
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ---------- Configuracion ----------

UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/app/uploads")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
EXTENSIONES_PERMITIDAS = {".pdf", ".zip"}
ZONA = ZoneInfo("America/Panama")

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    # Sin SECRET_KEY la app arranca igual, pero las sesiones se pierden al
    # reiniciar. En el despliegue hay que definirla (ver .env.example).
    _secret = secrets.token_hex(32)
    print("AVISO: SECRET_KEY no esta definida; se usa una clave temporal.", flush=True)

app.secret_key = _secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
    MAX_CONTENT_LENGTH=MAX_FILE_SIZE + 1024 * 1024,
)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_CONFIG = {
    "host": DB_HOST,
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "permisos_ambientales"),
    "cursorclass": pymysql.cursors.DictCursor,
}

# Aiven exige SSL. Con DB_SSL_CA (el ca.pem de Aiven) se verifica el
# certificado; sin el, se mantiene la conexion cifrada sin verificar.
_ca = os.environ.get("DB_SSL_CA")
if _ca:
    DB_CONFIG["ssl"] = ssl.create_default_context(cafile=_ca)
elif "aivencloud" in DB_HOST:
    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE
    DB_CONFIG["ssl"] = _ctx
    print("AVISO: conexion a Aiven sin verificar el certificado; defina DB_SSL_CA.", flush=True)

os.makedirs(UPLOADS_DIR, exist_ok=True)

CATEGORIAS_DOCS = {
    "I":   ["Línea Base", "Plan de Manejo", "Anexos Legales"],
    "II":  ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía"],
    "III": ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía", "Evidencia Foro Público"],
}
PLAZOS_LEGALES = {"I": 20, "II": 40, "III": 80}
ESTADOS_RESUELTOS = {"aprobado", "rechazado"}
ROLES_REGISTRO = {"consultor", "promotor"}  # el jefe no se registra solo
ROLES_INTERNOS = {"consultor", "jefe"}

# HU-13: usuario jefe de prueba. En Render conviene definir JEFE_PASSWORD.
JEFE_EMAIL = os.environ.get("JEFE_EMAIL", "jefe1@ejemplo.com").strip().lower()
JEFE_NOMBRE = os.environ.get("JEFE_NOMBRE", "Jefa de la Consultora")
JEFE_PASSWORD = os.environ.get("JEFE_PASSWORD", "Jefe2026*")

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
ACCION_CREAR = "creó"
ACCION_SUBIR = "subió documento"
ACCION_APROBAR = "aprobó"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RUTAS_SIN_CABECERA = {"/login", "/registro"}


def hoy():
    return datetime.now(ZONA).date()


def ahora():
    # Hora de Panama sin zona: asi se guarda en DATETIME.
    return datetime.now(ZONA).replace(tzinfo=None, microsecond=0)


def problema_de_password(password):
    """Politica del Sprint 6. Devuelve el mensaje de error o None."""
    if not isinstance(password, str):
        return "La contrasena debe ser texto."
    if len(password) < 8:
        return "La contrasena debe tener al menos 8 caracteres."
    if len(password) > 128:
        return "La contrasena admite hasta 128 caracteres."
    if not any(c.isdigit() for c in password):
        return "La contrasena debe incluir al menos un numero."
    if not any(c.isupper() for c in password):
        return "La contrasena debe incluir al menos una letra mayuscula."
    return None


# ---------- Errores ----------

class ApiError(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def respuesta_error(status, mensaje):
    # "error" y "mensaje" a la vez: las pantallas viejas leen uno u otro.
    return jsonify({"ok": False, "error": mensaje, "mensaje": mensaje}), status


@app.errorhandler(ApiError)
def _api_error(e):
    return respuesta_error(e.status, e.mensaje)


@app.errorhandler(HTTPException)
def _http_error(e):
    if e.code == 413:
        return respuesta_error(413, "El archivo supera el limite de 20 MB.")
    return respuesta_error(e.code, e.name)


@app.errorhandler(pymysql.MySQLError)
def _db_error(e):
    print(f"ERROR DE BASE DE DATOS: {e}", flush=True)
    return respuesta_error(500, "Error de base de datos.")


@app.errorhandler(Exception)
def _error_inesperado(e):
    print(f"ERROR INESPERADO: {e!r}", flush=True)
    return respuesta_error(500, "Error interno del servidor.")


@app.after_request
def cabeceras_de_seguridad(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if resp.mimetype == "application/json":
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- Base de datos ----------

@contextmanager
def cursor():
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


# ---------- Arranque: tabla del historial y usuario jefe ----------

def inicializar_bd():
    """Crea lo que el Sprint 8 necesita si no existe. Se puede correr
    muchas veces: no cambia nada si ya esta."""
    problema = problema_de_password(JEFE_PASSWORD)
    if problema:
        raise ValueError(f"JEFE_PASSWORD no cumple la politica: {problema}")
    with cursor() as cur:
        cur.execute(DDL_HISTORIAL)
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
        print("Sprint 8: tabla historial_expediente y usuario jefe verificados.", flush=True)
    except Exception as e:  # noqa: BLE001 - la app sigue; se reintenta luego
        print(f"AVISO: no se pudo preparar la base para el Sprint 8: {e!r}", flush=True)


@app.before_request
def preparar_bd():
    if request.path != "/health":
        asegurar_bd()


# ---------- Sesion y permisos ----------

@app.before_request
def exigir_cabecera_en_escrituras():
    """Proteccion contra CSRF: un formulario de otro sitio no puede mandar
    cabeceras propias. Solo aplica si hay sesion (sin sesion sale 401)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") \
            and request.path not in RUTAS_SIN_CABECERA \
            and session.get("uid") \
            and request.headers.get("X-Requested-With") != "fetch":
        return respuesta_error(403, "Peticion rechazada: falta la cabecera X-Requested-With.")
    return None


def usuario_sesion():
    uid = session.get("uid")
    if not uid:
        return None
    with cursor() as cur:
        cur.execute("SELECT id, email, rol, nombre FROM usuarios WHERE id=%s", (uid,))
        u = cur.fetchone()
    if not u:
        session.clear()
    return u


def requiere_login(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        u = usuario_sesion()
        if not u:
            return respuesta_error(401, "No autenticado")
        g.usuario = u
        return f(*args, **kwargs)
    return envoltura


COLUMNAS_EXPEDIENTE = ("id, codigo, proyecto, promotor, promotor_email, categoria, estado, "
                       "fecha_ingreso, usuario_id, acceso_publico")


def cargar_expediente(cur, codigo):
    cur.execute(f"SELECT {COLUMNAS_EXPEDIENTE} FROM expedientes WHERE codigo=%s", (codigo,))
    exp = cur.fetchone()
    if not exp:
        raise ApiError(404, "Expediente no encontrado.")
    return exp


def puede_ver(u, exp):
    if u["rol"] == "jefe":
        return True  # HU-13: una sola consultora, el jefe ve todo
    if u["rol"] == "promotor":
        return bool(exp["promotor_email"]) and exp["promotor_email"] == u["email"]
    return u["rol"] == "consultor" and exp["usuario_id"] == u["id"]


def exigir_lectura(u, exp):
    if not puede_ver(u, exp):
        raise ApiError(403, "Sin acceso a este expediente.")


def exigir_gestion(u, exp):
    """Subir, borrar, someter: el consultor duenio o el jefe."""
    if u["rol"] == "jefe":
        return
    if u["rol"] != "consultor" or exp["usuario_id"] != u["id"]:
        raise ApiError(403, "No autorizado.")


def exigir_jefe(u):
    if u["rol"] != "jefe":
        raise ApiError(403, "Solo el jefe de la consultora puede aprobar internamente.")


def registrar_historial(cur, expediente_id, usuario_id, accion):
    """HU-14. Va en la misma transaccion que la accion: si una falla, no
    queda ninguna."""
    cur.execute("INSERT INTO historial_expediente (expediente_id, usuario_id, accion, fecha) "
                "VALUES (%s, %s, %s, %s)", (expediente_id, usuario_id, accion, ahora()))


def texto(data, campo, maximo, obligatorio=True):
    valor = data.get(campo, "")
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise ApiError(400, f"El campo '{campo}' debe ser texto.")
    valor = valor.strip()
    if obligatorio and not valor:
        raise ApiError(400, f"El campo '{campo}' es obligatorio.")
    if len(valor) > maximo:
        raise ApiError(400, f"El campo '{campo}' admite hasta {maximo} caracteres.")
    return valor


def entero(nombre, defecto, minimo, maximo):
    valor = request.args.get(nombre, "")
    if valor == "":
        return defecto
    try:
        n = int(valor)
    except ValueError:
        raise ApiError(400, f"'{nombre}' debe ser un numero entero.")
    if n < minimo or n > maximo:
        raise ApiError(400, f"'{nombre}' debe estar entre {minimo} y {maximo}.")
    return n


def como_fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        return datetime.strptime(valor, "%Y-%m-%d").date()
    return valor


# ---------- Verificacion de requisitos y plazos ----------

def es_contenido_valido(file_stream):
    header = file_stream.read(4)
    file_stream.seek(0)
    return header.startswith(b'%PDF') or header.startswith(b'PK\x03\x04')


def calcular_verificacion(categoria, documentos):
    requeridos = CATEGORIAS_DOCS.get(categoria, CATEGORIAS_DOCS["II"])
    docs_por_carpeta = {d["carpeta"]: d["estado"] for d in documentos}
    completos = sum(1 for carpeta in requeridos if docs_por_carpeta.get(carpeta) == "recibido")
    faltantes = [carpeta for carpeta in requeridos if docs_por_carpeta.get(carpeta) != "recibido"]
    return {
        "categoria": categoria,
        "total_requeridos": len(requeridos),
        "completos": completos,
        "faltantes": faltantes,
        "puede_someter": len(faltantes) == 0,
    }


def calcular_semaforo(exp, dia=None):
    """HU-07. Devuelve el estado del plazo legal de un expediente."""
    categoria = exp.get("categoria") if exp.get("categoria") in PLAZOS_LEGALES else "II"
    limite = PLAZOS_LEGALES[categoria]
    umbral = max(2, math.ceil(limite * 0.25))
    base = {
        "expediente": exp["codigo"],
        "categoria": categoria,
        "estado_expediente": exp["estado"],
        "limite_dias": limite,
        "umbral_por_vencer": umbral,
    }

    if exp["estado"] in ESTADOS_RESUELTOS:
        return dict(base,
                    dias_transcurridos=None,
                    dias_restantes_legales=None,
                    estado_semaforo="resuelto",
                    alerta_vencimiento="Resuelto: el plazo legal ya no corre.")

    transcurridos = ((dia or hoy()) - como_fecha(exp["fecha_ingreso"])).days
    restantes = limite - transcurridos
    if restantes < 0:
        estado = "vencido"
        alerta = f"VENCIDO (Supero por {abs(restantes)} dias)"
    elif restantes <= umbral:
        estado = "por_vencer"
        alerta = f"ALERTA CRITICA (Quedan {restantes} dias)"
    else:
        estado = "en_plazo"
        alerta = f"Dentro del plazo legal ({restantes} dias de {limite})"

    return dict(base,
                dias_transcurridos=transcurridos,
                dias_restantes_legales=restantes,
                estado_semaforo=estado,
                alerta_vencimiento=alerta)


# ---------- Estaticos ----------

@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")


@app.route("/api", methods=["GET"])
def api_info():
    return jsonify({"servicio": "Permisos Ambientales - API", "version": "0.9", "estado": "activo"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ---------- Autenticacion ----------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    password = str(data.get("password", "") or "")

    if not email or not password:
        return jsonify({"acceso": False, "mensaje": "Debe ingresar correo y contrasena."}), 401

    with cursor() as cur:
        cur.execute("SELECT id, email, password_hash, rol, nombre FROM usuarios WHERE email=%s", (email,))
        u = cur.fetchone()

    if u and check_password_hash(u["password_hash"], password):
        session.clear()
        session["uid"] = u["id"]
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {u['nombre']}. Acceso concedido a sus expedientes.",
            "rol": u["rol"],
            "nombre": u["nombre"],
            "email": u["email"],
        }), 200

    return jsonify({"acceso": False, "mensaje": "Credenciales incorrectas."}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "mensaje": "Sesion cerrada."}), 200


@app.route("/sesion", methods=["GET"])
@requiere_login
def sesion_actual():
    u = g.usuario
    return jsonify({"email": u["email"], "rol": u["rol"], "nombre": u["nombre"]}), 200


@app.route("/registro", methods=["POST"])
def registro():
    data = request.get_json(silent=True) or {}
    nombre = texto(data, "nombre", 255, obligatorio=False)
    email = texto(data, "email", 255, obligatorio=False).lower()
    password = data.get("password", "")
    rol = data.get("rol", "consultor")

    if not nombre or not email or not password:
        return jsonify({"ok": False, "mensaje": "Todos los campos son obligatorios."}), 400
    if not isinstance(password, str):
        return jsonify({"ok": False, "mensaje": "La contrasena debe ser texto."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"ok": False, "mensaje": "El correo no es valido."}), 400
    if rol not in ROLES_REGISTRO:
        return jsonify({"ok": False, "mensaje": "Rol no permitido. Use consultor o promotor."}), 400
    problema = problema_de_password(password)
    if problema:
        return jsonify({"ok": False, "mensaje": problema}), 400

    try:
        with cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409
            cur.execute(
                "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
                (nombre, email, generate_password_hash(password), rol),
            )
    except pymysql.err.IntegrityError:
        return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409

    return jsonify({"ok": True, "mensaje": "Usuario registrado correctamente."}), 201


# ---------- Dashboard ----------

def filtro_de(u):
    """Condicion SQL (sobre el alias e de expedientes) de lo que ve cada rol."""
    if u["rol"] == "jefe":
        return "1=1", []
    if u["rol"] == "promotor":
        return "e.promotor_email=%s", [u["email"]]
    return "e.usuario_id=%s", [u["id"]]


@app.route("/dashboard", methods=["GET"])
@requiere_login
def dashboard():
    filtro, params = filtro_de(g.usuario)
    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM expedientes e WHERE {filtro}", params)
        activos = cur.fetchone()["n"]
        cur.execute(f"SELECT COUNT(*) AS n FROM expedientes e WHERE {filtro} AND e.estado='pendiente'", params)
        pendientes = cur.fetchone()["n"]
        cur.execute(f"SELECT COUNT(*) AS n FROM expedientes e WHERE {filtro} AND e.estado='aprobado'", params)
        aprobados = cur.fetchone()["n"]
        cur.execute(f"SELECT e.codigo, e.proyecto, e.estado FROM expedientes e WHERE {filtro} "
                    f"ORDER BY e.fecha_ingreso DESC, e.id DESC LIMIT 5", params)
        recientes = cur.fetchall()
        cur.execute(
            f"""SELECT d.carpeta, d.fecha_subida, e.codigo
                FROM documentos d JOIN expedientes e ON e.id = d.expediente_id
                WHERE {filtro} AND d.estado = 'recibido' AND d.fecha_subida IS NOT NULL""", params
        )
        docs_recibidos = cur.fetchall()

    proximas = []
    dia = hoy()
    for d in docs_recibidos:
        dias_restantes = 365 - (dia - como_fecha(d["fecha_subida"])).days
        if dias_restantes < 30:
            proximas.append({
                "codigo": d["codigo"],
                "descripcion": f"{d['carpeta']} vence en {dias_restantes} días",
                "dias_restantes": dias_restantes,
            })
    proximas.sort(key=lambda x: x["dias_restantes"])

    return jsonify({
        "metricas": {"activos": activos, "pendientes": pendientes, "alertas": len(proximas),
                     "aprobados": aprobados},
        "recientes": recientes, "alertas": proximas,
    })


# ---------- Expedientes ----------

@app.route("/expedientes", methods=["GET"])
@requiere_login
def listar_expedientes():
    q = request.args.get("q", "").strip()[:100]
    page = entero("page", 1, 1, 100000)
    per_page = entero("per_page", 50, 1, 100)
    offset = (page - 1) * per_page

    filtro, params = filtro_de(g.usuario)
    where = f"WHERE {filtro}"
    params = list(params)
    if q:
        patron = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where += " AND (e.codigo LIKE %s OR e.proyecto LIKE %s OR e.promotor LIKE %s)"
        params.extend([patron, patron, patron])

    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM expedientes e {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""SELECT e.codigo, e.proyecto, e.promotor, e.categoria, e.estado, e.fecha_ingreso,
                               u.nombre AS consultor
                        FROM expedientes e LEFT JOIN usuarios u ON u.id = e.usuario_id
                        {where} ORDER BY e.fecha_ingreso DESC, e.id DESC LIMIT %s OFFSET %s""",
                    params + [per_page, offset])
        filas = cur.fetchall()

    for f in filas:
        # HU-13: el jefe ve los plazos de cada expediente en la lista.
        sem = calcular_semaforo(f)
        f["plazo"] = {"estado_semaforo": sem["estado_semaforo"],
                      "dias_restantes_legales": sem["dias_restantes_legales"],
                      "limite_dias": sem["limite_dias"]}
        if f["fecha_ingreso"]:
            f["fecha_ingreso"] = f["fecha_ingreso"].strftime("%Y-%m-%d")

    return jsonify({
        "expedientes": filas,
        "paginacion": {"total": total, "page": page, "per_page": per_page,
                       "pages": (total + per_page - 1) // per_page},
    })


@app.route("/expedientes", methods=["POST"])
@requiere_login
def crear_expediente():
    u = g.usuario
    if u["rol"] not in ROLES_INTERNOS:
        raise ApiError(403, "Solo un consultor o el jefe pueden crear expedientes.")

    data = request.get_json(silent=True) or {}
    proyecto = texto(data, "proyecto", 150, obligatorio=False)
    promotor = texto(data, "promotor", 150, obligatorio=False)
    promotor_email = texto(data, "promotor_email", 255, obligatorio=False).lower() or None
    categoria = data.get("categoria", "II")

    if not proyecto or not promotor:
        return jsonify({"ok": False, "mensaje": "Proyecto y promotor son obligatorios."}), 400
    if categoria not in CATEGORIAS_DOCS:
        return jsonify({"ok": False, "mensaje": "Categoria invalida. Use I, II o III."}), 400
    if promotor_email and not EMAIL_RE.match(promotor_email):
        return jsonify({"ok": False, "mensaje": "El correo del promotor no es valido."}), 400

    dia = hoy()
    prefijo = f"SP-A8-{dia.year}-"
    with cursor() as cur:
        # El codigo sale del mayor numero usado (no de COUNT(*), que se repetia
        # si se borraba un expediente). Si dos personas crean a la vez, el
        # UNIQUE de codigo rechaza a la segunda y se reintenta.
        for _ in range(5):
            cur.execute(
                "SELECT MAX(CAST(SUBSTRING(codigo, %s) AS UNSIGNED)) AS n FROM expedientes WHERE codigo LIKE %s",
                (len(prefijo) + 1, prefijo + "%"),
            )
            codigo = f"{prefijo}{(cur.fetchone()['n'] or 0) + 1:03d}"
            try:
                cur.execute(
                    """INSERT INTO expedientes (codigo, proyecto, promotor, promotor_email, categoria,
                                                estado, fecha_ingreso, usuario_id)
                       VALUES (%s, %s, %s, %s, %s, 'pendiente', %s, %s)""",
                    (codigo, proyecto, promotor, promotor_email, categoria, dia.isoformat(), u["id"]),
                )
                break
            except pymysql.err.IntegrityError:
                continue
        else:
            raise ApiError(409, "No se pudo asignar un codigo. Intente de nuevo.")

        exp_id = cur.lastrowid
        for carpeta in CATEGORIAS_DOCS[categoria]:
            cur.execute("INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, 'pendiente')",
                        (exp_id, carpeta))
        registrar_historial(cur, exp_id, u["id"], ACCION_CREAR)

    return jsonify({"ok": True, "codigo": codigo, "mensaje": "Expediente creado."}), 201


@app.route("/expedientes/<codigo>", methods=["GET"])
@requiere_login
def detalle_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT id, carpeta, estado, archivo_nombre, archivo_tamano, fecha_subida "
                    "FROM documentos WHERE expediente_id=%s ORDER BY id", (exp["id"],))
        docs = cur.fetchall()
        cur.execute("SELECT motivo, fecha FROM aprobaciones WHERE expediente_id=%s ORDER BY fecha DESC LIMIT 1",
                    (exp["id"],))
        aprob = cur.fetchone()

    verificacion = calcular_verificacion(exp["categoria"], docs)
    if exp["fecha_ingreso"]:
        exp["fecha_ingreso"] = exp["fecha_ingreso"].strftime("%d/%m/%Y")
    for campo in ("id", "usuario_id", "promotor_email", "acceso_publico"):
        del exp[campo]
    for d in docs:
        if d["fecha_subida"]:
            d["fecha_subida"] = d["fecha_subida"].strftime("%d/%m/%Y %H:%M")
    if aprob and aprob["fecha"]:
        aprob["fecha"] = aprob["fecha"].strftime("%d/%m/%Y %H:%M")

    return jsonify({"expediente": exp, "documentos": docs, "aprobacion": aprob, "verificacion": verificacion})


@app.route("/expedientes/<codigo>/aprobaciones", methods=["GET"])
@requiere_login
def listar_aprobaciones(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("""SELECT a.id, a.motivo, a.fecha, u.nombre AS aprobado_por_nombre FROM aprobaciones a
                       LEFT JOIN usuarios u ON u.id = a.aprobado_por
                       WHERE a.expediente_id = %s ORDER BY a.fecha DESC""", (exp["id"],))
        aprobaciones = cur.fetchall()

    for a in aprobaciones:
        if a["fecha"]:
            a["fecha"] = a["fecha"].strftime("%d/%m/%Y %H:%M")
    return jsonify({"expediente_codigo": exp["codigo"], "estado": exp["estado"], "aprobaciones": aprobaciones})


# ---------- Documentos ----------

@app.route("/expedientes/<codigo>/documentos/<carpeta>/subir", methods=["POST"])
@requiere_login
def subir_documento(codigo, carpeta):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        if exp["estado"] != "pendiente":
            raise ApiError(403, "Expediente no editable.")

        if "archivo" not in request.files:
            raise ApiError(400, "No se recibio archivo.")
        archivo = request.files["archivo"]
        nombre_original = secure_filename(archivo.filename or "")
        ext = os.path.splitext(nombre_original)[1].lower()
        if ext not in EXTENSIONES_PERMITIDAS:
            raise ApiError(400, "Solo PDF y ZIP.")
        if not es_contenido_valido(archivo.stream):
            raise ApiError(400, "Contenido invalido.")

        archivo.stream.seek(0, os.SEEK_END)
        tamano = archivo.stream.tell()
        archivo.stream.seek(0)
        if tamano > MAX_FILE_SIZE:
            raise ApiError(400, "Max 20 MB.")

        cur.execute("SELECT id, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s",
                    (exp["id"], carpeta))
        doc = cur.fetchone()
        if not doc:
            raise ApiError(404, "Documento no encontrado.")

        carpeta_path = os.path.join(UPLOADS_DIR, exp["codigo"])
        os.makedirs(carpeta_path, exist_ok=True)
        nombre_unico = f"{uuid.uuid4().hex[:8]}_{nombre_original}"
        archivo.save(os.path.join(carpeta_path, nombre_unico))

        cur.execute("""UPDATE documentos SET estado='recibido', archivo_nombre=%s, archivo_ruta=%s,
                       archivo_tamano=%s, fecha_subida=NOW() WHERE id=%s""",
                    (nombre_original, os.path.join(exp["codigo"], nombre_unico), tamano, doc["id"]))
        registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_SUBIR)

    # Al reemplazar, el archivo anterior ya no lo apunta nadie.
    borrar_archivo(doc["archivo_ruta"])
    return jsonify({"ok": True, "mensaje": "Subido.", "archivo_nombre": nombre_original,
                    "archivo_tamano": tamano}), 200


def ruta_segura(ruta):
    if not ruta or ".." in ruta or ruta.startswith("/") or ruta.startswith("\\"):
        return None
    return os.path.join(UPLOADS_DIR, ruta)


def borrar_archivo(ruta):
    fisica = ruta_segura(ruta)
    if fisica and os.path.exists(fisica):
        try:
            os.remove(fisica)
        except OSError:
            pass


@app.route("/expedientes/<codigo>/documentos/<carpeta>/descargar", methods=["GET"])
@requiere_login
def descargar_documento(codigo, carpeta):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT archivo_nombre, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s",
                    (exp["id"], carpeta))
        doc = cur.fetchone()

    if not doc or not doc["archivo_ruta"]:
        raise ApiError(404, "No disponible")
    fisica = ruta_segura(doc["archivo_ruta"])
    if not fisica:
        raise ApiError(400, "Ruta invalida")
    if not os.path.exists(fisica):
        raise ApiError(404, "No en disco")

    return send_from_directory(os.path.dirname(fisica), os.path.basename(fisica),
                               as_attachment=True, download_name=doc["archivo_nombre"])


@app.route("/expedientes/<codigo>/documentos/<carpeta>/eliminar", methods=["DELETE", "POST"])
@requiere_login
def eliminar_documento(codigo, carpeta):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        if exp["estado"] != "pendiente":
            raise ApiError(403, "Expediente no editable.")
        cur.execute("SELECT id, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s",
                    (exp["id"], carpeta))
        doc = cur.fetchone()
        if not doc or not doc["archivo_ruta"]:
            raise ApiError(400, "No tiene archivo.")
        cur.execute("""UPDATE documentos SET estado='pendiente', archivo_nombre=NULL, archivo_ruta=NULL,
                       archivo_tamano=NULL, fecha_subida=NULL WHERE id=%s""", (doc["id"],))

    borrar_archivo(doc["archivo_ruta"])
    return jsonify({"ok": True, "mensaje": "Documento eliminado."}), 200


@app.route("/expedientes/<codigo>/descargar-todo", methods=["GET"])
@requiere_login
def descargar_zip_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT carpeta, archivo_nombre, archivo_ruta FROM documentos "
                    "WHERE expediente_id=%s AND estado='recibido'", (exp["id"],))
        docs = cur.fetchall()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        indice_txt = (f"EXPEDIENTE: {exp['codigo']}\nProyecto: {exp['proyecto']}\nPromotor: {exp['promotor']}\n"
                      f"Categoría: {exp['categoria']}\nFecha: {datetime.now(ZONA).strftime('%Y-%m-%d %H:%M:%S')}"
                      f"\n\nArchivos:\n")
        for d in docs:
            indice_txt += f"- [{d['carpeta']}] {d['archivo_nombre']}\n"
            fisica = ruta_segura(d["archivo_ruta"])
            if fisica and os.path.exists(fisica):
                zf.write(fisica, arcname=f"{d['carpeta'].replace(' ', '_')}/{d['archivo_nombre']}")
        zf.writestr('Indice_Expediente.txt', indice_txt)

    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True,
                     download_name=f"{exp['codigo']}_completo.zip")


# ---------- PDF ----------

def latin1(valor):
    # Las fuentes base de FPDF solo traen latin-1; un emoji tumbaba el PDF.
    return str(valor).encode("latin-1", "replace").decode("latin-1")


@app.route("/expedientes/<codigo>/pdf", methods=["GET"])
@requiere_login
def generar_pdf_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s ORDER BY id", (exp["id"],))
        docs = cur.fetchall()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "Resumen Ejecutivo del Expediente", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(10)

    pdf.set_font("Helvetica", '', 12)
    for etiqueta, valor in (("Codigo", exp["codigo"]), ("Proyecto", exp["proyecto"]),
                            ("Promotor", exp["promotor"]), ("Categoria", exp["categoria"]),
                            ("Estado", exp["estado"]), ("Fecha de Ingreso", exp["fecha_ingreso"])):
        pdf.cell(0, 10, latin1(f"{etiqueta}: {valor}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Documentos del expediente:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", '', 12)
    for d in docs:
        estado_doc = "Recibido" if d['estado'] == 'recibido' else "Pendiente"
        pdf.cell(0, 10, latin1(f"- {d['carpeta']}: {estado_doc}"), new_x="LMARGIN", new_y="NEXT")

    return send_file(io.BytesIO(bytes(pdf.output())), mimetype='application/pdf', as_attachment=True,
                     download_name=f"{exp['codigo']}-resumen.pdf")


# ---------- Plazos (HU-07) ----------

@app.route("/expedientes/<codigo>/alertas", methods=["GET"])
@requiere_login
def obtener_alertas(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
    return jsonify(calcular_semaforo(exp)), 200


# ---------- Acciones del flujo ----------

@app.route("/expedientes/<codigo>/aprobar", methods=["POST"])
@requiere_login
def aprobar_expediente(codigo):
    data = request.get_json(silent=True) or {}
    motivo = texto(data, "motivo", 2000, obligatorio=False)
    if not motivo:
        return jsonify({"ok": False, "mensaje": "Motivo obligatorio."}), 400

    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_jefe(g.usuario)  # HU-13: solo el jefe aprueba internamente
        if exp["estado"] != "pendiente":
            raise ApiError(400, "Estado invalido.")
        cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s", (exp["id"],))
        verif = calcular_verificacion(exp["categoria"], cur.fetchall())
        if not verif["puede_someter"]:
            raise ApiError(400, f"Faltan: {', '.join(verif['faltantes'])}")
        cur.execute("INSERT INTO aprobaciones (expediente_id, motivo, aprobado_por) VALUES (%s, %s, %s)",
                    (exp["id"], motivo, g.usuario["id"]))
        # Condicional: si dos pestanas aprueban a la vez, solo una cambia el estado.
        cambiadas = cur.execute("UPDATE expedientes SET estado='aprobado_interno' WHERE id=%s AND estado='pendiente'",
                                (exp["id"],))
        if cambiadas != 1:
            raise ApiError(400, "Estado invalido.")
        registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_APROBAR)
    return jsonify({"ok": True, "mensaje": "Aprobado internamente."}), 200


def cambiar_estado(codigo, desde, hacia, mensaje_error):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        if exp["estado"] != desde:
            raise ApiError(400, mensaje_error)
        cambiadas = cur.execute("UPDATE expedientes SET estado=%s WHERE id=%s AND estado=%s",
                                (hacia, exp["id"], desde))
        if cambiadas != 1:
            raise ApiError(400, mensaje_error)


@app.route("/expedientes/<codigo>/someter", methods=["POST"])
@requiere_login
def someter_expediente(codigo):
    cambiar_estado(codigo, "aprobado_interno", "evaluacion", "Debe aprobarse internamente primero.")
    return jsonify({"ok": True, "mensaje": "Sometido a MiAmbiente."}), 200


@app.route("/expedientes/<codigo>/aprobar-miambiente", methods=["POST"])
@requiere_login
def aprobar_miambiente(codigo):
    cambiar_estado(codigo, "evaluacion", "aprobado", "Debe estar en evaluacion.")
    return jsonify({"ok": True, "mensaje": "Aprobado por MiAmbiente."}), 200


# ---------- Historial (HU-14) ----------

@app.route("/historial", methods=["GET"])
@app.route("/expedientes/<codigo>/historial", methods=["GET"])
@requiere_login
def ver_historial(codigo=None):
    """Jefe: todo. Consultor: solo sus expedientes. Promotor: 403."""
    u = g.usuario
    if u["rol"] not in ROLES_INTERNOS:
        raise ApiError(403, "El historial solo lo ven el jefe y los consultores.")

    codigo = codigo or request.args.get("codigo", "").strip() or None
    page = entero("page", 1, 1, 100000)
    per_page = entero("per_page", 50, 1, 200)

    condiciones, params = [], []
    with cursor() as cur:
        if codigo:
            exp = cargar_expediente(cur, codigo)
            exigir_lectura(u, exp)
            condiciones.append("h.expediente_id=%s")
            params.append(exp["id"])
        if u["rol"] == "consultor":
            condiciones.append("e.usuario_id=%s")
            params.append(u["id"])
        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        cur.execute(f"SELECT COUNT(*) AS total FROM historial_expediente h "
                    f"JOIN expedientes e ON e.id = h.expediente_id {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""SELECT h.id, h.fecha, h.accion, e.codigo, e.proyecto,
                               u.nombre AS usuario, u.email AS usuario_email, u.rol AS usuario_rol
                        FROM historial_expediente h
                        JOIN expedientes e ON e.id = h.expediente_id
                        JOIN usuarios u ON u.id = h.usuario_id
                        {where}
                        ORDER BY h.fecha DESC, h.id DESC LIMIT %s OFFSET %s""",
                    params + [per_page, (page - 1) * per_page])
        filas = cur.fetchall()

    for f in filas:
        f["fecha"] = f["fecha"].strftime("%Y-%m-%d %H:%M:%S") if f["fecha"] else None
    return jsonify({
        "historial": filas,
        "paginacion": {"total": total, "page": page, "per_page": per_page,
                       "pages": (total + per_page - 1) // per_page},
    })


@app.route("/historial", methods=["POST", "PUT", "PATCH", "DELETE"])
@app.route("/historial/<path:_resto>", methods=["POST", "PUT", "PATCH", "DELETE"])
@app.route("/expedientes/<codigo>/historial", methods=["POST", "PUT", "PATCH", "DELETE"])
@app.route("/expedientes/<codigo>/historial/<path:_resto>", methods=["POST", "PUT", "PATCH", "DELETE"])
def historial_solo_lectura(codigo=None, _resto=None):
    # HU-14: nadie, ni el jefe, edita ni borra entradas.
    return respuesta_error(405, "El historial es de solo lectura.")


# ---------- Consulta publica (HU-09) ----------

@app.route("/consulta/<codigo>", methods=["GET"])
def consulta_publica(codigo):
    with cursor() as cur:
        cur.execute("SELECT codigo, proyecto, promotor, categoria, estado, acceso_publico "
                    "FROM expedientes WHERE codigo=%s", (codigo,))
        exp = cur.fetchone()
    if not exp:
        raise ApiError(404, "No encontrado")
    return jsonify({"expediente": exp}), 200


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


asegurar_bd()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
