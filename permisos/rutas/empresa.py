"""Mi consultora: datos de la empresa, politica de seguridad, uso, exportacion completa,
registro de accesos y titularidad. Es del director de proyectos (rol jefe) de cada empresa.

El titular es quien creo la cuenta (o a quien se le transfirio): es el unico que invita a otros
directores, cambia roles y transfiere la titularidad. Cualquier director ve y edita lo demas.
"""
import csv
import io
import os
import re
import tempfile
import time
import zipfile
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request, send_file

from .. import auditoria
from ..almacenamiento import AlmacenamientoError, almacen
from ..bd import _esquema, cursor
from ..config import EMAIL_RE, ZONA
from ..errores import ApiError
from ..seguridad import condicion_empresa, requiere_login
from ..utiles import texto
from .colaboracion import _seguro, libro_cartera
from .cuenta import _confirmar_clave

bp = Blueprint("empresa", __name__)

CAMPOS_DATOS = (("razon_social", 200), ("ruc", 40), ("direccion", 300), ("telefono", 40),
                ("email_contacto", 255), ("pie_documento", 300))
SESIONES_PERMITIDAS = (15, 30, 60, 120)  # minutos; nunca mas que el maximo global del servidor
AVISOS_PERMITIDOS = (15, 30, 45)
LIMITE_DOCUMENTOS_ZIP = 400 * 1024 * 1024  # bytes de documentos que entran en la exportacion
_ultimo_export = {}


def _director():
    u = g.usuario
    if u["rol"] != "jefe" or u.get("organizacion_id") is None or not _esquema["org"]:
        raise ApiError(403, "Solo el director de proyectos puede ver esta sección.")
    return u


def _necesita(bandera, que):
    if not _esquema[bandera]:
        raise ApiError(503, f"{que} aún no está disponible: falta actualizar la base de datos.")


