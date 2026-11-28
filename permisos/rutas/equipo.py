"""El jefe gestiona el equipo de consultores de su empresa (alta, baja, reasignacion y clave).

- Alta: el jefe da nombre y correo. La app genera una contrasena temporal que
  se muestra una sola vez (igual que la cuenta del promotor); si el jefe manda
  una propia, debe cumplir la politica del Sprint 6. En los dos casos el
  consultor debe cambiarla en su primer ingreso.
- Baja logica: el consultor queda desactivado, no se borra. No puede iniciar
  sesion y su sesion abierta deja de valer; sus expedientes y su historial se
  conservan. Se puede reactivar.
- Reasignacion: los expedientes de un consultor desactivado pasan a otro
  activo. Cada expediente queda en el historial como "reasigno", a nombre del jefe.

- Restablecer clave: si un consultor olvido la suya, el jefe le genera una temporal.

Solo el jefe, y solo sobre los consultores de su propia empresa; cualquier otro rol recibe 403.
"""
from functools import wraps

import pymysql
from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from .. import auditoria
from ..bd import _esquema, col_activo, cursor, registrar_historial
from ..config import ACCION_REASIGNAR, EMAIL_RE
from ..errores import ApiError
from ..reglas import problema_de_password
from ..seguridad import condicion_empresa, requiere_login
from ..utiles import texto
from ..reglas import plural
from .expedientes import contrasena_temporal

bp = Blueprint("equipo", __name__)


def requiere_jefe(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        if g.usuario["rol"] != "jefe":
            raise ApiError(403, "Solo el director de proyectos gestiona a los consultores.")
        return f(*args, **kwargs)
    return envoltura


def cargar_consultor(cur, consultor_id):
    empresa, params = condicion_empresa(g.usuario, "u")
    cur.execute(f"SELECT id, nombre, email, {col_activo()} FROM usuarios u "
                f"WHERE u.id=%s AND u.rol='consultor' AND {empresa}", [consultor_id, *params])
    c = cur.fetchone()
    if not c:
        raise ApiError(404, "Consultor no encontrado.")
    return c


@bp.route("/consultores", methods=["GET"])
@requiere_login
@requiere_jefe
def listar_consultores():
    activo = "u.activo" if _esquema["activo"] else "1 AS activo"
    empresa, params = condicion_empresa(g.usuario, "u")
    with cursor() as cur:
        cur.execute(f"""SELECT u.id, u.nombre, u.email, u.fecha_creacion, {activo},
                               (SELECT COUNT(*) FROM expedientes e WHERE e.usuario_id = u.id) AS expedientes
                        FROM usuarios u WHERE u.rol = 'consultor' AND {empresa}""", params)
        filas = cur.fetchall()
    consultores = [{
        "id": c["id"],
        "nombre": c["nombre"],
        "email": c["email"],
        "activo": bool(c["activo"]),
        "expedientes": c["expedientes"],
        "fecha_creacion": c["fecha_creacion"].strftime("%Y-%m-%d") if c["fecha_creacion"] else None,
    } for c in filas]
    # Activos primero; dentro de cada grupo, por nombre.
    consultores.sort(key=lambda c: (not c["activo"], c["nombre"].lower(), c["id"]))
    return jsonify({"consultores": consultores})


@bp.route("/consultores", methods=["POST"])
@requiere_login
@requiere_jefe
def crear_consultor():
    data = request.get_json(silent=True) or {}
    nombre = texto(data, "nombre", 255, obligatorio=False)
    email = texto(data, "email", 255, obligatorio=False).lower()
    password = data.get("password") or None
    if not nombre or not email:
        raise ApiError(400, "Nombre y correo son obligatorios.")
    if not EMAIL_RE.match(email):
        raise ApiError(400, "El correo no es valido.")
    if password is not None:
        problema = problema_de_password(password)  # politica del Sprint 6
        if problema:
            raise ApiError(400, problema)
    temporal = password or contrasena_temporal()

    try:
        with cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                raise ApiError(409, "Ese correo ya está registrado.")
            columna, marca = (", debe_cambiar_clave", ", TRUE") if _esquema["cambio_clave"] else ("", "")
            if _esquema["org"]:
                columna, marca = columna + ", organizacion_id", marca + ", %s"
            cur.execute(f"INSERT INTO usuarios (nombre, email, password_hash, rol{columna}) "
                        f"VALUES (%s, %s, %s, 'consultor'{marca})",
                        (nombre, email, generate_password_hash(temporal),
                         *((g.usuario["organizacion_id"],) if _esquema["org"] else ())))
            nuevo_id = cur.lastrowid
            auditoria.registrar(cur, g.usuario.get("organizacion_id"), g.usuario["id"], "equipo_alta", nombre, email=email)
    except pymysql.err.IntegrityError:
        raise ApiError(409, "Ese correo ya está registrado.")

    respuesta = {"ok": True, "id": nuevo_id, "email": email,
                 "mensaje": f"Se dio de alta a {nombre} como consultor. Deberá cambiar la contraseña en su "
                            "primer ingreso."}
    if password is None:
        # Igual que la cuenta del promotor: la temporal se muestra una sola vez.
        respuesta["password_temporal"] = temporal
    return jsonify(respuesta), 201


def cambiar_activo(consultor_id, activo):
    if not _esquema["activo"]:
        raise ApiError(503, "La base aún no tiene la columna usuarios.activo. Ver sql/sprint9_manual.sql.")
    with cursor() as cur:
        c = cargar_consultor(cur, consultor_id)
        if bool(c["activo"]) == activo:
            raise ApiError(409, "El consultor ya está activo." if activo else "El consultor ya está desactivado.")
        cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (activo, consultor_id))
        auditoria.registrar(cur, g.usuario.get("organizacion_id"), g.usuario["id"],
                            "equipo_activado" if activo else "equipo_desactivado", c["nombre"])
    return c


