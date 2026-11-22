"""Rutas sin sesion: salud, informacion de la API, consulta publica (HU-09)
y archivos del frontend."""
from flask import Blueprint, jsonify, send_from_directory

from ..bd import cursor
from ..errores import ApiError

bp = Blueprint("publico", __name__)


@bp.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")


@bp.route("/api", methods=["GET"])
def api_info():
    return jsonify({"servicio": "Permisos Ambientales - API", "version": "0.9", "estado": "activo"}), 200


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/consulta/<codigo>", methods=["GET"])
def consulta_publica(codigo):
    with cursor() as cur:
        cur.execute("SELECT codigo, proyecto, promotor, categoria, estado, acceso_publico "
                    "FROM expedientes WHERE codigo=%s", (codigo,))
        exp = cur.fetchone()
    if not exp:
        raise ApiError(404, "No encontrado")
    return jsonify({"expediente": exp}), 200


@bp.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)
