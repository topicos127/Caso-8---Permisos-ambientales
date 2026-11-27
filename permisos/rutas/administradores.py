"""Administradores de la plataforma: quien puede crear empresas, ver el servicio y restaurar respaldos.

Un administrador se une por invitacion (enlace de un solo uso, igual que el resto de las cuentas):
no hay otra forma de crear uno despues del primero, que sale de ADMIN_EMAIL al arrancar. Todos tienen
los mismos permisos, asi que las reglas protegen lo que no debe perderse:
  - nadie se desactiva a si mismo ni se restablece su propio acceso (lo hace desde "Mi perfil");
  - la plataforma nunca se queda sin un administrador activo.
Cada paso queda en el registro de la plataforma (eventos sin empresa).
"""
from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from .. import auditoria
from ..bd import _esquema, col_activo, cursor
from ..config import ADMIN_DOMINIOS, EMAIL_RE, INVITACION_HORAS, ROL_ADMIN, correo_en_dominios, mensaje_dominios
from ..errores import ApiError
from ..reglas import ahora
from ..seguridad import requiere_admin
from ..utiles import texto
from .expedientes import contrasena_temporal
from .invitaciones import _enlace, _estado, nueva_invitacion

bp = Blueprint("administradores", __name__)

# Eventos que le interesan a la administracion: los de gestion de administradores y los accesos de estas cuentas.
EVENTOS_VISIBLES = 40


def _fecha(valor):
    return valor.strftime("%d/%m/%Y %H:%M") if valor else None


def _exigir_tabla_lista():
    if not _esquema["activo"]:
        raise ApiError(503, "Falta la columna usuarios.activo; reinicie la aplicación para que se cree.")


def _administrador(cur, usuario_id):
    cur.execute(f"SELECT id, nombre, email, rol, {col_activo()} FROM usuarios WHERE id=%s", (usuario_id,))
    a = cur.fetchone()
    if not a or a["rol"] != ROL_ADMIN:
        raise ApiError(404, "Administrador no encontrado.")
    return a


def _activos(cur):
    cur.execute("SELECT COUNT(*) AS n FROM usuarios WHERE rol=%s AND activo", (ROL_ADMIN,))
    return cur.fetchone()["n"]


@bp.route("/plataforma/administradores", methods=["GET"])
@requiere_admin
def listar():
    with cursor() as cur:
        cur.execute(f"""SELECT u.id, u.nombre, u.email, {'u.activo' if _esquema['activo'] else '1 AS activo'}, u.fecha_creacion,
                               {'u.totp_activo' if _esquema['totp'] else '0 AS totp_activo'},
                               (SELECT MAX(e.fecha) FROM eventos_cuenta e
                                 WHERE e.usuario_id = u.id AND e.tipo = 'acceso') AS ultimo_acceso
                        FROM usuarios u WHERE u.rol=%s ORDER BY u.id""", (ROL_ADMIN,))
        admins = cur.fetchall()
        cur.execute("""SELECT i.id, i.email, i.fecha_creacion, i.expira, i.usada_en, i.revocada, c.nombre AS creada_por
                       FROM invitaciones i JOIN usuarios c ON c.id = i.creada_por
                       WHERE i.rol=%s ORDER BY i.id DESC LIMIT 30""", (ROL_ADMIN,))
        invitaciones = cur.fetchall()
        cur.execute("""SELECT e.tipo, e.detalle, e.email, e.ip, e.fecha, u.nombre
                       FROM eventos_cuenta e LEFT JOIN usuarios u ON u.id = e.usuario_id
                       WHERE e.organizacion_id IS NULL ORDER BY e.id DESC LIMIT %s""", (EVENTOS_VISIBLES,))
        eventos = cur.fetchall()
    ahora_ = ahora()
    for a in admins:
        a["es_usted"] = a["id"] == g.usuario["id"]
        a["activo"] = bool(a["activo"])
        a["totp_activo"] = bool(a["totp_activo"])
        a["fecha_creacion"] = _fecha(a["fecha_creacion"])
        a["ultimo_acceso"] = _fecha(a["ultimo_acceso"])
    for i in invitaciones:
        i["estado"] = _estado(i, ahora_)
        for campo in ("fecha_creacion", "expira", "usada_en"):
            i[campo] = _fecha(i[campo])
    for e in eventos:
        e["texto"] = auditoria.TIPOS.get(e["tipo"], e["tipo"])
        e["fecha"] = _fecha(e["fecha"])
    return jsonify({"administradores": admins, "invitaciones": invitaciones, "eventos": eventos,
                    "activos": sum(1 for a in admins if a["activo"]), "dominios": list(ADMIN_DOMINIOS)}), 200


