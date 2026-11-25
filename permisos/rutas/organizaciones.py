"""Empresas: la marca propia de cada consultora y la administracion de la plataforma.

- El jefe edita el nombre, el color y el logo de SU empresa.
- El administrador de la plataforma crea empresas (con la invitacion para su jefe),
  las activa o desactiva y restablece el acceso de un jefe que quedo bloqueado.
  El administrador no ve expedientes ni documentos de ninguna empresa.
"""
import hashlib
from io import BytesIO

import pymysql
from flask import Blueprint, g, jsonify, request, send_file
from werkzeug.security import generate_password_hash

from ..almacenamiento import AlmacenamientoError, almacen
from ..bd import _esquema, cursor
from ..config import COLORES_EMPRESA, EMAIL_RE, ROL_ADMIN
from ..empresas import datos_empresa
from ..errores import ApiError
from ..seguridad import requiere_admin, requiere_login
from ..utiles import texto
from .expedientes import contrasena_temporal
from .invitaciones import _enlace, nueva_invitacion

bp = Blueprint("organizaciones", __name__)

LOGO_MAX_BYTES = 1024 * 1024  # 1 MB
TIPOS_LOGO = {  # firma del archivo -> (extension, tipo MIME). SVG no: puede llevar scripts.
    b"\x89PNG\r\n\x1a\n": ("png", "image/png"),
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
}


def _tipo_logo(datos):
    for firma, tipo in TIPOS_LOGO.items():
        if datos.startswith(firma):
            return tipo
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def _validar_color(color):
    if color not in COLORES_EMPRESA:
        raise ApiError(400, "Elija un color de la paleta.")
    return color


def _exigir_empresa_propia(u):
    if not _esquema["org"]:
        raise ApiError(503, "Las empresas aún no están disponibles: falta actualizar la base de datos.")
    if u["rol"] == ROL_ADMIN or u.get("organizacion_id") is None:
        raise ApiError(403, "Esta cuenta no pertenece a una consultora.")


# ---------- La empresa del usuario ----------

@bp.route("/organizacion", methods=["GET"])
@requiere_login
def mi_empresa():
    _exigir_empresa_propia(g.usuario)
    with cursor() as cur:
        empresa = datos_empresa(cur, g.usuario["organizacion_id"])
    return jsonify({"empresa": empresa, "colores": list(COLORES_EMPRESA),
                    "puede_editar": g.usuario["rol"] == "jefe"}), 200


@bp.route("/organizacion", methods=["POST"])
@requiere_login
def editar_empresa():
    u = g.usuario
    _exigir_empresa_propia(u)
    if u["rol"] != "jefe":
        raise ApiError(403, "Solo el jefe de la consultora puede cambiar la marca de la empresa.")
    data = request.get_json(silent=True) or {}
    sets, params = [], []
    if "nombre" in data:
        nombre = texto(data, "nombre", 150)
        if len(nombre) < 3:
            raise ApiError(400, "El nombre debe tener al menos 3 caracteres.")
        sets.append("nombre=%s")
        params.append(nombre)
    if "color" in data:
        sets.append("color=%s")
        params.append(_validar_color(data["color"]))
    if not sets:
        raise ApiError(400, "No hay nada que cambiar.")
    try:
        with cursor() as cur:
            cur.execute(f"UPDATE organizaciones SET {', '.join(sets)} WHERE id=%s", (*params, u["organizacion_id"]))
            empresa = datos_empresa(cur, u["organizacion_id"])
    except pymysql.err.IntegrityError:
        raise ApiError(409, "Ya existe una empresa con ese nombre.")
    return jsonify({"ok": True, "empresa": empresa, "mensaje": "Marca de la empresa actualizada."}), 200


