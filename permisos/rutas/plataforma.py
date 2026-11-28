"""Operacion de la plataforma: estado del servicio, registro de errores y respaldos.

/estado es publico y minimo (la pagina de estado lo consulta). Todo lo demas es solo
para el administrador de la plataforma.
"""
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, send_file

from .. import config, registro_errores, respaldos
from ..almacenamiento import AlmacenamientoError, almacen
from ..bd import _esquema, cursor
from ..config import VERSION
from ..errores import ApiError
from ..reglas import ahora
from ..seguridad import requiere_admin
from ..reglas import plural

bp = Blueprint("plataforma", __name__)



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


# ---------- Resumen para el administrador ----------

DIAS_SERIE = 14
DIAS_INACTIVA = 30


def _una(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


@bp.route("/plataforma/resumen", methods=["GET"])
@requiere_admin
def resumen():
    """Cifras de toda la plataforma para el tablero del administrador. Solo agregados: nunca el
    contenido de un expediente, un documento o un comentario."""
    ahora_ = ahora()
    hace30 = ahora_ - timedelta(days=30)
    desde_serie = (ahora_ - timedelta(days=DIAS_SERIE - 1)).replace(hour=0, minute=0, second=0)
    con_activo = "COALESCE(SUM(activo=1), 0)" if _esquema["activo"] else "COUNT(*)"
    con_2fa = "COALESCE(SUM(totp_activo=1), 0)" if _esquema["totp"] else "0"
    con_terminos = "COALESCE(SUM(terminos_aceptados_en IS NULL), 0)" if _esquema["terminos"] else "0"

    with cursor() as cur:
        e = _una(cur, "SELECT COUNT(*) AS total, COALESCE(SUM(activa), 0) AS activas, "
                      "COALESCE(SUM(fecha_creacion >= %s), 0) AS nuevas FROM organizaciones", (hace30,))
        empresas = {"total": int(e["total"]), "activas": int(e["activas"]), "nuevas_30d": int(e["nuevas"])}
        empresas["desactivadas"] = empresas["total"] - empresas["activas"]

        cur.execute(f"SELECT rol, COUNT(*) AS n, {con_activo} AS activos, {con_2fa} AS con_2fa FROM usuarios GROUP BY rol")
        por_rol = {r["rol"]: {"total": int(r["n"]), "activos": int(r["activos"]), "con_2fa": int(r["con_2fa"])}
                   for r in cur.fetchall()}
        u = _una(cur, f"SELECT COUNT(*) AS total, COALESCE(SUM(fecha_creacion >= %s), 0) AS nuevos, "
                      f"{con_terminos} AS sin_terminos FROM usuarios", (hace30,))
        usuarios = {"total": int(u["total"]), "nuevos_30d": int(u["nuevos"]), "sin_terminos": int(u["sin_terminos"]),
                    "por_rol": por_rol}

        cur.execute("SELECT estado, COUNT(*) AS n FROM expedientes GROUP BY estado")
        por_estado = {r["estado"]: int(r["n"]) for r in cur.fetchall()}
        cur.execute("SELECT categoria, COUNT(*) AS n FROM expedientes GROUP BY categoria")
        por_categoria = {r["categoria"]: int(r["n"]) for r in cur.fetchall()}
        x = _una(cur, "SELECT COUNT(*) AS total, COALESCE(SUM(fecha_ingreso >= %s), 0) AS nuevos FROM expedientes",
                 (hace30.date(),))
        expedientes = {"total": int(x["total"]), "nuevos_30d": int(x["nuevos"]), "por_estado": por_estado,
                       "por_categoria": por_categoria,
                       "en_tramite": sum(n for est, n in por_estado.items() if est not in ("aprobado", "rechazado"))}

        d = _una(cur, "SELECT COUNT(*) AS total, COALESCE(SUM(estado='recibido'), 0) AS recibidos FROM documentos")
        v = _una(cur, "SELECT COUNT(*) AS n FROM documento_versiones")
        documentos = {"total": int(d["total"]), "recibidos": int(d["recibidos"]), "versiones": int(v["n"])}

        i = _una(cur, "SELECT COALESCE(SUM(usada_en IS NULL AND revocada=0 AND expira >= %s), 0) AS pendientes, "
                      "COALESCE(SUM(usada_en IS NULL AND revocada=0 AND expira < %s), 0) AS vencidas, "
                      "COALESCE(SUM(usada_en >= %s), 0) AS usadas_30d FROM invitaciones", (ahora_, ahora_, hace30))
        invitaciones = {k: int(i[k]) for k in ("pendientes", "vencidas", "usadas_30d")}

        cur.execute("SELECT DATE(fecha) AS dia, COUNT(*) AS n FROM historial_expediente WHERE fecha >= %s GROUP BY DATE(fecha)",
                    (desde_serie,))
        por_dia = {str(r["dia"]): int(r["n"]) for r in cur.fetchall()}
        actividad = []
        for k in range(DIAS_SERIE):
            dia = (desde_serie + timedelta(days=k)).date()
            actividad.append({"dia": dia.strftime("%d/%m"), "n": por_dia.get(str(dia), 0)})

        cur.execute("""SELECT o.id, o.nombre, o.color, o.activa,
                (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol <> 'promotor') AS equipo,
                (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol = 'promotor') AS clientes,
                (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol = 'jefe') AS jefes,
                (SELECT COUNT(*) FROM expedientes ex WHERE ex.organizacion_id = o.id) AS expedientes,
                (SELECT COUNT(*) FROM expedientes ex WHERE ex.organizacion_id = o.id
                    AND ex.estado NOT IN ('aprobado', 'rechazado')) AS en_tramite,
                (SELECT MAX(h.fecha) FROM historial_expediente h JOIN expedientes ex ON ex.id = h.expediente_id
                    WHERE ex.organizacion_id = o.id) AS ultima_actividad
                FROM organizaciones o ORDER BY expedientes DESC, o.nombre""")
        filas = cur.fetchall()

    ranking = []
    for f_ in filas:
        ult = f_["ultima_actividad"]
        ranking.append({
            "id": f_["id"], "nombre": f_["nombre"], "color": f_["color"], "activa": bool(f_["activa"]),
            "equipo": int(f_["equipo"]), "clientes": int(f_["clientes"]), "jefes": int(f_["jefes"]),
            "expedientes": int(f_["expedientes"]), "en_tramite": int(f_["en_tramite"]),
            "ultima_actividad": ult.strftime("%d/%m/%Y") if ult else None,
            "inactiva": bool(f_["activa"]) and (ult is None or ult < ahora_ - timedelta(days=DIAS_INACTIVA)),
        })

    # Avisos para actuar: lo que el administrador deberia mirar hoy.
    base, archivos = _estado_base()
    ficha = respaldos.ultimo()
    avisos = []
    if not base:
        avisos.append({"nivel": "alta", "texto": "La base de datos no responde.", "pestana": "servicio"})
    if not archivos:
        avisos.append({"nivel": "alta", "texto": "El almacenamiento de archivos no responde.", "pestana": "servicio"})
    horas = None
    if ficha:
        horas = int((ahora_ - datetime.strptime(ficha["nombre"][9:24], "%Y%m%d-%H%M%S")).total_seconds() // 3600)
    if ficha is None:
        avisos.append({"nivel": "alta", "texto": "Todavía no hay ningún respaldo.", "pestana": "respaldos"})
    elif horas > 36:
        avisos.append({"nivel": "media", "texto": f"El último respaldo tiene {horas // 24} días.", "pestana": "respaldos"})
    if registro_errores.resumen()["errores"]:
        avisos.append({"nivel": "media", "texto": f"Hubo {plural(registro_errores.resumen()['errores'], 'error', 'errores')} desde el último arranque.",
                       "pestana": "servicio"})
    sin_jefe = [r["nombre"] for r in ranking if r["activa"] and r["jefes"] == 0]
    if sin_jefe:
        avisos.append({"nivel": "media", "texto": "Sin director de proyectos todavía: " + ", ".join(sin_jefe[:3])
                       + ("…" if len(sin_jefe) > 3 else "") + ".", "pestana": "empresas"})
    if invitaciones["vencidas"]:
        avisos.append({"nivel": "info", "texto": f"{plural(invitaciones['vencidas'], 'invitación vencida', 'invitaciones vencidas')} sin usar.", "pestana": "empresas"})
    inactivas = [r["nombre"] for r in ranking if r["inactiva"] and r["jefes"] > 0]
    if inactivas:
        avisos.append({"nivel": "info", "texto": f"Sin actividad en {DIAS_INACTIVA} días: " + ", ".join(inactivas[:3])
                       + ("…" if len(inactivas) > 3 else "") + ".", "pestana": "empresas"})
    jefes = por_rol.get("jefe", {"total": 0, "con_2fa": 0})
    if _esquema["totp"] and jefes["total"] > jefes["con_2fa"]:
        avisos.append({"nivel": "info", "texto": f"{plural(jefes['total'] - jefes['con_2fa'], 'director de proyectos', 'directores de proyectos')} sin verificación en dos pasos.",
                       "pestana": "empresas"})

    return jsonify({
        "empresas": empresas, "usuarios": usuarios, "expedientes": expedientes, "documentos": documentos,
        "invitaciones": invitaciones, "actividad": actividad, "ranking": ranking, "avisos": avisos,
        "servicio": {"base_de_datos": base, "archivos": archivos, "version": VERSION,
                     "almacenamiento": config.ALMACENAMIENTO, "horas_desde_respaldo": horas},
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
