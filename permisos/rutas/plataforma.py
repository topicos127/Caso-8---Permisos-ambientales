"""Operacion de la plataforma: estado del servicio, registro de errores y respaldos.

/estado es publico y minimo (la pagina de estado lo consulta). Todo lo demas es solo
para el administrador de la plataforma.
"""
import os

from flask import Blueprint, jsonify, request, send_file

from .. import config, registro_errores, respaldos
from ..almacenamiento import AlmacenamientoError, almacen
from ..bd import _esquema, cursor
from ..errores import ApiError
from ..seguridad import requiere_admin

bp = Blueprint("plataforma", __name__)

VERSION = "1.0"


def _estado_base():
    try:
        with cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        base = True
    except Exception:
        base = False
    try:
        archivos = almacen().salud()
    except AlmacenamientoError:
        archivos = False
    return base, archivos


@bp.route("/estado", methods=["GET"])
def estado_publico():
    base, archivos = _estado_base()
    r = registro_errores.resumen()
    return jsonify({"servicio": "operativo" if base and archivos else "con problemas",
                    "base_de_datos": base, "archivos": archivos, "version": VERSION,
                    "activo_desde": r["activo_desde"]}), 200 if base else 503


@bp.route("/plataforma/estado", methods=["GET"])
@requiere_admin
def estado_detalle():
    base, archivos = _estado_base()
    ficha = respaldos.ultimo()
    totales = {}
    if base:
        with cursor() as cur:
            for clave, tabla in (("empresas", "organizaciones"), ("usuarios", "usuarios"),
                                 ("expedientes", "expedientes"), ("documentos", "documentos")):
                try:
                    cur.execute(f"SELECT COUNT(*) AS n FROM {tabla}")
                    totales[clave] = cur.fetchone()["n"]
                except Exception:
                    totales[clave] = None
    return jsonify({
        "base_de_datos": base, "archivos": archivos, "version": VERSION,
        "almacenamiento": config.ALMACENAMIENTO, "respaldo_automatico": config.RESPALDO_AUTOMATICO,
        "respaldo_hora": config.RESPALDO_HORA, "respaldos_conservar": config.RESPALDOS_CONSERVAR,
        "ultimo_respaldo": ficha, "totales": totales, "funciones": dict(_esquema),
        **registro_errores.resumen(),
    }), 200


@bp.route("/plataforma/errores", methods=["GET"])
@requiere_admin
def errores():
    return jsonify({"errores": registro_errores.ultimos(50)}), 200


# ---------- Respaldos ----------

@bp.route("/plataforma/respaldos", methods=["GET"])
@requiere_admin
def listar_respaldos():
    return jsonify({"respaldos": respaldos.listar(), "automatico": config.RESPALDO_AUTOMATICO,
                    "hora": config.RESPALDO_HORA, "conservar": config.RESPALDOS_CONSERVAR}), 200


@bp.route("/plataforma/respaldos", methods=["POST"])
@requiere_admin
def crear_respaldo():
    try:
        ficha = respaldos.crear()
    except (respaldos.RespaldoError, AlmacenamientoError, OSError) as e:
        raise ApiError(500, f"No se pudo crear el respaldo: {e}")
    return jsonify({"ok": True, "respaldo": ficha, "mensaje": "Respaldo creado."}), 201


@bp.route("/plataforma/respaldos/<nombre>", methods=["GET"])
@requiere_admin
def descargar_respaldo(nombre):
    ruta = respaldos.ruta_de(nombre)
    if not ruta:
        raise ApiError(404, "Respaldo no encontrado.")
    return send_file(ruta, as_attachment=True, download_name=os.path.basename(ruta), mimetype="application/zip")


@bp.route("/plataforma/respaldos/<nombre>/verificar", methods=["POST"])
@requiere_admin
def verificar_respaldo(nombre):
    try:
        manifiesto = respaldos.verificar(nombre)
    except respaldos.RespaldoError as e:
        raise ApiError(400, str(e))
    return jsonify({"ok": True, "manifiesto": manifiesto, "mensaje": "El respaldo está completo y sin alterar."}), 200


@bp.route("/plataforma/respaldos/<nombre>/restaurar", methods=["POST"])
@requiere_admin
def restaurar_respaldo(nombre):
    """Reemplaza TODOS los datos por los del respaldo. Pide escribir RESTAURAR para evitar un clic accidental."""
    data = request.get_json(silent=True) or {}
    if data.get("confirmar") != "RESTAURAR":
        raise ApiError(400, "Escriba RESTAURAR para confirmar: esta acción reemplaza todos los datos actuales.")
    try:
        resultado = respaldos.restaurar(nombre)
    except respaldos.RespaldoError as e:
        raise ApiError(400, str(e))
    return jsonify({"ok": True, **resultado,
                    "mensaje": "Datos restaurados. Antes se guardó un respaldo del estado anterior."}), 200


@bp.route("/plataforma/respaldos/<nombre>", methods=["DELETE"])
@requiere_admin
def eliminar_respaldo(nombre):
    if not respaldos.eliminar(nombre):
        raise ApiError(404, "Respaldo no encontrado.")
    return jsonify({"ok": True, "mensaje": "Respaldo eliminado."}), 200
