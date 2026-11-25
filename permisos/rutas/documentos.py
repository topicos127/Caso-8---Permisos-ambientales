"""HU-01: subir y descargar documentos, con versiones y codigo de trazabilidad;
HU-06: ZIP del expediente.

Sprint 9: un documento nunca se elimina. Cada subida crea una version nueva con
un codigo de trazabilidad unico y la huella SHA-256 del archivo; las versiones
anteriores se conservan (en la base y en disco) y se pueden consultar y descargar.
"""
import hashlib
import io
import os
import uuid
import zipfile
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from ..bd import SQL_ULTIMA_VERSION, _esquema, cargar_expediente, cursor, registrar_historial
from ..config import (ACCION_SUBIR, ACCION_VERSION, CARPETA_CARTOGRAFIA, EXTENSIONES_PERMITIDAS, MAX_FILE_SIZE,
                      UPLOADS_DIR, ZONA)
from ..errores import ApiError
from ..inspeccion import problema_archivo, problema_cartografia
from ..reglas import ahora, hoy
from ..seguridad import exigir_gestion, exigir_lectura, requiere_login
from ..utiles import formatear_fechas, ruta_segura

bp = Blueprint("documentos", __name__)

def fecha_vencimiento_enviada():
    """HU-05 (Sprint 10): fecha de vencimiento opcional del documento (campo del
    formulario fecha_vencimiento, AAAA-MM-DD). Debe ser posterior a hoy."""
    valor = (request.form.get("fecha_vencimiento") or "").strip()
    if not valor:
        return None
    try:
        fecha = datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(400, "La fecha de vencimiento debe tener el formato AAAA-MM-DD.")
    if fecha <= hoy():
        raise ApiError(400, "La fecha de vencimiento debe ser posterior a hoy: el documento ya estaría vencido.")
    return fecha


def validar_archivo(carpeta=None):
    """Devuelve (nombre_seguro, contenido) o lanza ApiError 400."""
    if "archivo" not in request.files:
        raise ApiError(400, "No se recibio archivo.")
    archivo = request.files["archivo"]
    nombre_original = secure_filename(archivo.filename or "")
    ext = os.path.splitext(nombre_original)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise ApiError(400, "Solo PDF y ZIP.")
    contenido = archivo.stream.read(MAX_FILE_SIZE + 1)
    if len(contenido) > MAX_FILE_SIZE:
        raise ApiError(400, "Max 20 MB.")
    problema = problema_archivo(ext, contenido)  # HU-01: revision de seguridad
    if not problema and carpeta == CARPETA_CARTOGRAFIA:
        problema = problema_cartografia(ext, contenido)  # HU-01 (Sprint 10): shapefile completo
    if problema:
        raise ApiError(400, problema)
    return nombre_original, contenido


def codigo_trazabilidad(codigo_expediente, documento_id, version, sha256):
    """Unico por (documento, version); el final es el inicio de la huella del
    archivo, asi el codigo tambien sirve para comprobar que no cambio."""
    return f"{codigo_expediente}-D{documento_id}-V{version}-{sha256[:8].upper()}"


