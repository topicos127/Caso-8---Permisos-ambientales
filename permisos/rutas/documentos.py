"""HU-01: subir, descargar y eliminar documentos; HU-06: ZIP del expediente."""
import io
import os
import uuid
import zipfile
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from ..bd import cargar_expediente, cursor, registrar_historial
from ..config import ACCION_ELIMINAR, ACCION_SUBIR, EXTENSIONES_PERMITIDAS, MAX_FILE_SIZE, UPLOADS_DIR, ZONA
from ..errores import ApiError
from ..reglas import es_contenido_valido, hoy
from ..seguridad import exigir_gestion, exigir_lectura, requiere_login
from ..utiles import borrar_archivo, ruta_segura

bp = Blueprint("documentos", __name__)


def validar_archivo():
    """Devuelve (archivo, nombre_seguro, tamano) o lanza ApiError 400."""
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
    return archivo, nombre_original, tamano


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

            archivo, nombre_original, tamano = validar_archivo()

            cur.execute("SELECT id, archivo_ruta FROM documentos WHERE expediente_id=%s AND carpeta=%s",
                        (exp["id"], carpeta))
            doc = cur.fetchone()
            if not doc:
                raise ApiError(404, "Documento no encontrado.")

            carpeta_path = os.path.join(UPLOADS_DIR, exp["codigo"])
            os.makedirs(carpeta_path, exist_ok=True)
            nombre_unico = f"{uuid.uuid4().hex[:8]}_{nombre_original}"
            guardado = os.path.join(carpeta_path, nombre_unico)
            archivo.save(guardado)

            cur.execute("""UPDATE documentos SET estado='recibido', archivo_nombre=%s, archivo_ruta=%s,
                           archivo_tamano=%s, fecha_subida=NOW() WHERE id=%s""",
                        (nombre_original, os.path.join(exp["codigo"], nombre_unico), tamano, doc["id"]))
            registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_SUBIR)
    except Exception:
        # Sprint 9: si la transaccion no se confirma, el archivo nuevo no debe
        # quedar huerfano en disco.
        if guardado and os.path.exists(guardado):
            try:
                os.remove(guardado)
            except OSError:
                pass
        raise

    # Al reemplazar, el archivo anterior ya no lo apunta nadie.
    borrar_archivo(doc["archivo_ruta"])
    return jsonify({"ok": True, "mensaje": "Subido.", "archivo_nombre": nombre_original,
                    "archivo_tamano": tamano}), 200


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/descargar", methods=["GET"])
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


@bp.route("/expedientes/<codigo>/documentos/<carpeta>/eliminar", methods=["DELETE", "POST"])
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
        registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_ELIMINAR)

    borrar_archivo(doc["archivo_ruta"])
    return jsonify({"ok": True, "mensaje": "Documento eliminado."}), 200


@bp.route("/expedientes/<codigo>/descargar-todo", methods=["GET"])
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
    # HU-06: nombre estandarizado con el codigo y la fecha de Panama.
    return send_file(memory_file, mimetype='application/zip', as_attachment=True,
                     download_name=f"{exp['codigo']}_{hoy().isoformat()}.zip")
