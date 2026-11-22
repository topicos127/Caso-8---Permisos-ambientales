"""Panel con metricas, expedientes recientes, documentos por vencer (HU-05) y
prioridades segun el Indice de Preparacion (HU-15)."""
from flask import Blueprint, g, jsonify

from ..bd import cursor, documentos_de
from ..config import ROLES_INTERNOS
from ..reglas import VIGENCIA_DOCUMENTO_DIAS, calcular_ipe, como_fecha, hoy, AVISO_VENCIMIENTO_DIAS
from ..seguridad import filtro_de, requiere_login

bp = Blueprint("dashboard", __name__)

PRIORIDADES_MAXIMAS = 5


@bp.route("/dashboard", methods=["GET"])
@requiere_login
def dashboard():
    filtro, params = filtro_de(g.usuario)
    interno = g.usuario["rol"] in ROLES_INTERNOS
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
        prioritarios = []
        if interno:
            # HU-15: donde poner al equipo. Los que menos preparados estan, primero;
            # los ya resueltos no necesitan nada.
            cur.execute(f"""SELECT e.id, e.codigo, e.proyecto, e.categoria, e.estado, e.fecha_ingreso
                            FROM expedientes e WHERE {filtro} AND e.estado NOT IN ('aprobado', 'rechazado')""",
                        params)
            abiertos = cur.fetchall()
            docs = documentos_de(cur, [a["id"] for a in abiertos])
            for a in abiertos:
                r = calcular_ipe(a, docs[a["id"]])
                prioritarios.append({"codigo": a["codigo"], "proyecto": a["proyecto"], "ipe": r["ipe"],
                                     "banda": r["banda"], "banda_texto": r["banda_texto"],
                                     "proxima_accion": r["acciones"][0]["texto"] if r["acciones"] else None})
            prioritarios.sort(key=lambda p: (p["ipe"], p["codigo"]))
            prioritarios = prioritarios[:PRIORIDADES_MAXIMAS]

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
        "recientes": recientes, "alertas": proximas, "prioridades": prioritarios,
    })
