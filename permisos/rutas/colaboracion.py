"""Trabajo en equipo y reportes: responsable de cada expediente, comentarios internos,
vistas guardadas, busqueda global y exportaciones (Excel y CSV).

Todo se limita a la empresa del usuario con las mismas reglas de seguridad.py.
"""
import csv
import io
import json
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request, send_file

from ..bd import (_esquema, cargar_expediente, col_sometimiento, cursor, documentos_de,
                  registrar_historial)
from ..config import ACCION_RESPONSABLE, ROLES_INTERNOS, ZONA
from ..errores import ApiError
from ..reglas import calcular_ipe, calcular_semaforo
from ..seguridad import condicion_empresa, exigir_jefe, exigir_lectura, filtro_de, requiere_login
from ..utiles import texto

bp = Blueprint("colaboracion", __name__)

ETIQUETA_ESTADO = {"pendiente": "Pendiente", "aprobado_interno": "Aprobado internamente",
                   "evaluacion": "En evaluación", "aprobado": "Aprobado", "rechazado": "Rechazado"}
ETIQUETA_SEMAFORO = {"en_plazo": "En plazo", "por_vencer": "Por vencer", "vencido": "Vencido", "resuelto": "Resuelto"}
MAX_VISTAS = 12
FILTROS_VISTA = {"q", "estado", "categoria", "orden"}


def _solo_internos():
    if g.usuario["rol"] not in ROLES_INTERNOS:
        raise ApiError(403, "Solo el equipo de la consultora puede hacer esto.")