def _huella_en_disco(ruta):
    fisica = ruta_segura(ruta) if ruta else None
    if not fisica or not os.path.exists(fisica):
        return None
    h = hashlib.sha256()
    with open(fisica, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _insertar_version(cur, exp, documento_id, version, nombre, ruta, tamano, sha256, usuario_id, fecha):
    codigo = codigo_trazabilidad(exp["codigo"], documento_id, version, sha256 or "0" * 8)
    cur.execute("""INSERT INTO documento_versiones
                   (documento_id, version, codigo_trazabilidad, archivo_nombre, archivo_ruta, archivo_tamano,
                    sha256, subido_por, fecha_subida)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (documento_id, version, codigo, nombre, ruta, tamano, sha256, usuario_id, fecha))
    return codigo


def _documento(cur, exp, carpeta, bloquear=False):
    cur.execute("SELECT id, archivo_nombre, archivo_ruta, archivo_tamano, fecha_subida FROM documentos "
                "WHERE expediente_id=%s AND carpeta=%s" + (" FOR UPDATE" if bloquear else ""),
                (exp["id"], carpeta))
    doc = cur.fetchone()
    if not doc:
        raise ApiError(404, "Documento no encontrado.")
    return doc


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/subir", methods=["POST"])
@requiere_login
def subir_documento(codigo, carpeta):
    guardado = None  # archivo nuevo en disco, para borrarlo si la base falla
    try:
        with cursor() as cur:
            exp = cargar_expediente(cur, codigo)
            exigir_gestion(g.usuario, exp)
            if exp["estado"] != "pendiente":
                raise ApiError(403, "Expediente no editable.")

            nombre_original, contenido = validar_archivo(carpeta)
            vence = fecha_vencimiento_enviada()
            doc = _documento(cur, exp, carpeta, bloquear=True)

            cur.execute("SELECT COALESCE(MAX(version), 0) AS ultima FROM documento_versiones WHERE documento_id=%s",
                        (doc["id"],))
            ultima = int(cur.fetchone()["ultima"])
            if ultima == 0 and doc["archivo_ruta"]:
                # Archivo subido antes de que existieran las versiones: queda como la 1.
                _insertar_version(cur, exp, doc["id"], 1, doc["archivo_nombre"], doc["archivo_ruta"],
                                  doc["archivo_tamano"], _huella_en_disco(doc["archivo_ruta"]), None,
                                  doc["fecha_subida"] or ahora())
                ultima = 1
            version = ultima + 1
            sha256 = hashlib.sha256(contenido).hexdigest()

            carpeta_path = os.path.join(UPLOADS_DIR, exp["codigo"])
            os.makedirs(carpeta_path, exist_ok=True)
            nombre_unico = f"{uuid.uuid4().hex[:8]}_v{version}_{nombre_original}"
            guardado = os.path.join(carpeta_path, nombre_unico)
            with open(guardado, "wb") as f:
                f.write(contenido)

            ruta = os.path.join(exp["codigo"], nombre_unico)
            momento = ahora()
            codigo_doc = _insertar_version(cur, exp, doc["id"], version, nombre_original, ruta, len(contenido),
                                           sha256, g.usuario["id"], momento)
            cur.execute("""UPDATE documentos SET estado='recibido', archivo_nombre=%s, archivo_ruta=%s,
                           archivo_tamano=%s, fecha_subida=%s WHERE id=%s""",
                        (nombre_original, ruta, len(contenido), momento, doc["id"]))
            if _esquema["vencimiento"]:
                # La fecha es del archivo: una version nueva sin fecha vuelve a la regla del ano.
                cur.execute("UPDATE documentos SET fecha_vencimiento=%s WHERE id=%s",
                            (vence.isoformat() if vence else None, doc["id"]))
            registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_SUBIR if version == 1 else ACCION_VERSION)
    except Exception:
        # Si la transaccion no se confirma, el archivo nuevo no debe quedar huerfano en disco.
        if guardado and os.path.exists(guardado):
            try:
                os.remove(guardado)
            except OSError:
                pass
        raise

    # Las versiones anteriores se conservan: no se borra ningun archivo.
    return jsonify({"ok": True, "mensaje": f"Subido como versión {version}.", "archivo_nombre": nombre_original,
                    "archivo_tamano": len(contenido), "version": version, "codigo_trazabilidad": codigo_doc,
                    "sha256": sha256, "fecha_vencimiento": vence.isoformat() if vence else None}), 200


def _enviar(ruta, nombre):
    fisica = ruta_segura(ruta) if ruta else None
    if not ruta:
        raise ApiError(404, "No disponible")
    if not fisica:
        raise ApiError(400, "Ruta invalida")
    if not os.path.exists(fisica):
        raise ApiError(404, "No en disco")
    return send_from_directory(os.path.dirname(fisica), os.path.basename(fisica),
                               as_attachment=True, download_name=nombre)


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/descargar", methods=["GET"])
@requiere_login
def descargar_documento(codigo, carpeta):
    """La version vigente (la ultima)."""
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT archivo_nombre, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s",
                    (exp["id"], carpeta))
        doc = cur.fetchone()
    if not doc:
        raise ApiError(404, "No disponible")
    return _enviar(doc["archivo_ruta"], doc["archivo_nombre"])


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/versiones", methods=["GET"])
@requiere_login
def versiones_documento(codigo, carpeta):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        doc = _documento(cur, exp, carpeta)
        cur.execute("""SELECT v.version, v.codigo_trazabilidad, v.archivo_nombre, v.archivo_tamano, v.sha256,
                              v.fecha_subida, u.nombre AS subido_por
                       FROM documento_versiones v LEFT JOIN usuarios u ON u.id = v.subido_por
                       WHERE v.documento_id=%s ORDER BY v.version DESC""", (doc["id"],))
        versiones = cur.fetchall()
    formatear_fechas(versiones, "fecha_subida", "%d/%m/%Y %H:%M")
    return jsonify({"carpeta": carpeta, "versiones": versiones}), 200


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/versiones/<int:version>/descargar", methods=["GET"])
@requiere_login
def descargar_version(codigo, carpeta, version):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        doc = _documento(cur, exp, carpeta)
        cur.execute("SELECT archivo_nombre, archivo_ruta FROM documento_versiones "
                    "WHERE documento_id=%s AND version=%s", (doc["id"], version))
        v = cur.fetchone()
    if not v:
        raise ApiError(404, "Versión no encontrada.")
    return _enviar(v["archivo_ruta"], v["archivo_nombre"])


@bp.route("/documentos/trazabilidad/<codigo>", methods=["GET"])
@requiere_login
def buscar_por_trazabilidad(codigo):
    """Dado un codigo de trazabilidad, a que expediente, documento y version pertenece."""
    with cursor() as cur:
        cur.execute("""SELECT v.version, v.codigo_trazabilidad, v.archivo_nombre, v.archivo_tamano, v.sha256,
                              v.fecha_subida, d.carpeta, e.codigo AS expediente
                       FROM documento_versiones v JOIN documentos d ON d.id = v.documento_id
                       JOIN expedientes e ON e.id = d.expediente_id
                       WHERE v.codigo_trazabilidad=%s""", (codigo.strip().upper(),))
        v = cur.fetchone()
        if not v:
            raise ApiError(404, "Código de trazabilidad no encontrado.")
        exigir_lectura(g.usuario, cargar_expediente(cur, v["expediente"]))
    formatear_fechas([v], "fecha_subida", "%d/%m/%Y %H:%M")
    return jsonify({"version": v}), 200


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/eliminar", methods=["DELETE", "POST"])
@requiere_login
def eliminar_documento(codigo, carpeta):
    # HU-01 (Sprint 9): los documentos no se eliminan; se corrigen con una version nueva.
    raise ApiError(405, "Los documentos no se eliminan: suba una nueva versión. "
                        "Las versiones anteriores se conservan para la trazabilidad.")


@bp.route("/expedientes/<codigo>/descargar-todo", methods=["GET"])
@requiere_login
def descargar_zip_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute(f"SELECT d.carpeta, d.archivo_nombre, d.archivo_ruta, {SQL_ULTIMA_VERSION} FROM documentos d "
                    "WHERE d.expediente_id=%s AND d.estado='recibido'", (exp["id"],))
        docs = cur.fetchall()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        indice_txt = (f"EXPEDIENTE: {exp['codigo']}\nProyecto: {exp['proyecto']}\nPromotor: {exp['promotor']}\n"
                      f"Categoría: {exp['categoria']}\nFecha: {datetime.now(ZONA).strftime('%Y-%m-%d %H:%M:%S')}"
                      f"\n\nArchivos (versión vigente):\n")
        for d in docs:
            traza = f" · v{d['version']} · {d['codigo_trazabilidad']}" if d.get("codigo_trazabilidad") else ""
            indice_txt += f"- [{d['carpeta']}] {d['archivo_nombre']}{traza}\n"
            fisica = ruta_segura(d["archivo_ruta"]) if d["archivo_ruta"] else None
            if fisica and os.path.exists(fisica):
                zf.write(fisica, arcname=f"{d['carpeta'].replace(' ', '_')}/{d['archivo_nombre']}")
        zf.writestr('Indice_Expediente.txt', indice_txt)

    memory_file.seek(0)
    # HU-06: nombre estandarizado con el codigo y la fecha de Panama.
    return send_file(memory_file, mimetype='application/zip', as_attachment=True,
                     download_name=f"{exp['codigo']}_{hoy().isoformat()}.zip")