@bp.route("/plataforma/administradores/invitaciones", methods=["POST"])
@requiere_admin
def invitar():
    data = request.get_json(silent=True) or {}
    email = texto(data, "email", 255, obligatorio=False).lower()
    if email and not EMAIL_RE.match(email):
        raise ApiError(400, "El correo no es válido.")
    if email and not correo_en_dominios(email, ADMIN_DOMINIOS):
        raise ApiError(400, mensaje_dominios(ADMIN_DOMINIOS))
    with cursor() as cur:
        if email:
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                raise ApiError(409, "Ese correo ya tiene una cuenta.")
        token, expira = nueva_invitacion(cur, None, ROL_ADMIN, g.usuario["id"], email)
        auditoria.registrar(cur, None, g.usuario["id"], "admin_invitacion_creada", email or "sin correo fijo")
    return jsonify({"ok": True, "enlace": _enlace(token), "token": token, "expira": expira.strftime("%d/%m/%Y %H:%M"),
                    "mensaje": f"Comparta este enlace con la persona. Es de un solo uso, vence en {INVITACION_HORAS} "
                               "horas y no se vuelve a mostrar."}), 201


@bp.route("/plataforma/administradores/invitaciones/<int:invitacion_id>", methods=["DELETE"])
@requiere_admin
def revocar(invitacion_id):
    with cursor() as cur:
        cur.execute("SELECT id, rol, usada_en FROM invitaciones WHERE id=%s", (invitacion_id,))
        i = cur.fetchone()
        if not i or i["rol"] != ROL_ADMIN:
            raise ApiError(404, "Invitación no encontrada.")
        if i["usada_en"]:
            raise ApiError(409, "Esa invitación ya se usó.")
        cur.execute("UPDATE invitaciones SET revocada=TRUE WHERE id=%s", (invitacion_id,))
        auditoria.registrar(cur, None, g.usuario["id"], "admin_invitacion_revocada", "")
    return jsonify({"ok": True, "mensaje": "Invitación revocada."}), 200


@bp.route("/plataforma/administradores/<int:usuario_id>/activo", methods=["POST"])
@requiere_admin
def cambiar_estado(usuario_id):
    _exigir_tabla_lista()
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("activo"), bool):
        raise ApiError(400, "Indique si la cuenta debe quedar activa.")
    activar = data["activo"]
    if usuario_id == g.usuario["id"]:
        raise ApiError(409, "No puede desactivar su propia cuenta. Pídaselo a otro administrador.")
    with cursor() as cur:
        a = _administrador(cur, usuario_id)
        if not activar and a["activo"] and _activos(cur) <= 1:
            raise ApiError(409, "La plataforma no puede quedarse sin un administrador activo.")
        sets = "activo=%s" + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (activar, usuario_id))
        auditoria.registrar(cur, None, g.usuario["id"], "admin_activado" if activar else "admin_desactivado",
                            a["email"])
    return jsonify({"ok": True, "mensaje": f"{a['nombre']} {'reactivado' if activar else 'desactivado'}. "
                    + ("" if activar else "Sus sesiones abiertas dejaron de valer.")}), 200


@bp.route("/plataforma/administradores/<int:usuario_id>/restablecer", methods=["POST"])
@requiere_admin
def restablecer(usuario_id):
    """Otro administrador perdio su contrasena y sus codigos: se le genera una temporal y se le quitan los dos pasos."""
    if usuario_id == g.usuario["id"]:
        raise ApiError(409, "Su propia contraseña se cambia desde «Mi perfil».")
    temporal = contrasena_temporal()
    with cursor() as cur:
        a = _administrador(cur, usuario_id)
        sets = "password_hash=%s" + (", debe_cambiar_clave=TRUE" if _esquema["cambio_clave"] else "") \
            + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "") \
            + (", totp_activo=FALSE, totp_secreto=NULL, totp_ultimo_paso=0" if _esquema["totp"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (generate_password_hash(temporal), usuario_id))
        auditoria.registrar(cur, None, g.usuario["id"], "admin_clave_restablecida", a["email"])
    return jsonify({"ok": True, "email": a["email"], "password_temporal": temporal,
                    "mensaje": f"Entregue esta contraseña a {a['nombre']} por un canal seguro. Se muestra una sola vez; "
                               "deberá cambiarla al entrar y volver a activar sus dos pasos."}), 200
