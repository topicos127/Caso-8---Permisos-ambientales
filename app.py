"""
Sistema de Permisos Ambientales - API completa (Sprint 3)
"""
import os
from datetime import date
import pymysql
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "permisos123"),
    "database": os.environ.get("DB_NAME", "permisos_ambientales"),
    "cursorclass": pymysql.cursors.DictCursor,
}

# Documentos exigidos por categoria de Estudio de Impacto Ambiental,
# conforme al Decreto Ejecutivo 59 de 2000 (Articulos 23, 24 y 25).
# Cada categoria acumula los documentos de la categoria anterior.
DOCS_CATEGORIA_I = [
    "Paz y Salvo de la ANAM",
    "Descripcion del proyecto",
    "Descripcion del area de influencia",
    "Identificacion de impactos",
    "Declaracion jurada notariada",
]
DOCS_CATEGORIA_II = DOCS_CATEGORIA_I + [
    "Resumen ejecutivo (max. 20 paginas)",
    "Plan de Manejo Ambiental",
    "Plan de participacion ciudadana",
    "Equipo de profesionales",
    "Anexos cartograficos",
]
DOCS_CATEGORIA_III = [
    d for d in DOCS_CATEGORIA_II if d != "Resumen ejecutivo (max. 20 paginas)"
] + [
    "Resumen ejecutivo (max. 40 paginas)",
    "Evidencia de foro publico",
]
DOCS_POR_CATEGORIA = {
    "I": DOCS_CATEGORIA_I,
    "II": DOCS_CATEGORIA_II,
    "III": DOCS_CATEGORIA_III,
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def usuario_actual():
    return request.headers.get("X-Usuario-Email", "").strip().lower()


def obtener_usuario_id(cur, email):
    cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
    row = cur.fetchone()
    return row["id"] if row else None


# ---------- Estaticos y servicio ----------

@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:filename>", methods=["GET"])
def static_files(filename):
    """
    Sirve cualquier archivo estatico (css, js, imagenes, otras paginas html)
    que viva dentro de la carpeta 'static/'. Captura todo lo que no coincida
    con una ruta mas especifica definida mas abajo (login, expedientes, etc).
    """
    return send_from_directory("static", filename)


@app.route("/api", methods=["GET"])
def api_info():
    return jsonify({"servicio": "Permisos Ambientales - API", "version": "0.3", "estado": "activo"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ---------- Autenticacion ----------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"acceso": False, "mensaje": "Debe ingresar correo y contrasena."}), 401

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, password_hash, rol, nombre FROM usuarios WHERE email=%s",
                    (email,),
                )
                u = cur.fetchone()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"acceso": False, "mensaje": "No se pudo conectar con la base de datos."}), 500

    if u and check_password_hash(u["password_hash"], password):
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {u['nombre']}. Acceso concedido a sus expedientes.",
            "rol": u["rol"],
            "nombre": u["nombre"],
        }), 200

    return jsonify({"acceso": False, "mensaje": "Credenciales incorrectas. Verifique su correo y contrasena."}), 401


@app.route("/registro", methods=["POST"])
def registro():
    data = request.get_json(silent=True) or {}
    nombre = data.get("nombre", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    rol = data.get("rol", "consultor")

    if not nombre or not email or not password:
        return jsonify({"ok": False, "mensaje": "Todos los campos son obligatorios."}), 400
    if len(password) < 8:
        return jsonify({"ok": False, "mensaje": "La contrasena debe tener al menos 8 caracteres."}), 400
    if rol not in ("consultor", "promotor"):
        return jsonify({"ok": False, "mensaje": "Tipo de usuario invalido."}), 400

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
                if cur.fetchone():
                    return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409
                cur.execute(
                    "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
                    (nombre, email, generate_password_hash(password), rol),
                )
            conn.commit()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"ok": False, "mensaje": "No se pudo registrar el usuario."}), 500

    return jsonify({"ok": True, "mensaje": "Usuario registrado correctamente."}), 201