def es_titular(cur, u):
    """True si el usuario es el titular de su empresa (o si la empresa aun no tiene uno definido)."""
    if not _esquema["titular"]:
        return True
    cur.execute("SELECT titular_id FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
    titular = (cur.fetchone() or {}).get("titular_id")
    return titular is None or titular == u["id"]


def _exigir_titular(cur, u):
    if not es_titular(cur, u):
        raise ApiError(403, "Solo el titular de la cuenta puede hacer esto.")


def _fecha(d):
    return d.strftime("%d/%m/%Y %H:%M") if d else None


# ---------- Datos de la empresa ----------

@bp.route("/organizacion/datos", methods=["GET"])
@requiere_login
def ver_datos():
    u = _director()
    _necesita("org_perfil", "Los datos de la empresa")
    with cursor() as cur:
        cur.execute("SELECT razon_social, ruc, direccion, telefono, email_contacto, pie_documento "
                    "FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
        fila = cur.fetchone() or {}
    return jsonify({"datos": {k: fila.get(k) or "" for k, _ in CAMPOS_DATOS}}), 200


@bp.route("/organizacion/datos", methods=["POST"])
@requiere_login
def guardar_datos():
    u = _director()
    _necesita("org_perfil", "Los datos de la empresa")
    data = request.get_json(silent=True) or {}
    sets, params = [], []
    for campo, maximo in CAMPOS_DATOS:
        if campo in data:
            valor = texto(data, campo, maximo, obligatorio=False)
            if campo == "email_contacto" and valor and not EMAIL_RE.match(valor.lower()):
                raise ApiError(400, "El correo de contacto no es válido.")
            sets.append(f"{campo}=%s")
            params.append(valor or None)
    if not sets:
        raise ApiError(400, "No hay nada que guardar.")
    with cursor() as cur:
        cur.execute(f"UPDATE organizaciones SET {', '.join(sets)} WHERE id=%s", (*params, u["organizacion_id"]))
        auditoria.registrar(cur, u["organizacion_id"], u["id"], "datos", ", ".join(s.split("=")[0] for s in sets))
    return jsonify({"ok": True, "mensaje": "Datos de la empresa guardados."}), 200


# ---------- Politica de seguridad y plazos ----------

@bp.route("/organizacion/politica", methods=["GET"])
@requiere_login
def ver_politica():
    u = _director()
    _necesita("org_politica", "La política de la empresa")
    with cursor() as cur:
        cur.execute("SELECT exigir_2fa, sesion_minutos, aviso_defecto FROM organizaciones WHERE id=%s",
                    (u["organizacion_id"],))
        o = cur.fetchone() or {}
        mi_2fa = False
        if _esquema["totp"]:
            cur.execute("SELECT totp_activo FROM usuarios WHERE id=%s", (u["id"],))
            mi_2fa = bool((cur.fetchone() or {}).get("totp_activo"))
        titular = es_titular(cur, u)
    return jsonify({"exigir_2fa": bool(o.get("exigir_2fa")), "sesion_minutos": o.get("sesion_minutos"),
                    "aviso_defecto": o.get("aviso_defecto"), "mi_2fa": mi_2fa, "soy_titular": titular,
                    "opciones_sesion": list(SESIONES_PERMITIDAS), "opciones_aviso": list(AVISOS_PERMITIDOS)}), 200


@bp.route("/organizacion/politica", methods=["POST"])
@requiere_login
def guardar_politica():
    u = _director()
    _necesita("org_politica", "La política de la empresa")
    data = request.get_json(silent=True) or {}
    sets, params, cambios = [], [], []
    with cursor() as cur:
        if "exigir_2fa" in data:
            valor = data["exigir_2fa"]
            if not isinstance(valor, bool):
                raise ApiError(400, "Indique si se exigen o no los dos pasos.")
            if valor:
                cur.execute("SELECT totp_activo FROM usuarios WHERE id=%s", (u["id"],)) if _esquema["totp"] else None
                if not _esquema["totp"] or not (cur.fetchone() or {}).get("totp_activo"):
                    raise ApiError(409, "Active primero sus propios dos pasos en «Mi perfil»: si no, quedaría "
                                        "bloqueado cuando la política empiece a regir.")
            sets.append("exigir_2fa=%s")
            params.append(valor)
            cambios.append("dos pasos obligatorios: " + ("sí" if valor else "no"))
        if "sesion_minutos" in data:
            valor = data["sesion_minutos"]
            if valor is not None and (isinstance(valor, bool) or valor not in SESIONES_PERMITIDAS):
                raise ApiError(400, "Elija 15, 30, 60 o 120 minutos, o deje el valor general.")
            sets.append("sesion_minutos=%s")
            params.append(valor)
            cambios.append(f"inactividad: {valor or 'general'} min")
        if "aviso_defecto" in data:
            valor = data["aviso_defecto"]
            if valor is not None and (isinstance(valor, bool) or valor not in AVISOS_PERMITIDOS):
                raise ApiError(400, "El aviso debe ser de 15, 30 o 45 días.")
            sets.append("aviso_defecto=%s")
            params.append(valor)
            cambios.append(f"aviso de vencimiento: {valor or 'sin definir'}")
        if not sets:
            raise ApiError(400, "No hay nada que guardar.")
        cur.execute(f"UPDATE organizaciones SET {', '.join(sets)} WHERE id=%s", (*params, u["organizacion_id"]))
        aplicados = 0
        if data.get("aplicar_aviso") is True and data.get("aviso_defecto") is not None and _esquema["aviso"]:
            aplicados = cur.execute("UPDATE usuarios SET aviso_vencimiento_dias=%s WHERE organizacion_id=%s "
                                    "AND rol IN ('consultor', 'jefe')", (data["aviso_defecto"], u["organizacion_id"]))
            cambios.append(f"aviso aplicado a {aplicados} persona(s)")
        auditoria.registrar(cur, u["organizacion_id"], u["id"], "politica", "; ".join(cambios))
    return jsonify({"ok": True, "aplicados": aplicados, "mensaje": "Política guardada."}), 200


@bp.route("/organizacion/equipo", methods=["GET"])
@requiere_login
def seguridad_del_equipo():
    """Quien tiene los dos pasos activos y cuando entro por ultima vez."""
    u = _director()
    empresa, params = condicion_empresa(u, "u")
    activo = "u.activo" if _esquema["activo"] else "1"
    totp = "u.totp_activo" if _esquema["totp"] else "0"
    with cursor() as cur:
        cur.execute(f"""SELECT u.id, u.nombre, u.email, u.rol, {activo} AS activo, {totp} AS dos_pasos,
                               (SELECT MAX(ev.fecha) FROM eventos_cuenta ev
                                WHERE ev.usuario_id = u.id AND ev.tipo = 'acceso') AS ultimo_acceso
                        FROM usuarios u WHERE {empresa} AND u.rol IN ('consultor', 'jefe')
                        ORDER BY u.rol, u.nombre""", params)
        filas = cur.fetchall()
        titular = None
        if _esquema["titular"]:
            cur.execute("SELECT titular_id FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
            titular = (cur.fetchone() or {}).get("titular_id")
    for f in filas:
        f["activo"], f["dos_pasos"] = bool(f["activo"]), bool(f["dos_pasos"])
        f["titular"] = f["id"] == titular
        f["ultimo_acceso"] = _fecha(f["ultimo_acceso"])
    return jsonify({"equipo": filas}), 200


@bp.route("/organizacion/cerrar-sesiones", methods=["POST"])
@requiere_login
def cerrar_sesiones_del_equipo():
    """Cierra las sesiones abiertas de todas las personas de la empresa (menos la de quien lo pide)."""
    u = _director()
    _necesita("sesion", "Cerrar sesiones")
    data = request.get_json(silent=True) or {}
    with cursor() as cur:
        _confirmar_clave(cur, data.get("password"))
        n = cur.execute("UPDATE usuarios SET sesion_version = sesion_version + 1 WHERE organizacion_id=%s AND id<>%s",
                        (u["organizacion_id"], u["id"]))
        auditoria.registrar(cur, u["organizacion_id"], u["id"], "sesiones_cerradas", f"{n} cuenta(s)")
    return jsonify({"ok": True, "cuentas": n,
                    "mensaje": f"Se cerraron las sesiones de {n} cuenta(s). Tendrán que iniciar sesión otra vez."}), 200


# ---------- Uso ----------

@bp.route("/organizacion/uso", methods=["GET"])
@requiere_login
def uso():
    u = _director()
    org = u["organizacion_id"]
    activo = "COALESCE(SUM(activo=1), 0)" if _esquema["activo"] else "COUNT(*)"
    with cursor() as cur:
        cur.execute(f"SELECT rol, COUNT(*) AS n, {activo} AS activos FROM usuarios WHERE organizacion_id=%s GROUP BY rol", (org,))
        personas = {r["rol"]: {"total": int(r["n"]), "activos": int(r["activos"])} for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(estado NOT IN ('aprobado', 'rechazado')), 0) AS en_tramite "
                    "FROM expedientes WHERE organizacion_id=%s", (org,))
        e = cur.fetchone()
        cur.execute("SELECT COALESCE(SUM(d.estado='recibido'), 0) AS recibidos FROM documentos d "
                    "JOIN expedientes e ON e.id = d.expediente_id WHERE e.organizacion_id=%s", (org,))
        docs = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(v.archivo_tamano), 0) AS bytes FROM documento_versiones v "
                    "JOIN documentos d ON d.id = v.documento_id JOIN expedientes e ON e.id = d.expediente_id "
                    "WHERE e.organizacion_id=%s", (org,))
        v = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n FROM comentarios c JOIN expedientes e ON e.id = c.expediente_id "
                    "WHERE e.organizacion_id=%s", (org,))
        comentarios = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM invitaciones WHERE organizacion_id=%s AND usada_en IS NULL "
                    "AND revocada=0 AND expira >= %s", (org, datetime.now(ZONA).replace(tzinfo=None)))
        invitaciones = cur.fetchone()["n"]
    return jsonify({"personas": personas, "expedientes": {"total": int(e["n"]), "en_tramite": int(e["en_tramite"])},
                    "documentos": {"recibidos": int(docs["recibidos"]), "versiones": int(v["n"]),
                                   "bytes": int(v["bytes"])},
                    "comentarios": int(comentarios), "invitaciones_pendientes": int(invitaciones)}), 200


