"""Invitaciones: la unica forma de crear una cuenta nueva.

El jefe invita a los consultores de su empresa; el administrador de la plataforma
invita al jefe de cada empresa nueva. La invitacion es un enlace de un solo uso que
vence (INVITACION_HORAS). Solo se guarda su SHA-256: el enlace se muestra una vez,
al crearla, y quien la crea se lo entrega a la persona por el canal que prefiera.
"""
import secrets
from datetime import timedelta

from flask import Blueprint, g, jsonify, request

from .. import limitador
from ..bd import cursor
from ..config import EMAIL_RE, INVITACION_HORAS, ROL_ADMIN
from ..errores import ApiError
from ..reglas import ahora
from ..seguridad import requiere_login
from ..utiles import texto
from .auth import hash_token

bp = Blueprint("invitaciones", __name__)


def nueva_invitacion(cur, organizacion_id, rol, creada_por, email=None):
    """Crea la invitacion y devuelve el token en claro (no se puede volver a ver)."""
    token = secrets.token_urlsafe(24)
    ahora_ = ahora()
    expira = ahora_ + timedelta(hours=INVITACION_HORAS)
    cur.execute("INSERT INTO invitaciones (token_hash, organizacion_id, rol, email, creada_por, "
                "fecha_creacion, expira) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (hash_token(token), organizacion_id, rol, email or None, creada_por, ahora_, expira))
    return token, expira


def _enlace(token):
    return f"{request.host_url.rstrip('/')}/registro.html?invitacion={token}"


def _estado(i, ahora_):
    if i["usada_en"]:
        return "usada"
    if i["revocada"]:
        return "revocada"
    return "vencida" if i["expira"] < ahora_ else "pendiente"


@bp.route("/invitaciones", methods=["POST"])
@requiere_login
def crear():
    u = g.usuario
    data = request.get_json(silent=True) or {}
    email = texto(data, "email", 255, obligatorio=False).lower()
    if email and not EMAIL_RE.match(email):
        raise ApiError(400, "El correo no es valido.")

    if u["rol"] == "jefe":
        organizacion_id, rol = u["organizacion_id"], "consultor"
    elif u["rol"] == ROL_ADMIN:
        # El administrador invita al jefe de una empresa que ya existe.
        organizacion_id, rol = data.get("organizacion_id"), "jefe"
        if isinstance(organizacion_id, bool) or not isinstance(organizacion_id, int):
            raise ApiError(400, "Indique la empresa a la que pertenecerá el jefe.")
    else:
        raise ApiError(403, "Solo el jefe de la consultora puede invitar a su equipo.")

    with cursor() as cur:
        cur.execute("SELECT activa FROM organizaciones WHERE id=%s", (organizacion_id,))
        org = cur.fetchone()
        if not org or not org["activa"]:
            raise ApiError(404, "Empresa no encontrada o desactivada.")
        if email:
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                raise ApiError(409, "Ese correo ya tiene una cuenta.")
        token, expira = nueva_invitacion(cur, organizacion_id, rol, u["id"], email)
    return jsonify({"ok": True, "enlace": _enlace(token), "token": token, "rol": rol,
                    "expira": expira.strftime("%d/%m/%Y %H:%M"),
                    "mensaje": f"Comparta este enlace con la persona invitada. Es de un solo uso, vence en "
                               f"{INVITACION_HORAS} horas y no se vuelve a mostrar."}), 201


@bp.route("/invitaciones", methods=["GET"])
@requiere_login
def listar():
    u = g.usuario
    if u["rol"] not in ("jefe", ROL_ADMIN):
        raise ApiError(403, "Solo el jefe de la consultora puede ver las invitaciones.")
    if u["rol"] == "jefe":
        donde, params = "i.organizacion_id=%s", [u["organizacion_id"]]
    else:
        donde, params = "1=1", []
    with cursor() as cur:
        cur.execute(f"""SELECT i.id, i.rol, i.email, i.fecha_creacion, i.expira, i.usada_en, i.revocada,
                               o.nombre AS empresa, uu.nombre AS usada_por
                        FROM invitaciones i
                        JOIN organizaciones o ON o.id = i.organizacion_id
                        LEFT JOIN usuarios uu ON uu.id = i.usada_por
                        WHERE {donde} ORDER BY i.id DESC LIMIT 100""", params)
        filas = cur.fetchall()
    ahora_ = ahora()
    for i in filas:
        i["estado"] = _estado(i, ahora_)
        for campo in ("fecha_creacion", "expira", "usada_en"):
            i[campo] = i[campo].strftime("%d/%m/%Y %H:%M") if i[campo] else None
    return jsonify({"invitaciones": filas}), 200


@bp.route("/invitaciones/<int:invitacion_id>", methods=["DELETE"])
@requiere_login
def revocar(invitacion_id):
    u = g.usuario
    if u["rol"] not in ("jefe", ROL_ADMIN):
        raise ApiError(403, "No autorizado.")
    with cursor() as cur:
        cur.execute("SELECT id, organizacion_id, usada_en FROM invitaciones WHERE id=%s", (invitacion_id,))
        i = cur.fetchone()
        # Una invitacion de otra empresa responde igual que una inexistente.
        if not i or (u["rol"] == "jefe" and i["organizacion_id"] != u["organizacion_id"]):
            raise ApiError(404, "Invitación no encontrada.")
        if i["usada_en"]:
            raise ApiError(409, "Esa invitación ya se usó.")
        cur.execute("UPDATE invitaciones SET revocada=TRUE WHERE id=%s", (invitacion_id,))
    return jsonify({"ok": True, "mensaje": "Invitación revocada."}), 200


@bp.route("/invitaciones/validar", methods=["GET"])
def validar():
    """Publica: la pantalla de registro la usa para decir a que empresa se une la persona."""
    token = (request.args.get("token") or "").strip()
    clave = (request.remote_addr, "invitacion")
    if limitador.bloqueado(clave):
        raise ApiError(429, "Demasiados intentos. Espere un minuto.")
    with cursor() as cur:
        cur.execute("""SELECT i.rol, i.email, i.expira, i.usada_en, i.revocada, o.nombre AS empresa, o.activa
                       FROM invitaciones i JOIN organizaciones o ON o.id = i.organizacion_id
                       WHERE i.token_hash=%s""", (hash_token(token),))
        i = token and cur.fetchone()
    if not i or i["usada_en"] or i["revocada"] or i["expira"] < ahora() or not i["activa"]:
        limitador.anotar_fallo(clave)
        raise ApiError(404, "La invitación no es válida, ya se usó o venció.")
    return jsonify({"ok": True, "empresa": i["empresa"], "rol": i["rol"], "email": i["email"]}), 200