# ---------- Dashboard ----------

@app.route("/dashboard", methods=["GET"])
def dashboard():
    email = usuario_actual()
    if not email:
        return jsonify({"error": "No autenticado"}), 401

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u:
                    return jsonify({"error": "Usuario no encontrado"}), 404
                uid = u["id"]

                cur.execute("SELECT COUNT(*) AS n FROM expedientes WHERE usuario_id=%s", (uid,))
                activos = cur.fetchone()["n"]

                cur.execute("SELECT COUNT(*) AS n FROM expedientes WHERE usuario_id=%s AND estado='pendiente'", (uid,))
                pendientes = cur.fetchone()["n"]

                cur.execute(
                    """SELECT COUNT(*) AS n FROM alertas a
                       JOIN expedientes e ON e.id=a.expediente_id WHERE e.usuario_id=%s""",
                    (uid,),
                )
                alertas = cur.fetchone()["n"]

                cur.execute("SELECT COUNT(*) AS n FROM expedientes WHERE usuario_id=%s AND estado='aprobado'", (uid,))
                aprobados = cur.fetchone()["n"]

                cur.execute(
                    """SELECT codigo, proyecto, estado FROM expedientes
                       WHERE usuario_id=%s ORDER BY fecha_ingreso DESC LIMIT 5""",
                    (uid,),
                )
                recientes = cur.fetchall()

                cur.execute(
                    """SELECT a.descripcion, a.dias_restantes FROM alertas a
                       JOIN expedientes e ON e.id=a.expediente_id
                       WHERE e.usuario_id=%s ORDER BY a.dias_restantes ASC LIMIT 5""",
                    (uid,),
                )
                proximas = cur.fetchall()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"error": "Error de base de datos"}), 500

    return jsonify({
        "metricas": {"activos": activos, "pendientes": pendientes, "alertas": alertas, "aprobados": aprobados},
        "recientes": recientes,
        "alertas": proximas,
    })


# ---------- Expedientes ----------