@bp.route("/consultores/<int:consultor_id>/desactivar", methods=["POST"])
@requiere_login
@requiere_jefe
def desactivar_consultor(consultor_id):
    c = cambiar_activo(consultor_id, False)
    return jsonify({"ok": True, "mensaje": f"{c['nombre']} quedó desactivado y ya no puede iniciar sesión."}), 200


@bp.route("/consultores/<int:consultor_id>/activar", methods=["POST"])
@requiere_login
@requiere_jefe
def activar_consultor(consultor_id):
    c = cambiar_activo(consultor_id, True)
    return jsonify({"ok": True,
                    "mensaje": f"{c['nombre']} quedó reactivado y puede volver a iniciar sesión."}), 200


@bp.route("/consultores/<int:consultor_id>/reasignar", methods=["POST"])
@requiere_login
@requiere_jefe
def reasignar_expedientes(consultor_id):
    data = request.get_json(silent=True) or {}
    try:
        destino_id = int(data.get("destino_id"))
    except (TypeError, ValueError):
        raise ApiError(400, "Indica el consultor que recibe los expedientes (destino_id).")

    with cursor() as cur:
        origen = cargar_consultor(cur, consultor_id)
        if origen["activo"]:
            raise ApiError(409, "Primero desactiva al consultor: solo se reasignan los expedientes de "
                                "consultores dados de baja.")
        if destino_id == consultor_id:
            raise ApiError(400, "El consultor de destino debe ser otro.")
        empresa, params = condicion_empresa(g.usuario, "u")
        cur.execute(f"SELECT id, nombre, {col_activo()} FROM usuarios u WHERE u.id=%s AND u.rol='consultor' "
                    f"AND {empresa}", [destino_id, *params])
        destino = cur.fetchone()
        if not destino:
            raise ApiError(400, "El consultor de destino no existe.")
        if not destino["activo"]:
            raise ApiError(400, "El consultor de destino está desactivado.")

        cur.execute("SELECT id FROM expedientes WHERE usuario_id=%s", (consultor_id,))
        ids = [e["id"] for e in cur.fetchall()]
        if ids:
            cur.execute("UPDATE expedientes SET usuario_id=%s WHERE usuario_id=%s", (destino_id, consultor_id))
            for exp_id in ids:
                registrar_historial(cur, exp_id, g.usuario["id"], ACCION_REASIGNAR)
        auditoria.registrar(cur, g.usuario.get("organizacion_id"), g.usuario["id"], "equipo_reasignado",
                            f"{len(ids)} de {origen['nombre']} a {destino['nombre']}")

    return jsonify({"ok": True, "reasignados": len(ids),
                    "mensaje": f"{plural(len(ids), 'expediente', 'expedientes')} de {origen['nombre']} "
                               f"{'pasó' if len(ids) == 1 else 'pasaron'} a {destino['nombre']}."}), 200


@bp.route("/consultores/<int:consultor_id>/restablecer-clave", methods=["POST"])
@requiere_login
@requiere_jefe
def restablecer_clave_consultor(consultor_id):
    """El consultor olvido su contrasena: el jefe le genera una temporal (se muestra una
    sola vez). La clave anterior deja de valer y sus sesiones abiertas se cierran."""
    temporal = contrasena_temporal()
    with cursor() as cur:
        c = cargar_consultor(cur, consultor_id)
        sets = "password_hash=%s" + (", debe_cambiar_clave=TRUE" if _esquema["cambio_clave"] else "") \
            + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "") \
            + (", totp_activo=FALSE, totp_secreto=NULL, totp_ultimo_paso=0" if _esquema["totp"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (generate_password_hash(temporal), consultor_id))
        auditoria.registrar(cur, g.usuario.get("organizacion_id"), g.usuario["id"], "clave_restablecida", c["nombre"])
    return jsonify({"ok": True, "email": c["email"], "password_temporal": temporal,
                    "mensaje": f"Entregue esta contraseña a {c['nombre']} por un canal seguro. Se muestra una sola "
                               "vez y deberá cambiarla en su próximo ingreso."}), 200
