"""HU-14: historial del expediente, de solo lectura."""
from flask import Blueprint, g, jsonify, request

from ..bd import cargar_expediente, cursor
from ..config import ROLES_INTERNOS
from ..errores import ApiError, respuesta_error
from ..seguridad import condicion_empresa, exigir_lectura, requiere_login
from ..utiles import entero, formatear_fechas, paginacion

bp = Blueprint("historial", __name__)


@bp.route("/historial", methods=["GET"])
@bp.route("/expedientes/<codigo>/historial", methods=["GET"])
@requiere_login
def ver_historial(codigo=None):
    """Jefe: todo. Consultor: solo sus expedientes. Promotor: 403."""
    u = g.usuario
    if u["rol"] not in ROLES_INTERNOS:
        raise ApiError(403, "El historial solo lo ven el director de proyectos y los consultores.")

    codigo = codigo or request.args.get("codigo", "").strip() or None
    page = entero("page", 1, 1, 100000)
    per_page = entero("per_page", 50, 1, 200)

    empresa, params_empresa = condicion_empresa(u)  # solo el historial de su empresa
    condiciones, params = [empresa], list(params_empresa)
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

    formatear_fechas(filas, "fecha", "%Y-%m-%d %H:%M:%S")
    return jsonify({"historial": filas, "paginacion": paginacion(total, page, per_page)})


@bp.route("/historial", methods=["POST", "PUT", "PATCH", "DELETE"])
@bp.route("/historial/<path:_resto>", methods=["POST", "PUT", "PATCH", "DELETE"])
@bp.route("/expedientes/<codigo>/historial", methods=["POST", "PUT", "PATCH", "DELETE"])
@bp.route("/expedientes/<codigo>/historial/<path:_resto>", methods=["POST", "PUT", "PATCH", "DELETE"])
def historial_solo_lectura(codigo=None, _resto=None):
    # HU-14: nadie, ni el jefe, edita ni borra entradas.
    return respuesta_error(405, "El historial es de solo lectura.")
