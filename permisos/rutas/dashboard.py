"""Panel con metricas, expedientes recientes y documentos por vencer (HU-05)."""
from flask import Blueprint, g, jsonify

from ..bd import cursor
from ..reglas import como_fecha, hoy
from ..seguridad import filtro_de, requiere_login

bp = Blueprint("dashboard", __name__)

VIGENCIA_DOCUMENTO_DIAS = 365  # supuesto actual: todo documento vence al ano
AVISO_VENCIMIENTO_DIAS = 30


@bp.route("/dashboard", methods=["GET"])
@requiere_login
def dashboard():
    filtro, params = filtro_de(g.usuario)
    with cursor() as cur:
        cur.execute(f"""SELECT COUNT(*) AS activos,
                               COALESCE(SUM(e.estado='pendiente'), 0) AS pendientes,
                               COALESCE(SUM(e.estado='aprobado'), 0) AS aprobados
                        FROM expedientes e WHERE {filtro}""", params)
        conteos = cur.fetchone()
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
        dias_restantes = VIGENCIA_DOCUMENTO_DIAS - (dia - como_fecha(d["fecha_subida"])).days
        if dias_restantes < AVISO_VENCIMIENTO_DIAS:
            proximas.append({
                "codigo": d["codigo"],
                "descripcion": f"{d['carpeta']} vence en {dias_restantes} días",
                "dias_restantes": dias_restantes,
            })
    proximas.sort(key=lambda x: x["dias_restantes"])

    return jsonify({
        "metricas": {"activos": int(conteos["activos"]), "pendientes": int(conteos["pendientes"]),
                     "alertas": len(proximas), "aprobados": int(conteos["aprobados"])},
        "recientes": recientes, "alertas": proximas,
    })
