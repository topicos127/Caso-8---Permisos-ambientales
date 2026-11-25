"""Rutas sin sesion: salud, informacion de la API, consulta publica (HU-09)
y archivos del frontend."""
from flask import Blueprint, jsonify, send_from_directory

from ..bd import col_org, cursor
from ..config import ESTADO_PUBLICO
from ..empresas import datos_empresa
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
    """HU-09. Solo datos publicos y solo si la consultora habilito el acceso
    publico: si no, el backend no entrega nada del expediente (Ley 81 de 2019).
    Como el resumen PDF se arma con estos datos, sin acceso tampoco hay PDF."""
    with cursor() as cur:
        cur.execute(f"""SELECT e.codigo, e.proyecto, e.promotor, e.categoria, e.estado, e.acceso_publico,
                              u.nombre AS consultor, {col_org('e')}
                       FROM expedientes e LEFT JOIN usuarios u ON u.id = e.usuario_id
                       WHERE e.codigo=%s""", (codigo,))
        exp = cur.fetchone()
        if not exp:
            raise ApiError(404, "No encontrado")
        if not exp["acceso_publico"]:
            raise ApiError(403, "Este proyecto no está disponible para consulta pública.")
        empresa = datos_empresa(cur, exp.pop("organizacion_id", None))
    exp["acceso_publico"] = True
    exp["estado_publico"] = ESTADO_PUBLICO.get(exp["estado"], exp["estado"])
    # Solo la marca (nombre, color, logo): nada interno de la empresa.
    marca = {k: empresa[k] for k in ("nombre", "color", "logo")} if empresa else None
    return jsonify({"expediente": exp, "empresa": marca}), 200


@bp.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)