def _seguro(valor):
    """Evita la inyeccion de formulas: un texto que empieza con = + - @ se abriria como formula en Excel."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


# ---------- Responsable ----------

@bp.route("/expedientes/<codigo>/responsable", methods=["POST"])
@requiere_login
def cambiar_responsable(codigo):
    exigir_jefe(g.usuario, "Solo el jefe de la consultora puede cambiar el responsable.")
    data = request.get_json(silent=True) or {}
    nuevo = data.get("usuario_id")
    if isinstance(nuevo, bool) or not isinstance(nuevo, int):
        raise ApiError(400, "Elija a la persona responsable.")
    empresa, params_empresa = condicion_empresa(g.usuario, "u")
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        activo = "u.activo=1" if _esquema["activo"] else "1=1"
        cur.execute(f"SELECT u.id, u.nombre, u.rol FROM usuarios u WHERE u.id=%s AND {empresa} "
                    f"AND u.rol IN ('consultor','jefe') AND {activo}", (nuevo, *params_empresa))
        destino = cur.fetchone()
        if not destino:
            raise ApiError(404, "Esa persona no está activa en su consultora.")
        if destino["id"] == exp["usuario_id"]:
            raise ApiError(409, "Ya es la persona responsable.")
        cur.execute("UPDATE expedientes SET usuario_id=%s WHERE id=%s", (destino["id"], exp["id"]))
        registrar_historial(cur, exp["id"], g.usuario["id"], f"{ACCION_RESPONSABLE} a {destino['nombre']}"[:50])
    return jsonify({"ok": True, "responsable": {"id": destino["id"], "nombre": destino["nombre"]},
                    "mensaje": f"{destino['nombre']} es ahora responsable del expediente."}), 200


# ---------- Comentarios internos ----------

@bp.route("/expedientes/<codigo>/comentarios", methods=["GET"])
@requiere_login
def listar_comentarios(codigo):
    _solo_internos()  # el promotor no ve las conversaciones internas
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("""SELECT c.id, c.texto, c.fecha, u.nombre AS autor, u.rol AS autor_rol, c.usuario_id
                       FROM comentarios c JOIN usuarios u ON u.id = c.usuario_id
                       WHERE c.expediente_id=%s ORDER BY c.fecha DESC, c.id DESC LIMIT 200""", (exp["id"],))
        filas = cur.fetchall()
    for c in filas:
        c["fecha"] = c["fecha"].strftime("%d/%m/%Y %H:%M")
        c["mio"] = c.pop("usuario_id") == g.usuario["id"]
    return jsonify({"comentarios": filas}), 200


@bp.route("/expedientes/<codigo>/comentarios", methods=["POST"])
@requiere_login
def comentar(codigo):
    _solo_internos()
    data = request.get_json(silent=True) or {}
    cuerpo = texto(data, "texto", 1000)
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        ahora = datetime.now(ZONA).replace(tzinfo=None, microsecond=0)
        cur.execute("INSERT INTO comentarios (expediente_id, usuario_id, texto, fecha) VALUES (%s, %s, %s, %s)",
                    (exp["id"], g.usuario["id"], cuerpo, ahora))
    return jsonify({"ok": True, "mensaje": "Comentario publicado."}), 201


# ---------- Vistas guardadas ----------

@bp.route("/vistas", methods=["GET"])
@requiere_login
def listar_vistas():
    with cursor() as cur:
        cur.execute("SELECT id, nombre, filtros FROM vistas_guardadas WHERE usuario_id=%s ORDER BY id", (g.usuario["id"],))
        filas = cur.fetchall()
    for v in filas:
        try:
            v["filtros"] = json.loads(v["filtros"])
        except ValueError:
            v["filtros"] = {}
    return jsonify({"vistas": filas}), 200


@bp.route("/vistas", methods=["POST"])
@requiere_login
def guardar_vista():
    data = request.get_json(silent=True) or {}
    nombre = texto(data, "nombre", 60)
    filtros = data.get("filtros")
    if not isinstance(filtros, dict):
        raise ApiError(400, "Indique los filtros de la vista.")
    limpios = {}
    for clave, valor in filtros.items():
        if clave not in FILTROS_VISTA:
            raise ApiError(400, f"Filtro no permitido: {clave}.")
        if not isinstance(valor, str) or len(valor) > 100:
            raise ApiError(400, f"El filtro '{clave}' no es válido.")
        if valor:
            limpios[clave] = valor
    if not limpios:
        raise ApiError(400, "Aplique al menos un filtro antes de guardar la vista.")
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM vistas_guardadas WHERE usuario_id=%s", (g.usuario["id"],))
        if cur.fetchone()["n"] >= MAX_VISTAS:
            raise ApiError(409, f"Puede guardar hasta {MAX_VISTAS} vistas. Elimine alguna.")
        cur.execute("INSERT INTO vistas_guardadas (usuario_id, nombre, filtros, fecha) VALUES (%s, %s, %s, %s)",
                    (g.usuario["id"], nombre, json.dumps(limpios, ensure_ascii=False),
                     datetime.now(ZONA).replace(tzinfo=None, microsecond=0)))
        vista_id = cur.lastrowid
    return jsonify({"ok": True, "id": vista_id, "mensaje": "Vista guardada."}), 201


@bp.route("/vistas/<int:vista_id>", methods=["DELETE"])
@requiere_login
def borrar_vista(vista_id):
    with cursor() as cur:
        cur.execute("DELETE FROM vistas_guardadas WHERE id=%s AND usuario_id=%s", (vista_id, g.usuario["id"]))
        if cur.rowcount != 1:
            raise ApiError(404, "Vista no encontrada.")
    return jsonify({"ok": True, "mensaje": "Vista eliminada."}), 200


# ---------- Busqueda global (Ctrl+K) ----------

def _patron(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@bp.route("/buscar", methods=["GET"])
@requiere_login
def buscar():
    q = request.args.get("q", "").strip()[:80]
    if len(q) < 2:
        return jsonify({"expedientes": [], "personas": []}), 200
    filtro, params = filtro_de(g.usuario)
    patron = _patron(q)
    personas = []
    with cursor() as cur:
        cur.execute(f"""SELECT e.codigo, e.proyecto, e.promotor, e.estado FROM expedientes e
                        WHERE {filtro} AND (e.codigo LIKE %s OR e.proyecto LIKE %s OR e.promotor LIKE %s)
                        ORDER BY e.fecha_ingreso DESC, e.id DESC LIMIT 8""", [*params, patron, patron, patron])
        expedientes = cur.fetchall()
        if g.usuario["rol"] == "jefe":
            empresa, params_empresa = condicion_empresa(g.usuario, "u")
            cur.execute(f"""SELECT u.id, u.nombre, u.email FROM usuarios u
                            WHERE {empresa} AND u.rol='consultor' AND (u.nombre LIKE %s OR u.email LIKE %s)
                            ORDER BY u.nombre LIMIT 5""", [*params_empresa, patron, patron])
            personas = cur.fetchall()
    for e in expedientes:
        e["estado"] = ETIQUETA_ESTADO.get(e["estado"], e["estado"])
    return jsonify({"expedientes": expedientes, "personas": personas}), 200


# ---------- Exportaciones ----------

def _filas_cartera(u):
    filtro, params = filtro_de(u)
    interno = u["rol"] in ROLES_INTERNOS
    with cursor() as cur:
        cur.execute(f"""SELECT e.id, e.codigo, e.proyecto, e.promotor, e.categoria, e.estado, e.fecha_ingreso,
                               {col_sometimiento()}, uu.nombre AS responsable
                        FROM expedientes e LEFT JOIN usuarios uu ON uu.id = e.usuario_id
                        WHERE {filtro} ORDER BY e.fecha_ingreso DESC, e.id DESC LIMIT 5000""", params)
        filas = cur.fetchall()
        docs = documentos_de(cur, [f["id"] for f in filas]) if interno else {}
    salida = []
    for f in filas:
        sem = calcular_semaforo(f)
        fila = {"codigo": f["codigo"], "proyecto": f["proyecto"], "promotor": f["promotor"],
                "categoria": f["categoria"], "estado": ETIQUETA_ESTADO.get(f["estado"], f["estado"]),
                "ingreso": f["fecha_ingreso"], "responsable": f["responsable"] or "",
                "plazo": ETIQUETA_SEMAFORO.get(sem["estado_semaforo"], sem["estado_semaforo"]),
                "dias_restantes": sem["dias_restantes_legales"], "ipe": None}
        if interno:
            fila["ipe"] = calcular_ipe(f, docs[f["id"]])["ipe"]
        salida.append(fila)
    return salida


@bp.route("/exportar/cartera.xlsx", methods=["GET"])
@requiere_login
def exportar_cartera():
    """Excel con todos los expedientes que el usuario puede ver: lo que se presenta a gerencia o a un cliente."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    filas = _filas_cartera(g.usuario)
    interno = g.usuario["rol"] in ROLES_INTERNOS
    wb = Workbook()
    ws = wb.active
    ws.title = "Cartera"
    columnas = [("Código", "codigo", 18), ("Proyecto", "proyecto", 40), ("Promotor", "promotor", 28),
                ("Categoría", "categoria", 11), ("Estado", "estado", 22), ("Ingreso", "ingreso", 13),
                ("Responsable", "responsable", 26), ("Plazo", "plazo", 20), ("Días restantes", "dias_restantes", 15)]
    if interno:
        columnas.append(("Preparación (IPE)", "ipe", 17))
    ws.append([c[0] for c in columnas])
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="1F3A2E")
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    for f in filas:
        ws.append([_seguro(f[c[1]]) for c in columnas])
    for i, (_, _, ancho) in enumerate(columnas, 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    for fila in ws.iter_rows(min_row=2, min_col=6, max_col=6):
        for celda in fila:
            celda.number_format = "DD/MM/YYYY"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    resumen = wb.create_sheet("Resumen")
    resumen.append(["Resumen de la cartera"])
    resumen["A1"].font = Font(bold=True, size=13)
    resumen.append(["Generado", datetime.now(ZONA).strftime("%d/%m/%Y %H:%M")])
    resumen.append(["Expedientes", len(filas)])
    for estado in ETIQUETA_ESTADO.values():
        resumen.append([estado, sum(1 for f in filas if f["estado"] == estado)])
    resumen.column_dimensions["A"].width = 26
    resumen.column_dimensions["B"].width = 20

    salida = io.BytesIO()
    wb.save(salida)
    salida.seek(0)
    nombre = f"cartera-{datetime.now(ZONA):%Y%m%d}.xlsx"
    return send_file(salida, as_attachment=True, download_name=nombre,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/exportar/historial.csv", methods=["GET"])
@requiere_login
def exportar_historial():
    """Historial de acciones en CSV (para auditoria). Misma regla que /historial: jefe todo, consultor lo suyo."""
    u = g.usuario
    if u["rol"] not in ROLES_INTERNOS:
        raise ApiError(403, "El historial solo lo ven el jefe y los consultores.")
    empresa, params = condicion_empresa(u)
    condiciones, params = [empresa], list(params)
    if u["rol"] == "consultor":
        condiciones.append("e.usuario_id=%s")
        params.append(u["id"])
    with cursor() as cur:
        cur.execute(f"""SELECT h.fecha, e.codigo, e.proyecto, uu.nombre AS usuario, uu.rol AS rol, h.accion
                        FROM historial_expediente h JOIN expedientes e ON e.id = h.expediente_id
                        JOIN usuarios uu ON uu.id = h.usuario_id
                        WHERE {' AND '.join(condiciones)} ORDER BY h.fecha DESC, h.id DESC LIMIT 20000""", params)
        filas = cur.fetchall()
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["Fecha", "Código", "Proyecto", "Usuario", "Rol", "Acción"])
    for f in filas:
        escritor.writerow([f["fecha"].strftime("%Y-%m-%d %H:%M:%S"), f["codigo"], _seguro(f["proyecto"]),
                           _seguro(f["usuario"]), f["rol"], _seguro(f["accion"])])
    nombre = f"historial-{datetime.now(ZONA):%Y%m%d}.csv"
    # BOM para que Excel abra bien las tildes.
    return Response("﻿" + salida.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