# ---------- Exportar todos los datos ----------

def _csv(cabecera, filas):
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(cabecera)
    for f in filas:
        escritor.writerow([_seguro(c) if isinstance(c, str) else c for c in f])
    return ("﻿" + salida.getvalue()).encode("utf-8")


def _nombre_seguro(texto_):
    return re.sub(r"[^\w.\- ]", "_", str(texto_ or "archivo"))[:120] or "archivo"


@bp.route("/organizacion/exportar", methods=["GET"])
@requiere_login
def exportar_todo():
    """ZIP con todo lo de la empresa: cartera, historial, comentarios, equipo y los documentos."""
    u = _director()
    org = u["organizacion_id"]
    ahora = time.time()
    if ahora - _ultimo_export.get(org, 0) < 120:
        raise ApiError(429, "Acaba de generar una exportación. Espere un par de minutos para pedir otra.")
    _ultimo_export[org] = ahora

    empresa, params_u = condicion_empresa(u, "u")
    with cursor() as cur:
        cur.execute("SELECT nombre FROM organizaciones WHERE id=%s", (org,))
        nombre_empresa = cur.fetchone()["nombre"]
        cur.execute("""SELECT h.fecha, e.codigo, e.proyecto, uu.nombre AS usuario, uu.rol, h.accion
                       FROM historial_expediente h JOIN expedientes e ON e.id = h.expediente_id
                       JOIN usuarios uu ON uu.id = h.usuario_id
                       WHERE e.organizacion_id=%s ORDER BY h.fecha, h.id""", (org,))
        historial = cur.fetchall()
        cur.execute("""SELECT c.fecha, e.codigo, uu.nombre AS autor, c.texto
                       FROM comentarios c JOIN expedientes e ON e.id = c.expediente_id
                       JOIN usuarios uu ON uu.id = c.usuario_id
                       WHERE e.organizacion_id=%s ORDER BY c.fecha, c.id""", (org,))
        comentarios = cur.fetchall()
        cur.execute(f"SELECT u.nombre, u.email, u.rol, {'u.activo' if _esquema['activo'] else '1'} AS activo, "
                    f"u.fecha_creacion FROM usuarios u WHERE {empresa} ORDER BY u.rol, u.nombre", params_u)
        equipo = cur.fetchall()
        cur.execute("""SELECT e.codigo, d.carpeta, v.version, v.archivo_nombre, v.archivo_ruta, v.archivo_tamano,
                              v.sha256, v.codigo_trazabilidad, v.fecha_subida
                       FROM documento_versiones v JOIN documentos d ON d.id = v.documento_id
                       JOIN expedientes e ON e.id = d.expediente_id
                       WHERE e.organizacion_id=%s ORDER BY e.codigo, d.carpeta, v.version""", (org,))
        versiones = cur.fetchall()
        auditoria.registrar(cur, org, u["id"], "exportacion", f"{len(versiones)} versión(es) de documentos")

    total_bytes = sum(int(v["archivo_tamano"] or 0) for v in versiones)
    incluir_todo = total_bytes <= LIMITE_DOCUMENTOS_ZIP
    ultimas = {}
    for v in versiones:
        ultimas[(v["codigo"], v["carpeta"])] = v["version"]
    nota = ""
    if not incluir_todo:
        nota = ("Los documentos superan el tamaño máximo de esta exportación, así que se incluyó solo la versión "
                "más reciente de cada uno. El índice (indice_documentos.csv) lista todas las versiones con su huella.")
    fd, ruta_zip = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    indice, faltantes = [], 0
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("cartera.xlsx", libro_cartera(u).getvalue())
        z.writestr("historial.csv", _csv(["Fecha", "Código", "Proyecto", "Usuario", "Rol", "Acción"],
                                         [[h["fecha"].strftime("%Y-%m-%d %H:%M:%S"), h["codigo"], h["proyecto"],
                                           h["usuario"], h["rol"], h["accion"]] for h in historial]))
        z.writestr("comentarios.csv", _csv(["Fecha", "Código", "Autor", "Comentario"],
                                           [[c["fecha"].strftime("%Y-%m-%d %H:%M:%S"), c["codigo"], c["autor"], c["texto"]]
                                            for c in comentarios]))
        z.writestr("equipo.csv", _csv(["Nombre", "Correo", "Rol", "Activo", "Creado"],
                                      [[p["nombre"], p["email"], p["rol"], "sí" if p["activo"] else "no",
                                        p["fecha_creacion"].strftime("%Y-%m-%d") if p["fecha_creacion"] else ""]
                                       for p in equipo]))
        for v in versiones:
            incluido = "no"
            if incluir_todo or ultimas[(v["codigo"], v["carpeta"])] == v["version"]:
                try:
                    contenido = almacen().leer(v["archivo_ruta"]) if v["archivo_ruta"] else None
                except AlmacenamientoError:
                    contenido = None
                if contenido is None:
                    faltantes += 1
                else:
                    z.writestr(f"documentos/{_nombre_seguro(v['codigo'])}/{_nombre_seguro(v['carpeta'])}/"
                               f"v{v['version']}_{_nombre_seguro(v['archivo_nombre'])}", contenido)
                    incluido = "sí"
            indice.append([v["codigo"], v["carpeta"], v["version"], v["archivo_nombre"], v["archivo_tamano"],
                           v["sha256"], v["codigo_trazabilidad"],
                           v["fecha_subida"].strftime("%Y-%m-%d %H:%M:%S") if v["fecha_subida"] else "", incluido])
        z.writestr("indice_documentos.csv", _csv(["Código", "Carpeta", "Versión", "Archivo", "Bytes", "SHA-256",
                                                  "Trazabilidad", "Subido", "Incluido en el ZIP"], indice))
        z.writestr("LEEME.txt", (
            f"Exportación de {nombre_empresa}\nGenerada el {datetime.now(ZONA):%d/%m/%Y %H:%M} por {u['nombre']}.\n\n"
            "cartera.xlsx           todos los expedientes (estado, plazo, responsable, preparación)\n"
            "historial.csv          quién hizo cada acción y cuándo\n"
            "comentarios.csv        comentarios internos de los expedientes\n"
            "equipo.csv             las personas de la consultora\n"
            "indice_documentos.csv  cada versión de cada documento, con su huella SHA-256 y su código de trazabilidad\n"
            "documentos/            los archivos, por expediente y carpeta\n"
            + (f"\n{nota}\n" if nota else "") + (f"\n{faltantes} archivo(s) no se encontraron en el almacenamiento.\n" if faltantes else "")))
    resp = send_file(ruta_zip, as_attachment=True, mimetype="application/zip",
                     download_name=f"datos-{_nombre_seguro(nombre_empresa).replace(' ', '-')}-{datetime.now(ZONA):%Y%m%d}.zip")
    resp.call_on_close(lambda: os.path.exists(ruta_zip) and os.remove(ruta_zip))
    return resp