@app.route("/expedientes", methods=["GET"])
def listar_expedientes():
    email = usuario_actual()
    if not email:
        return jsonify({"error": "No autenticado"}), 401

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT e.codigo, e.proyecto, e.promotor, e.categoria, e.estado, e.fecha_ingreso
                       FROM expedientes e JOIN usuarios u ON u.id=e.usuario_id
                       WHERE u.email=%s ORDER BY e.fecha_ingreso DESC""",
                    (email,),
                )
                filas = cur.fetchall()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"error": "Error de base de datos"}), 500

    for f in filas:
        if f["fecha_ingreso"]:
            f["fecha_ingreso"] = f["fecha_ingreso"].strftime("%d/%m/%Y")

    return jsonify({"expedientes": filas})


@app.route("/expedientes", methods=["POST"])
def crear_expediente():
    email = usuario_actual()
    if not email:
        return jsonify({"error": "No autenticado"}), 401

    data = request.get_json(silent=True) or {}
    proyecto = data.get("proyecto", "").strip()
    promotor = data.get("promotor", "").strip()
    categoria = data.get("categoria", "II")

    if not proyecto or not promotor:
        return jsonify({"ok": False, "mensaje": "Proyecto y promotor son obligatorios."}), 400
    if categoria not in DOCS_POR_CATEGORIA:
        return jsonify({"ok": False, "mensaje": "Categoria invalida."}), 400

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                uid = obtener_usuario_id(cur, email)
                if not uid:
                    return jsonify({"ok": False, "mensaje": "Usuario no encontrado."}), 404

                cur.execute("SELECT COUNT(*) AS n FROM expedientes")
                n = cur.fetchone()["n"] + 1
                codigo = f"SP-A8-2026-{n:03d}"

                cur.execute(
                    """INSERT INTO expedientes (codigo, proyecto, promotor, categoria, estado, fecha_ingreso, usuario_id)
                       VALUES (%s, %s, %s, %s, 'evaluacion', %s, %s)""",
                    (codigo, proyecto, promotor, categoria, date.today().isoformat(), uid),
                )
                exp_id = cur.lastrowid

                for carpeta in DOCS_POR_CATEGORIA[categoria]:
                    cur.execute(
                        "INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, 'pendiente')",
                        (exp_id, carpeta),
                    )
            conn.commit()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"ok": False, "mensaje": "Error al guardar."}), 500

    return jsonify({"ok": True, "codigo": codigo, "mensaje": "Expediente creado."}), 201


@app.route("/expedientes/<codigo>", methods=["GET"])
def detalle_expediente(codigo):
    email = usuario_actual()
    if not email:
        return jsonify({"error": "No autenticado"}), 401

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                uid = obtener_usuario_id(cur, email)
                if not uid:
                    return jsonify({"error": "Usuario no encontrado"}), 404

                cur.execute(
                    """SELECT id, codigo, proyecto, promotor, categoria, estado, fecha_ingreso
                       FROM expedientes WHERE codigo=%s AND usuario_id=%s""",
                    (codigo, uid),
                )
                exp = cur.fetchone()
                if not exp:
                    return jsonify({"error": "Expediente no encontrado"}), 404

                cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s", (exp["id"],))
                docs = cur.fetchall()

                cur.execute(
                    "SELECT motivo, fecha FROM aprobaciones WHERE expediente_id=%s ORDER BY fecha DESC LIMIT 1",
                    (exp["id"],),
                )
                aprob = cur.fetchone()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"error": "Error de base de datos"}), 500

    if exp["fecha_ingreso"]:
        exp["fecha_ingreso"] = exp["fecha_ingreso"].strftime("%d/%m/%Y")
    del exp["id"]

    if aprob and aprob["fecha"]:
        aprob["fecha"] = aprob["fecha"].strftime("%d/%m/%Y %H:%M")

    return jsonify({"expediente": exp, "documentos": docs, "aprobacion": aprob})


@app.route("/expedientes/<codigo>/aprobar", methods=["POST"])
def aprobar_expediente(codigo):
    email = usuario_actual()
    if not email:
        return jsonify({"ok": False, "mensaje": "No autenticado"}), 401

    data = request.get_json(silent=True) or {}
    motivo = data.get("motivo", "").strip()
    if not motivo:
        return jsonify({"ok": False, "mensaje": "El motivo es obligatorio."}), 400

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u:
                    return jsonify({"ok": False, "mensaje": "Usuario no encontrado."}), 404

                # Solo el rol "consultor" puede dar la aprobacion interna
                # (equivalente al "jefe de la consultora" en HU-10).
                if u["rol"] != "consultor":
                    return jsonify({"ok": False, "mensaje": "No tienes permiso para aprobar expedientes."}), 403

                # El expediente debe pertenecer al usuario que aprueba.
                cur.execute(
                    "SELECT id FROM expedientes WHERE codigo=%s AND usuario_id=%s",
                    (codigo, u["id"]),
                )
                exp = cur.fetchone()
                if not exp:
                    return jsonify({"ok": False, "mensaje": "Expediente no encontrado."}), 404

                cur.execute(
                    "INSERT INTO aprobaciones (expediente_id, motivo, aprobado_por) VALUES (%s, %s, %s)",
                    (exp["id"], motivo, u["id"]),
                )
                cur.execute("UPDATE expedientes SET estado='aprobado' WHERE id=%s", (exp["id"],))
            conn.commit()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"ok": False, "mensaje": "Error al aprobar."}), 500

    return jsonify({"ok": True, "mensaje": "Expediente aprobado."}), 200


# ---------- Consulta publica ----------

@app.route("/consulta/<codigo>", methods=["GET"])
def consulta_publica(codigo):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT codigo, proyecto, promotor, categoria, estado
                       FROM expedientes WHERE codigo=%s""",
                    (codigo,),
                )
                exp = cur.fetchone()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({"error": "Error de base de datos"}), 500

    if not exp:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify({"expediente": exp}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)