@bp.route("/organizacion/logo", methods=["POST"])
@requiere_login
def subir_logo():
    u = g.usuario
    _exigir_empresa_propia(u)
    if u["rol"] != "jefe":
        raise ApiError(403, "Solo el jefe de la consultora puede cambiar el logo.")
    archivo = request.files.get("logo")
    if not archivo or not archivo.filename:
        raise ApiError(400, "Seleccione una imagen.")
    datos = archivo.read(LOGO_MAX_BYTES + 1)
    if len(datos) > LOGO_MAX_BYTES:
        raise ApiError(400, "El logo no puede superar 1 MB.")
    tipo = _tipo_logo(datos)
    if not tipo:
        raise ApiError(400, "El logo debe ser una imagen PNG, JPG o WebP.")
    ruta = f"organizaciones/{u['organizacion_id']}/logo-{hashlib.sha256(datos).hexdigest()[:10]}.{tipo[0]}"
    try:
        almacen().guardar(ruta, datos)
    except AlmacenamientoError as e:
        raise ApiError(503, str(e))
    with cursor() as cur:
        cur.execute("SELECT logo_ruta FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
        anterior = cur.fetchone()["logo_ruta"]
        cur.execute("UPDATE organizaciones SET logo_ruta=%s WHERE id=%s", (ruta, u["organizacion_id"]))
        empresa = datos_empresa(cur, u["organizacion_id"])
    if anterior and anterior != ruta:
        almacen().borrar(anterior)
    return jsonify({"ok": True, "empresa": empresa, "mensaje": "Logo actualizado."}), 200


@bp.route("/organizacion/logo", methods=["DELETE"])
@requiere_login
def quitar_logo():
    u = g.usuario
    _exigir_empresa_propia(u)
    if u["rol"] != "jefe":
        raise ApiError(403, "Solo el jefe de la consultora puede cambiar el logo.")
    with cursor() as cur:
        cur.execute("SELECT logo_ruta FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
        anterior = cur.fetchone()["logo_ruta"]
        cur.execute("UPDATE organizaciones SET logo_ruta=NULL WHERE id=%s", (u["organizacion_id"],))
    if anterior:
        almacen().borrar(anterior)
    return jsonify({"ok": True, "mensaje": "Logo eliminado."}), 200


@bp.route("/organizacion/logo/<int:org_id>", methods=["GET"])
def ver_logo(org_id):
    """Publico a proposito: el logo tambien sale en la consulta publica del promotor."""
    if not _esquema["org"]:
        raise ApiError(404, "Sin logo.")
    with cursor() as cur:
        cur.execute("SELECT logo_ruta FROM organizaciones WHERE id=%s", (org_id,))
        fila = cur.fetchone()
    ruta = fila and fila["logo_ruta"]
    datos = almacen().leer(ruta) if ruta else None
    tipo = _tipo_logo(datos) if datos else None
    if not tipo:
        raise ApiError(404, "Sin logo.")
    resp = send_file(BytesIO(datos), mimetype=tipo[1])
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ---------- Administracion de la plataforma ----------

@bp.route("/plataforma/empresas", methods=["GET"])
@requiere_admin
def listar_empresas():
    with cursor() as cur:
        cur.execute("""SELECT o.id, o.nombre, o.color, o.activa, o.fecha_creacion,
                              (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id) AS usuarios,
                              (SELECT COUNT(*) FROM expedientes e WHERE e.organizacion_id = o.id) AS expedientes,
                              (SELECT u.id FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol='jefe'
                                 ORDER BY u.id LIMIT 1) AS jefe_id,
                              (SELECT u.email FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol='jefe'
                                 ORDER BY u.id LIMIT 1) AS jefe_email
                       FROM organizaciones o ORDER BY o.id""")
        filas = cur.fetchall()
    for f in filas:
        f["activa"] = bool(f["activa"])
        f["fecha_creacion"] = f["fecha_creacion"].strftime("%d/%m/%Y")
    return jsonify({"empresas": filas, "colores": list(COLORES_EMPRESA)}), 200


@bp.route("/plataforma/empresas", methods=["POST"])
@requiere_admin
def crear_empresa():
    data = request.get_json(silent=True) or {}
    nombre = texto(data, "nombre", 150)
    if len(nombre) < 3:
        raise ApiError(400, "El nombre debe tener al menos 3 caracteres.")
    color = _validar_color(data.get("color", COLORES_EMPRESA[0]))
    email = texto(data, "email_jefe", 255, obligatorio=False).lower()
    if email and not EMAIL_RE.match(email):
        raise ApiError(400, "El correo del jefe no es válido.")
    try:
        with cursor() as cur:
            if email:
                cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
                if cur.fetchone():
                    raise ApiError(409, "Ese correo ya tiene una cuenta.")
            cur.execute("INSERT INTO organizaciones (nombre, color) VALUES (%s, %s)", (nombre, color))
            org_id = cur.lastrowid
            token, expira = nueva_invitacion(cur, org_id, "jefe", g.usuario["id"], email)
    except pymysql.err.IntegrityError:
        raise ApiError(409, "Ya existe una empresa con ese nombre.")
    return jsonify({"ok": True, "id": org_id, "enlace": _enlace(token), "expira": expira.strftime("%d/%m/%Y %H:%M"),
                    "mensaje": "Empresa creada. Entregue el enlace de invitación a su jefe: es de un solo uso "
                               "y no se vuelve a mostrar."}), 201


@bp.route("/plataforma/empresas/<int:org_id>/activa", methods=["POST"])
@requiere_admin
def activar_empresa(org_id):
    data = request.get_json(silent=True) or {}
    activa = data.get("activa")
    if not isinstance(activa, bool):
        raise ApiError(400, "Indique si la empresa queda activa o no.")
    with cursor() as cur:
        cur.execute("SELECT id FROM organizaciones WHERE id=%s", (org_id,))
        if not cur.fetchone():
            raise ApiError(404, "Empresa no encontrada.")
        cur.execute("UPDATE organizaciones SET activa=%s WHERE id=%s", (activa, org_id))
    return jsonify({"ok": True, "activa": activa,
                    "mensaje": "Empresa activada." if activa else
                    "Empresa desactivada: nadie de esa empresa puede entrar hasta reactivarla."}), 200


@bp.route("/plataforma/jefes/<int:usuario_id>/restablecer", methods=["POST"])
@requiere_admin
def restablecer_jefe(usuario_id):
    """El jefe perdio su contrasena y sus codigos: el administrador le genera una temporal y
    le quita la verificacion en dos pasos. Solo funciona sobre cuentas de jefe."""
    temporal = contrasena_temporal()
    with cursor() as cur:
        cur.execute("SELECT id, nombre, email, rol FROM usuarios WHERE id=%s", (usuario_id,))
        j = cur.fetchone()
        if not j or j["rol"] != "jefe":
            raise ApiError(404, "Jefe no encontrado.")
        sets = "password_hash=%s" + (", debe_cambiar_clave=TRUE" if _esquema["cambio_clave"] else "") \
            + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "") \
            + (", totp_activo=FALSE, totp_secreto=NULL, totp_ultimo_paso=0" if _esquema["totp"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (generate_password_hash(temporal), usuario_id))
    return jsonify({"ok": True, "email": j["email"], "password_temporal": temporal,
                    "mensaje": f"Entregue esta contraseña a {j['nombre']} por un canal seguro. Se muestra una "
                               "sola vez; deberá cambiarla al ingresar y volver a activar sus dos pasos."}), 200
