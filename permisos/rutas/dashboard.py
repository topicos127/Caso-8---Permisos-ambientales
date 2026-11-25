"""Panel con metricas, expedientes recientes, documentos por vencer (HU-05),
avisos de plazo legal (HU-08) y prioridades segun el Indice de Preparacion
(HU-15)."""
from datetime import timedelta

from flask import Blueprint, g, jsonify

from ..bd import col_aviso, col_sometimiento, col_vencimiento, cursor, documentos_de
from ..config import ROLES_INTERNOS
from ..reglas import AVISO_VENCIMIENTO_DIAS, ahora, calcular_ipe, calcular_semaforo, hoy, vencimiento_documento
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

        # Datos de los graficos del panel (solo conteos de lo que la persona puede ver).
        cur.execute(f"SELECT e.estado, COUNT(*) AS n FROM expedientes e WHERE {filtro} GROUP BY e.estado", params)
        por_estado = {}
        for r in cur.fetchall():
            # El cliente ve "aprobado internamente" como pendiente de subsanacion (HU-07).
            clave = "pendiente" if (not interno and r["estado"] == "aprobado_interno") else r["estado"]
            por_estado[clave] = por_estado.get(clave, 0) + int(r["n"])
        cur.execute(f"SELECT e.categoria, COUNT(*) AS n FROM expedientes e WHERE {filtro} GROUP BY e.categoria", params)
        por_categoria = {r["categoria"]: int(r["n"]) for r in cur.fetchall()}
        por_consultor, actividad = [], []
        if g.usuario["rol"] == "jefe":
            cur.execute(f"""SELECT u.nombre, COUNT(*) AS n,
                                   COALESCE(SUM(e.estado NOT IN ('aprobado', 'rechazado')), 0) AS en_tramite
                            FROM expedientes e JOIN usuarios u ON u.id = e.usuario_id
                            WHERE {filtro} GROUP BY u.id, u.nombre ORDER BY n DESC, u.nombre LIMIT 8""", params)
            por_consultor = [{"nombre": r["nombre"], "total": int(r["n"]), "en_tramite": int(r["en_tramite"])}
                             for r in cur.fetchall()]
        if interno:
            desde = (ahora() - timedelta(days=13)).replace(hour=0, minute=0, second=0)
            cur.execute(f"""SELECT DATE(h.fecha) AS dia, COUNT(*) AS n FROM historial_expediente h
                            JOIN expedientes e ON e.id = h.expediente_id
                            WHERE {filtro} AND h.fecha >= %s GROUP BY DATE(h.fecha)""", [*params, desde])
            por_dia = {str(r["dia"]): int(r["n"]) for r in cur.fetchall()}
            actividad = [{"dia": (desde + timedelta(days=k)).strftime("%d/%m"),
                          "n": por_dia.get(str((desde + timedelta(days=k)).date()), 0)} for k in range(14)]

    avisos_plazo = []
    prioritarios = []
    por_semaforo = {"en_plazo": 0, "por_vencer": 0, "vencido": 0}
    bandas = {"listo": 0, "en_preparacion": 0, "en_riesgo": 0}
    suma_ipe = 0
    for a in abiertos:
        # HU-08 (Sprint 10): aviso en pantalla cuando el plazo entra en "por vencer" o ya vencio.
        sem = calcular_semaforo(a)
        por_semaforo[sem["estado_semaforo"]] = por_semaforo.get(sem["estado_semaforo"], 0) + 1
        if sem["estado_semaforo"] in ("por_vencer", "vencido"):
            avisos_plazo.append({"codigo": a["codigo"], "proyecto": a["proyecto"],
                                 "estado_semaforo": sem["estado_semaforo"],
                                 "dias_restantes_legales": sem["dias_restantes_legales"],
                                 "base_plazo": sem["base_plazo"], "fecha_limite": sem["fecha_limite"]})
        if interno:
            # HU-15: donde poner al equipo. Los que menos preparados estan, primero.
            r = calcular_ipe(a, docs[a["id"]])
            bandas[r["banda"]] = bandas.get(r["banda"], 0) + 1
            suma_ipe += r["ipe"]
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
        "graficos": {
            "por_estado": por_estado, "por_categoria": por_categoria, "por_semaforo": por_semaforo,
            "por_consultor": por_consultor, "actividad": actividad,
            "ipe_bandas": bandas if interno else None,
            "ipe_promedio": (round(suma_ipe / len(abiertos)) if interno and abiertos else None),
        },
    })
