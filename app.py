"""
Sistema de Permisos Ambientales - API completa (Sprint 6 Final)
"""
import os
import uuid
import io
import zipfile
import ssl
from datetime import date, datetime
from werkzeug.utils import secure_filename
import pymysql
from fpdf import FPDF
from flask import Flask, request, jsonify, send_from_directory, send_file
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

# Si estamos en la nube (Aiven exige SSL), configuramos la conexión segura
if os.environ.get("DB_HOST") and "aivencloud" in os.environ.get("DB_HOST"):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    DB_CONFIG["ssl"] = ssl_context

UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/app/uploads")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
EXTENSIONES_PERMITIDAS = {".pdf", ".zip"}

os.makedirs(UPLOADS_DIR, exist_ok=True)


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def usuario_actual():
    return request.headers.get("X-Usuario-Email", "").strip().lower()


# ---------- Validación de Magic Bytes (Seguridad) ----------

def es_contenido_valido(file_stream):
    header = file_stream.read(4)
    file_stream.seek(0)
    return header.startswith(b'%PDF') or header.startswith(b'PK\x03\x04')


# ---------- Verificación de requisitos ----------

CATEGORIAS_DOCS = {
    "I":   ["Línea Base", "Plan de Manejo", "Anexos Legales"],
    "II":  ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía"],
    "III": ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía", "Evidencia Foro Público"],
}

PLAZOS_LEGALES = {"I": 20, "II": 40, "III": 80}


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


# ---------- Estáticos ----------

@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")

@app.route("/api", methods=["GET"])
def api_info():
    return jsonify({"servicio": "Permisos Ambientales - API", "version": "0.8", "estado": "activo"}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ---------- Autenticación ----------

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
                cur.execute("SELECT id, email, password_hash, rol, nombre FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
        finally:
            conn.close()
    except pymysql.MySQLError as e:
        print(f"ERROR DE CONEXION A MYSQL EN LOGIN: {e}", flush=True)
        return jsonify({"acceso": False, "mensaje": "No se pudo conectar con la base de datos."}), 500

    if u and check_password_hash(u["password_hash"], password):
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {u['nombre']}. Acceso concedido a sus expedientes.",
            "rol": u["rol"],
            "nombre": u["nombre"],
        }), 200

    return jsonify({"acceso": False, "mensaje": "Credenciales incorrectas."}), 401


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
    
    # Validación de seguridad de José
    if not any(c.isdigit() for c in password):
        return jsonify({"ok": False, "mensaje": "La contrasena debe incluir al menos un numero."}), 400
    if not any(c.isupper() for c in password):
        return jsonify({"ok": False, "mensaje": "La contrasena debe incluir al menos una letra mayuscula."}), 400

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
    except pymysql.MySQLError as e:
        print(f"ERROR DE CONEXION A MYSQL EN REGISTRO: {e}", flush=True)
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
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u:
                    return jsonify({"error": "Usuario no encontrado"}), 404
                uid = u["id"]
                es_promotor = (u["rol"] == "promotor")

                if es_promotor:
                    filtro = "promotor_email=%s"
                    param = email
                else:
                    filtro = "usuario_id=%s"
                    param = uid

                cur.execute(f"SELECT COUNT(*) AS n FROM expedientes WHERE {filtro}", (param,))
                activos = cur.fetchone()["n"]

                cur.execute(f"SELECT COUNT(*) AS n FROM expedientes WHERE {filtro} AND estado='pendiente'", (param,))
                pendientes = cur.fetchone()["n"]

                cur.execute(f"SELECT COUNT(*) AS n FROM expedientes WHERE {filtro} AND estado='aprobado'", (param,))
                aprobados = cur.fetchone()["n"]

                cur.execute(f"SELECT codigo, proyecto, estado FROM expedientes WHERE {filtro} ORDER BY fecha_ingreso DESC LIMIT 5", (param,))
                recientes = cur.fetchall()

                cur.execute(
                    f"""SELECT d.carpeta, d.fecha_subida, e.codigo 
                        FROM documentos d JOIN expedientes e ON e.id = d.expediente_id
                        WHERE e.{filtro} AND d.estado = 'recibido' AND d.fecha_subida IS NOT NULL""", (param,)
                )
                docs_recibidos = cur.fetchall()
                
                proximas = []
                hoy = date.today()
                for d in docs_recibidos:
                    fecha_sub = d["fecha_subida"]
                    if isinstance(fecha_sub, datetime): fecha_sub = fecha_sub.date()
                    elif isinstance(fecha_sub, str): fecha_sub = datetime.strptime(fecha_sub, "%Y-%m-%d").date()
                    dias_restantes = 365 - (hoy - fecha_sub).days
                    if dias_restantes < 30:
                        proximas.append({
                            "codigo": d["codigo"],
                            "descripcion": f"{d['carpeta']} vence en {dias_restantes} días",
                            "dias_restantes": dias_restantes
                        })
                proximas.sort(key=lambda x: x["dias_restantes"])
                alertas = len(proximas)
        finally:
            conn.close()
    except pymysql.MySQLError as e:
        print(f"ERROR EN DASHBOARD: {e}", flush=True)
        return jsonify({"error": f"Error de base de datos"}), 500

    return jsonify({
        "metricas": {"activos": activos, "pendientes": pendientes, "alertas": alertas, "aprobados": aprobados},
        "recientes": recientes, "alertas": proximas,
    })


