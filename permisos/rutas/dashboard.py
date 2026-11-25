"""Panel con metricas, expedientes recientes, documentos por vencer (HU-05),
avisos de plazo legal (HU-08) y prioridades segun el Indice de Preparacion
(HU-15)."""
from flask import Blueprint, g, jsonify

from ..bd import col_aviso, col_sometimiento, col_vencimiento, cursor, documentos_de
from ..config import ROLES_INTERNOS
from ..reglas import AVISO_VENCIMIENTO_DIAS, calcular_ipe, calcular_semaforo, hoy, vencimiento_documento
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
            f"""SELECT d.carpeta, d.estado, d.fecha_subida, {col_vencimiento()}, e.codigo
                FROM documentos d JOIN expedientes e ON e.id = d.expediente_id
                WHERE {filtro} AND d.estado = 'recibido' AND d.fecha_subida IS NOT NULL""", params
        )
        docs_recibidos = cur.fetchall()
        # HU-05 (Sprint 10): cada usuario elige con cuantos dias de anticipacion se le avisa.
        cur.execute(f"SELECT {col_aviso()} FROM usuarios WHERE id=%s", (g.usuario["id"],))
        fila_aviso = cur.fetchone()
        aviso = int((fila_aviso or {}).get("aviso_vencimiento_dias") or AVISO_VENCIMIENTO_DIAS)

        # Expedientes en tramite: avisos de plazo (todos los roles) e IPE (consultora).
        cur.execute(f"""SELECT e.id, e.codigo, e.proyecto, e.categoria, e.estado, e.fecha_ingreso,
                               {col_sometimiento()}
                        FROM expedientes e WHERE {filtro} AND e.estado NOT IN ('aprobado', 'rechazado')""",
                    params)
        abiertos = cur.fetchall()
        docs = documentos_de(cur, [a["id"] for a in abiertos]) if interno else {}

    avisos_plazo = []
    prioritarios = []
    for a in abiertos:
        # HU-08 (Sprint 10): aviso en pantalla cuando el plazo entra en "por vencer" o ya vencio.
        sem = calcular_semaforo(a)
        if sem["estado_semaforo"] in ("por_vencer", "vencido"):
            avisos_plazo.append({"codigo": a["codigo"], "proyecto": a["proyecto"],
                                 "estado_semaforo": sem["estado_semaforo"],
                                 "dias_restantes_legales": sem["dias_restantes_legales"],
                                 "base_plazo": sem["base_plazo"], "fecha_limite": sem["fecha_limite"]})
        if interno:
            # HU-15: donde poner al equipo. Los que menos preparados estan, primero.
            r = calcular_ipe(a, docs[a["id"]])
            prioritarios.append({"codigo": a["codigo"], "proyecto": a["proyecto"], "ipe": r["ipe"],
                                 "banda": r["banda"], "banda_texto": r["banda_texto"],
                                 "proxima_accion": r["acciones"][0]["texto"] if r["acciones"] else None})
    avisos_plazo.sort(key=lambda x: x["dias_restantes_legales"])
    prioritarios.sort(key=lambda p: (p["ipe"], p["codigo"]))
    prioritarios = prioritarios[:PRIORIDADES_MAXIMAS]

    proximas = []
    dia = hoy()
    for d in docs_recibidos:
        vence = vencimiento_documento(d)
        dias_restantes = (vence - dia).days
        if dias_restantes < aviso:
            texto = (f"{d['carpeta']} venció hace {abs(dias_restantes)} días" if dias_restantes < 0
                     else f"{d['carpeta']} vence en {dias_restantes} días")
            proximas.append({
                "codigo": d["codigo"],
                "descripcion": texto,
                "dias_restantes": dias_restantes,
                "fecha_vencimiento": vence.strftime("%d/%m/%Y"),
                "vencimiento_real": bool(d.get("fecha_vencimiento")),
            })
    proximas.sort(key=lambda x: x["dias_restantes"])

    return jsonify({
        "metricas": {"activos": int(conteos["activos"]), "pendientes": int(conteos["pendientes"]),
                     "alertas": len(proximas), "aprobados": int(conteos["aprobados"])},
        "recientes": recientes, "alertas": proximas, "prioridades": prioritarios if interno else [],
        "avisos_plazo": avisos_plazo, "aviso_vencimiento_dias": aviso,
    })