# ---------- Registro de accesos y cambios ----------

@bp.route("/organizacion/auditoria", methods=["GET"])
@requiere_login
def ver_auditoria():
    u = _director()
    tipo = request.args.get("tipo", "").strip()
    if tipo and tipo not in auditoria.TIPOS:
        raise ApiError(400, "Tipo de evento no válido.")
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        raise ApiError(400, "La página debe ser un número.")
    por_pagina = 40
    donde, params = "ev.organizacion_id=%s", [u["organizacion_id"]]
    if tipo:
        donde += " AND ev.tipo=%s"
        params.append(tipo)
    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM eventos_cuenta ev WHERE {donde}", params)
        total = cur.fetchone()["n"]
        cur.execute(f"""SELECT ev.fecha, ev.tipo, ev.detalle, ev.ip, ev.email, uu.nombre
                        FROM eventos_cuenta ev LEFT JOIN usuarios uu ON uu.id = ev.usuario_id
                        WHERE {donde} ORDER BY ev.id DESC LIMIT %s OFFSET %s""",
                    [*params, por_pagina, (pagina - 1) * por_pagina])
        filas = cur.fetchall()
    return jsonify({
        "eventos": [{"fecha": _fecha(f["fecha"]), "tipo": f["tipo"], "texto": auditoria.TIPOS.get(f["tipo"], f["tipo"]),
                     "detalle": f["detalle"], "ip": f["ip"], "quien": f["nombre"] or f["email"] or "—"} for f in filas],
        "tipos": [{"clave": k, "texto": t} for k, t in auditoria.TIPOS.items() if not k.startswith("admin_")],
        "paginacion": {"total": total, "pagina": pagina, "paginas": max(1, -(-total // por_pagina))},
    }), 200


@bp.route("/organizacion/auditoria.csv", methods=["GET"])
@requiere_login
def auditoria_csv():
    u = _director()
    with cursor() as cur:
        cur.execute("""SELECT ev.fecha, ev.tipo, ev.detalle, ev.ip, ev.email, uu.nombre
                       FROM eventos_cuenta ev LEFT JOIN usuarios uu ON uu.id = ev.usuario_id
                       WHERE ev.organizacion_id=%s ORDER BY ev.id DESC LIMIT 20000""", (u["organizacion_id"],))
        filas = cur.fetchall()
    cuerpo = _csv(["Fecha", "Evento", "Detalle", "Persona", "Correo", "IP"],
                  [[f["fecha"].strftime("%Y-%m-%d %H:%M:%S"), auditoria.TIPOS.get(f["tipo"], f["tipo"]), f["detalle"] or "",
                    f["nombre"] or "", f["email"] or "", f["ip"] or ""] for f in filas])
    return Response(cuerpo, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="accesos-{datetime.now(ZONA):%Y%m%d}.csv"'})


# ---------- Titularidad ----------

@bp.route("/organizacion/directores", methods=["GET"])
@requiere_login
def directores():
    u = _director()
    empresa, params = condicion_empresa(u, "u")
    activo = "u.activo" if _esquema["activo"] else "1"
    with cursor() as cur:
        cur.execute(f"SELECT u.id, u.nombre, u.email, u.rol, {activo} AS activo FROM usuarios u "
                    f"WHERE {empresa} AND u.rol IN ('jefe', 'consultor') ORDER BY u.rol, u.nombre", params)
        filas = cur.fetchall()
        titular = None
        if _esquema["titular"]:
            cur.execute("SELECT titular_id FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
            titular = (cur.fetchone() or {}).get("titular_id")
        soy = titular is None or titular == u["id"]
    jefes = [{"id": f["id"], "nombre": f["nombre"], "email": f["email"], "titular": f["id"] == titular,
              "activo": bool(f["activo"])} for f in filas if f["rol"] == "jefe"]
    candidatos = [{"id": f["id"], "nombre": f["nombre"], "email": f["email"]}
                  for f in filas if f["rol"] == "consultor" and f["activo"]]
    return jsonify({"directores": jefes, "candidatos": candidatos, "soy_titular": soy}), 200


@bp.route("/organizacion/titular", methods=["POST"])
@requiere_login
def transferir_titularidad():
    u = _director()
    _necesita("titular", "La titularidad")
    data = request.get_json(silent=True) or {}
    nuevo = data.get("usuario_id")
    if isinstance(nuevo, bool) or not isinstance(nuevo, int):
        raise ApiError(400, "Elija al director que será el titular.")
    empresa, params = condicion_empresa(u, "u")
    with cursor() as cur:
        _exigir_titular(cur, u)
        _confirmar_clave(cur, data.get("password"))
        cur.execute(f"SELECT u.id, u.nombre FROM usuarios u WHERE u.id=%s AND u.rol='jefe' AND {empresa}", (nuevo, *params))
        destino = cur.fetchone()
        if not destino or destino["id"] == u["id"]:
            raise ApiError(404, "Elija a otro director de proyectos de su consultora.")
        cur.execute("UPDATE organizaciones SET titular_id=%s WHERE id=%s", (nuevo, u["organizacion_id"]))
        auditoria.registrar(cur, u["organizacion_id"], u["id"], "titular_transferido", f"a {destino['nombre']}")
    return jsonify({"ok": True, "mensaje": f"{destino['nombre']} es ahora el titular de la cuenta."}), 200


@bp.route("/organizacion/directores/<int:usuario_id>/rol", methods=["POST"])
@requiere_login
def cambiar_rol(usuario_id):
    """El titular asciende a un consultor a director de proyectos, o devuelve a un director a consultor."""
    u = _director()
    data = request.get_json(silent=True) or {}
    rol = data.get("rol")
    if rol not in ("jefe", "consultor"):
        raise ApiError(400, "El rol debe ser director de proyectos o consultor.")
    empresa, params = condicion_empresa(u, "u")
    activo = "u.activo" if _esquema["activo"] else "1"
    with cursor() as cur:
        _exigir_titular(cur, u)
        cur.execute(f"SELECT u.id, u.nombre, u.rol, {activo} AS activo FROM usuarios u "
                    f"WHERE u.id=%s AND u.rol IN ('jefe', 'consultor') AND {empresa}", (usuario_id, *params))
        p = cur.fetchone()
        if not p:
            raise ApiError(404, "Persona no encontrada en su consultora.")
        if p["rol"] == rol:
            raise ApiError(409, "Ya tiene ese rol.")
        if rol == "jefe" and not p["activo"]:
            raise ApiError(409, "Reactive a la persona antes de ascenderla.")
        if rol == "consultor":
            cur.execute("SELECT titular_id FROM organizaciones WHERE id=%s", (u["organizacion_id"],)) if _esquema["titular"] else None
            if _esquema["titular"] and (cur.fetchone() or {}).get("titular_id") == p["id"]:
                raise ApiError(409, "El titular no puede pasar a consultor: transfiera primero la titularidad.")
        sets = "rol=%s" + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (rol, usuario_id))  # sus sesiones se renuevan con el rol nuevo
        auditoria.registrar(cur, u["organizacion_id"], u["id"], "rol_cambiado",
                            f"{p['nombre']}: {'director de proyectos' if rol == 'jefe' else 'consultor'}")
    return jsonify({"ok": True, "mensaje": f"{p['nombre']} ahora es " +
                    ("director de proyectos." if rol == "jefe" else "consultor.")}), 200