# ---------- Expedientes ----------

@app.route("/expedientes", methods=["GET"])
def listar_expedientes():
    email = usuario_actual()
    if not email:
        return jsonify({"error": "No autenticado"}), 401

    # Paginación y búsqueda de José
    q = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u: return jsonify({"error": "Usuario no encontrado"}), 404

                if u["rol"] == "promotor":
                    filtro = "promotor_email=%s"
                    param = email
                else:
                    filtro = "usuario_id=%s"
                    param = u["id"]

                query = f"SELECT codigo, proyecto, promotor, categoria, estado, fecha_ingreso FROM expedientes WHERE {filtro}"
                params = [param]

                if q:
                    query += " AND (codigo LIKE %s OR proyecto LIKE %s OR promotor LIKE %s)"
                    params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

                # Contar total para paginación
                count_query = query.replace("SELECT codigo, proyecto, promotor, categoria, estado, fecha_ingreso", "SELECT COUNT(*) as total")
                cur.execute(count_query, params)
                total = cur.fetchone()["total"]

                query += " ORDER BY fecha_ingreso DESC LIMIT %s OFFSET %s"
                params.extend([per_page, offset])
                cur.execute(query, params)
                filas = cur.fetchall()
        finally:
            conn.close()
    except pymysql.MySQLError as e:
        print(f"ERROR AL LISTAR EXPEDIENTES: {e}", flush=True)
        return jsonify({"error": "Error de base de datos"}), 500

    for f in filas:
        if f["fecha_ingreso"]: f["fecha_ingreso"] = f["fecha_ingreso"].strftime("%Y-%m-%d")

    return jsonify({
        "expedientes": filas,
        "paginacion": {"total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page}
    })


@app.route("/expedientes", methods=["POST"])
def crear_expediente():
    email = usuario_actual()
    if not email: return jsonify({"error": "No autenticado"}), 401

    data = request.get_json(silent=True) or {}
    proyecto = data.get("proyecto", "").strip()
    promotor = data.get("promotor", "").strip()
    promotor_email = (data.get("promotor_email", "") or "").strip().lower() or None
    categoria = data.get("categoria", "II")

    if not proyecto or not promotor:
        return jsonify({"ok": False, "mensaje": "Proyecto y promotor son obligatorios."}), 400

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u: return jsonify({"ok": False, "mensaje": "Usuario no encontrado."}), 404
                
                cur.execute("SELECT COUNT(*) AS n FROM expedientes")
                n = cur.fetchone()["n"] + 1
                codigo = f"SP-A8-2026-{n:03d}"

                cur.execute(
                    """INSERT INTO expedientes (codigo, proyecto, promotor, promotor_email, categoria, estado, fecha_ingreso, usuario_id)
                       VALUES (%s, %s, %s, %s, %s, 'pendiente', %s, %s)""",
                    (codigo, proyecto, promotor, promotor_email, categoria, date.today().isoformat(), u["id"]),
                )
                exp_id = cur.lastrowid

                for carpeta in CATEGORIAS_DOCS.get(categoria, CATEGORIAS_DOCS["II"]):
                    cur.execute("INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, 'pendiente')", (exp_id, carpeta))
            conn.commit()
        finally:
            conn.close()
    except pymysql.MySQLError as e:
        print(f"ERROR AL CREAR EXPEDIENTE: {e}", flush=True)
        return jsonify({"ok": False, "mensaje": "Error al guardar."}), 500

    return jsonify({"ok": True, "codigo": codigo, "mensaje": "Expediente creado."}), 201


@app.route("/expedientes/<codigo>", methods=["GET"])
def detalle_expediente(codigo):
    email = usuario_actual()
    if not email: return jsonify({"error": "No autenticado"}), 401

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u: return jsonify({"error": "Usuario no encontrado"}), 404

                cur.execute("""SELECT id, codigo, proyecto, promotor, promotor_email, categoria, estado, fecha_ingreso, usuario_id
                               FROM expedientes WHERE codigo=%s""", (codigo,))
                exp = cur.fetchone()
                if not exp: return jsonify({"error": "Expediente no encontrado"}), 404

                permitido = (u["rol"] == "promotor" and exp["promotor_email"] == email) or (u["rol"] != "promotor" and exp["usuario_id"] == u["id"])
                if not permitido: return jsonify({"error": "Sin acceso a este expediente"}), 403

                cur.execute("SELECT id, carpeta, estado, archivo_nombre, archivo_tamano, fecha_subida FROM documentos WHERE expediente_id=%s ORDER BY id", (exp["id"],))
                docs = cur.fetchall()

                cur.execute("SELECT motivo, fecha FROM aprobaciones WHERE expediente_id=%s ORDER BY fecha DESC LIMIT 1", (exp["id"],))
                aprob = cur.fetchone()
        finally:
            conn.close()
    except pymysql.MySQLError as e:
        print(f"ERROR EN DETALLE: {e}", flush=True)
        return jsonify({"error": "Error de base de datos"}), 500

    if exp["fecha_ingreso"]: exp["fecha_ingreso"] = exp["fecha_ingreso"].strftime("%d/%m/%Y")
    del exp["id"]; del exp["usuario_id"]; del exp["promotor_email"]

    for d in docs:
        if d["fecha_subida"]: d["fecha_subida"] = d["fecha_subida"].strftime("%d/%m/%Y %H:%M")
    if aprob and aprob["fecha"]: aprob["fecha"] = aprob["fecha"].strftime("%d/%m/%Y %H:%M")

    return jsonify({"expediente": exp, "documentos": docs, "aprobacion": aprob, "verificacion": calcular_verificacion(exp["categoria"], docs)})


@app.route("/expedientes/<codigo>/aprobaciones", methods=["GET"])
def listar_aprobaciones(codigo):
    email = usuario_actual()
    if not email: return jsonify({"error": "No autenticado"}), 401
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, usuario_id, promotor_email, categoria, estado FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if not exp: return jsonify({"error": "Expediente no encontrado"}), 404
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                permitido = (u["rol"] == "promotor" and exp["promotor_email"] == email) or (u["rol"] != "promotor" and exp["usuario_id"] == u["id"])
                if not permitido: return jsonify({"error": "Sin acceso"}), 403
                cur.execute("""SELECT a.id, a.motivo, a.fecha, u.nombre AS aprobado_por_nombre FROM aprobaciones a
                               LEFT JOIN usuarios u ON u.id = a.aprobado_por WHERE a.expediente_id = %s ORDER BY a.fecha DESC""", (exp["id"],))
                aprobaciones = cur.fetchall()
        finally:
            conn.close()
    except pymysql.MySQLError: return jsonify({"error": "Error de base de datos"}), 500

    for a in aprobaciones:
        if a["fecha"]: a["fecha"] = a["fecha"].strftime("%d/%m/%Y %H:%M")
    return jsonify({"expediente_codigo": codigo, "estado": exp["estado"], "aprobaciones": aprobaciones})


# ---------- Documentos ----------

@app.route("/expedientes/<codigo>/documentos/<carpeta>/subir", methods=["POST"])
def subir_documento(codigo, carpeta):
    email = usuario_actual()
    if not email: return jsonify({"ok": False, "mensaje": "No autenticado"}), 401
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u or u["rol"] == "promotor": return jsonify({"ok": False, "mensaje": "No autorizado."}), 403
                cur.execute("SELECT estado FROM expedientes WHERE codigo=%s", (codigo,))
                exp_check = cur.fetchone()
                if exp_check and exp_check["estado"] != "pendiente": return jsonify({"ok": False, "mensaje": "Expediente no editable."}), 403
                
                if "archivo" not in request.files: return jsonify({"ok": False, "mensaje": "No se recibio archivo."}), 400
                archivo = request.files["archivo"]
                nombre_original = secure_filename(archivo.filename)
                ext = os.path.splitext(nombre_original)[1].lower()
                
                if ext not in EXTENSIONES_PERMITIDAS: return jsonify({"ok": False, "mensaje": "Solo PDF y ZIP."}), 400
                if not es_contenido_valido(archivo.stream): return jsonify({"ok": False, "mensaje": "Contenido invalido."}), 400

                archivo.seek(0, os.SEEK_END)
                tamano = archivo.tell()
                archivo.seek(0)
                if tamano > MAX_FILE_SIZE: return jsonify({"ok": False, "mensaje": "Max 20 MB."}), 400

                cur.execute("""SELECT d.id FROM documentos d JOIN expedientes e ON e.id=d.expediente_id
                               WHERE e.codigo=%s AND d.carpeta=%s""", (codigo, carpeta))
                doc = cur.fetchone()
                if not doc: return jsonify({"ok": False, "mensaje": "Documento no encontrado."}), 404

                carpeta_path = os.path.join(UPLOADS_DIR, codigo)
                os.makedirs(carpeta_path, exist_ok=True)
                nombre_unico = f"{uuid.uuid4().hex[:8]}_{nombre_original}"
                archivo.save(os.path.join(carpeta_path, nombre_unico))

                cur.execute("""UPDATE documentos SET estado='recibido', archivo_nombre=%s, archivo_ruta=%s,
                               archivo_tamano=%s, fecha_subida=NOW() WHERE id=%s""",
                            (nombre_original, os.path.join(codigo, nombre_unico), tamano, doc["id"]))
            conn.commit()
        finally: conn.close()
    except Exception as e:
        print(f"ERROR AL SUBIR: {e}", flush=True)
        return jsonify({"ok": False, "mensaje": "Error al guardar."}), 500

    return jsonify({"ok": True, "mensaje": "Subido.", "archivo_nombre": nombre_original, "archivo_tamano": tamano}), 200


@app.route("/expedientes/<codigo>/documentos/<carpeta>/descargar", methods=["GET"])
def descargar_documento(codigo, carpeta):
    email = usuario_actual()
    if not email: return jsonify({"error": "No autenticado"}), 401
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                cur.execute("SELECT id, usuario_id, promotor_email FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if not exp: return jsonify({"error": "Expediente no encontrado"}), 404
                permitido = (u["rol"] == "promotor" and exp["promotor_email"] == email) or (u["rol"] != "promotor" and exp["usuario_id"] == u["id"])
                if not permitido: return jsonify({"error": "Sin acceso"}), 403

                cur.execute("SELECT archivo_nombre, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s", (exp["id"], carpeta))
                doc = cur.fetchone()
        finally: conn.close()
    except pymysql.MySQLError: return jsonify({"error": "Error BD"}), 500

    if not doc or not doc["archivo_ruta"]: return jsonify({"error": "No disponible"}), 404
    ruta = doc["archivo_ruta"]
    if ".." in ruta or ruta.startswith("/"): return jsonify({"error": "Ruta invalida"}), 400
    carpeta_fisica = os.path.join(UPLOADS_DIR, os.path.dirname(ruta))
    nombre_fisico = os.path.basename(ruta)
    if not os.path.exists(os.path.join(carpeta_fisica, nombre_fisico)): return jsonify({"error": "No en disco"}), 404

    return send_from_directory(carpeta_fisica, nombre_fisico, as_attachment=True, download_name=doc["archivo_nombre"])


@app.route("/expedientes/<codigo>/documentos/<carpeta>/eliminar", methods=["DELETE", "POST"])
def eliminar_documento(codigo, carpeta):
    email = usuario_actual()
    if not email: return jsonify({"ok": False, "mensaje": "No autenticado"}), 401
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u or u["rol"] == "promotor": return jsonify({"ok": False, "mensaje": "No autorizado."}), 403

                cur.execute("SELECT id, estado FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if exp["estado"] != "pendiente": return jsonify({"ok": False, "mensaje": "Expediente no editable."}), 403

                cur.execute("SELECT id, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s", (exp["id"], carpeta))
                doc = cur.fetchone()
                if not doc or not doc["archivo_ruta"]: return jsonify({"ok": False, "mensaje": "No tiene archivo."}), 400

                ruta = doc["archivo_ruta"]
                if ".." not in ruta and not ruta.startswith("/"):
                    ruta_fisica = os.path.join(UPLOADS_DIR, ruta)
                    if os.path.exists(ruta_fisica):
                        try: os.remove(ruta_fisica)
                        except OSError: pass

                cur.execute("""UPDATE documentos SET estado='pendiente', archivo_nombre=NULL, archivo_ruta=NULL,
                               archivo_tamano=NULL, fecha_subida=NULL WHERE id=%s""", (doc["id"],))
            conn.commit()
        finally: conn.close()
    except Exception as e: return jsonify({"ok": False, "mensaje": "Error."}), 500
    return jsonify({"ok": True, "mensaje": "Documento eliminado."}), 200


@app.route("/expedientes/<codigo>/descargar-todo", methods=["GET"])
def descargar_zip_expediente(codigo):
    memory_file = io.BytesIO()
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, proyecto, promotor, categoria FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if not exp: return jsonify({"error": "No encontrado"}), 404
                cur.execute("SELECT carpeta, archivo_nombre, archivo_ruta FROM documentos WHERE expediente_id=%s AND estado='recibido'", (exp["id"],))
                docs = cur.fetchall()
        finally: conn.close()
    except Exception: return jsonify({"error": "Error BD"}), 500

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        indice_txt = f"EXPEDIENTE: {codigo}\nProyecto: {exp['proyecto']}\nPromotor: {exp['promotor']}\nCategoría: {exp['categoria']}\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nArchivos:\n"
        for d in docs:
            indice_txt += f"- [{d['carpeta']}] {d['archivo_nombre']}\n"
            if d['archivo_ruta']:
                ruta_completa = os.path.join(UPLOADS_DIR, d['archivo_ruta'])
                if os.path.exists(ruta_completa):
                    arcname = f"{d['carpeta'].replace(' ', '_')}/{d['archivo_nombre']}"
                    zf.write(ruta_completa, arcname=arcname)
        zf.writestr('Indice_Expediente.txt', indice_txt)

    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f'{codigo}_completo.zip')


# ---------- PDF (José) ----------

@app.route("/expedientes/<codigo>/pdf", methods=["GET"])
def generar_pdf_expediente(codigo):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT codigo, proyecto, promotor, categoria, estado, fecha_ingreso FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if not exp: return jsonify({"error": "No encontrado"}), 404
                cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=(SELECT id FROM expedientes WHERE codigo=%s)", (codigo,))
                docs = cur.fetchall()
        finally: conn.close()
    except Exception: return jsonify({"error": "Error BD"}), 500

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Resumen Ejecutivo del Expediente", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Codigo: {exp['codigo']}", ln=True)
    pdf.cell(0, 10, f"Proyecto: {exp['proyecto']}", ln=True)
    pdf.cell(0, 10, f"Promotor: {exp['promotor']}", ln=True)
    pdf.cell(0, 10, f"Categoria: {exp['categoria']}", ln=True)
    pdf.cell(0, 10, f"Estado: {exp['estado']}", ln=True)
    pdf.cell(0, 10, f"Fecha de Ingreso: {exp['fecha_ingreso']}", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Documentos del expediente:", ln=True)
    pdf.set_font("Arial", '', 12)
    
    for d in docs:
        estado_doc = "Recibido" if d['estado'] == 'recibido' else "Pendiente"
        pdf.cell(0, 10, f"- {d['carpeta']}: {estado_doc}", ln=True)

    pdf_bytes = bytes(pdf.output())
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=f'{codigo}-resumen.pdf')


# ---------- Plazos y Acciones ----------

@app.route("/expedientes/<codigo>/alertas", methods=["GET"])
def obtener_alertas(codigo):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT codigo, categoria, fecha_ingreso FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if not exp: return jsonify({"error": "No encontrado"}), 404
                
                cat = exp.get("categoria") or "II"
                limite = PLAZOS_LEGALES.get(cat, 40)
                fecha_ingreso = exp.get("fecha_ingreso")
                if isinstance(fecha_ingreso, str): fecha_ingreso = datetime.strptime(fecha_ingreso, "%Y-%m-%d").date()
                elif isinstance(fecha_ingreso, datetime): fecha_ingreso = fecha_ingreso.date()
                
                transcurridos = (date.today() - fecha_ingreso).days
                restantes = limite - transcurridos
                
                if restantes < 0: estado_alerta = f"VENCIDO (Superó por {abs(restantes)} días)"
                elif restantes <= 5: estado_alerta = f"ALERTA CRÍTICA (Quedan {restantes} días)"
                else: estado_alerta = f"Dentro del plazo legal ({restantes} días de {limite})"

                return jsonify({"expediente": codigo, "categoria": cat, "dias_transcurridos": transcurridos, "dias_restantes_legales": restantes, "alerta_vencimiento": estado_alerta}), 200
        finally: conn.close()
    except Exception as e: return jsonify({"error": str(e)}), 500


@app.route("/expedientes/<codigo>/aprobar", methods=["POST"])
def aprobar_expediente(codigo):
    email = usuario_actual()
    if not email: return jsonify({"ok": False, "mensaje": "No autenticado"}), 401
    data = request.get_json(silent=True) or {}
    motivo = data.get("motivo", "").strip()
    if not motivo: return jsonify({"ok": False, "mensaje": "Motivo obligatorio."}), 400

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u or u["rol"] == "promotor": return jsonify({"ok": False, "mensaje": "No autorizado."}), 403

                cur.execute("SELECT id, categoria, estado FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if exp["estado"] != "pendiente": return jsonify({"ok": False, "mensaje": "Estado invalido."}), 400

                cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s", (exp["id"],))
                verif = calcular_verificacion(exp["categoria"], cur.fetchall())
                if not verif["puede_someter"]: return jsonify({"ok": False, "mensaje": f"Faltan: {', '.join(verif['faltantes'])}"}), 400

                cur.execute("INSERT INTO aprobaciones (expediente_id, motivo, aprobado_por) VALUES (%s, %s, %s)", (exp["id"], motivo, u["id"]))
                cur.execute("UPDATE expedientes SET estado='aprobado_interno' WHERE id=%s", (exp["id"],))
            conn.commit()
        finally: conn.close()
    except Exception: return jsonify({"ok": False, "mensaje": "Error al aprobar."}), 500
    return jsonify({"ok": True, "mensaje": "Aprobado internamente."}), 200


@app.route("/expedientes/<codigo>/someter", methods=["POST"])
def someter_expediente(codigo):
    email = usuario_actual()
    if not email: return jsonify({"ok": False, "mensaje": "No autenticado"}), 401
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u or u["rol"] == "promotor": return jsonify({"ok": False, "mensaje": "No autorizado."}), 403

                cur.execute("SELECT id, estado FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if exp["estado"] != "aprobado_interno": return jsonify({"ok": False, "mensaje": "Debe aprobarse internamente primero."}), 400

                cur.execute("UPDATE expedientes SET estado='evaluacion' WHERE id=%s", (exp["id"],))
            conn.commit()
        finally: conn.close()
    except Exception: return jsonify({"ok": False, "mensaje": "Error al someter."}), 500
    return jsonify({"ok": True, "mensaje": "Sometido a MiAmbiente."}), 200


@app.route("/expedientes/<codigo>/aprobar-miambiente", methods=["POST"])
def aprobar_miambiente(codigo):
    email = usuario_actual()
    if not email: return jsonify({"ok": False, "mensaje": "No autenticado"}), 401
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, rol FROM usuarios WHERE email=%s", (email,))
                u = cur.fetchone()
                if not u or u["rol"] == "promotor": return jsonify({"ok": False, "mensaje": "No autorizado."}), 403
                cur.execute("SELECT id, estado FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
                if exp["estado"] != "evaluacion": return jsonify({"ok": False, "mensaje": "Debe estar en evaluacion."}), 400
                cur.execute("UPDATE expedientes SET estado='aprobado' WHERE id=%s", (exp["id"],))
            conn.commit()
        finally: conn.close()
    except Exception: return jsonify({"ok": False, "mensaje": "Error."}), 500
    return jsonify({"ok": True, "mensaje": "Aprobado por MiAmbiente."}), 200


@app.route("/consulta/<codigo>", methods=["GET"])
def consulta_publica(codigo):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT codigo, proyecto, promotor, categoria, estado, acceso_publico FROM expedientes WHERE codigo=%s", (codigo,))
                exp = cur.fetchone()
        finally: conn.close()
    except Exception: return jsonify({"error": "Error BD"}), 500
    if not exp: return jsonify({"error": "No encontrado"}), 404
    return jsonify({"expediente": exp}), 200


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)