"""Seguridad de la cuenta: verificacion en dos pasos, codigos de recuperacion,
recuperar la contrasena sin correo y cerrar todas las sesiones.

Sin servicio de correo, la recuperacion funciona asi:
- el usuario guarda sus codigos de recuperacion (se muestran una sola vez) y con uno
  de ellos puede fijar una contrasena nueva aunque no recuerde la actual;
- si no los tiene, su jefe (o el administrador, en el caso del jefe) le genera una
  contrasena temporal.
Las acciones sensibles piden la contrasena actual aunque la sesion este abierta.
"""
from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .. import auditoria, limitador, totp
from ..bd import _esquema, col_sesion, col_totp, cursor
from ..config import CODIGOS_RECUPERACION, SESION_MINUTOS
from ..errores import ApiError
from ..reglas import ahora, problema_de_password
from ..seguridad import requiere_login

bp = Blueprint("cuenta", __name__)


def _confirmar_clave(cur, clave):
    """Exige la contrasena actual. Cuenta los fallos para que una sesion robada no sirva
    para adivinarla."""
    llave = ("confirmar", g.usuario["id"])
    if limitador.bloqueado(llave):
        raise ApiError(429, "Demasiados intentos. Espere un minuto.")
    cur.execute("SELECT password_hash FROM usuarios WHERE id=%s", (g.usuario["id"],))
    fila = cur.fetchone()
    if not isinstance(clave, str) or not clave or not fila or not check_password_hash(fila["password_hash"], clave):
        limitador.anotar_fallo(llave)
        raise ApiError(400, "La contraseña actual no es correcta.")
    limitador.limpiar(llave)


def _generar_codigos(cur, usuario_id):
    """Reemplaza los codigos sin usar por un juego nuevo y devuelve los codigos en claro."""
    cur.execute("DELETE FROM codigos_recuperacion WHERE usuario_id=%s AND usado_en IS NULL", (usuario_id,))
    codigos = []
    for _ in range(CODIGOS_RECUPERACION):
        codigo = totp.nuevo_codigo_recuperacion()
        cur.execute("INSERT INTO codigos_recuperacion (usuario_id, codigo_hash, fecha_creacion) VALUES (%s, %s, %s)",
                    (usuario_id, totp.hash_codigo(codigo), ahora()))
        codigos.append(codigo)
    return codigos


def _evento(tipo, cur):
    if _esquema["org"] and g.usuario.get("organizacion_id") is not None:
        auditoria.registrar(cur, g.usuario["organizacion_id"], g.usuario["id"], tipo)


def _exigir_totp():
    if not _esquema["totp"]:
        raise ApiError(503, "La verificación en dos pasos aún no está disponible: falta actualizar la base de datos.")


def _estado_dos_pasos(cur, usuario_id):
    cur.execute(f"SELECT {col_totp()} FROM usuarios WHERE id=%s", (usuario_id,))
    return cur.fetchone() or {}


@bp.route("/cuenta/seguridad", methods=["GET"])
@requiere_login
def seguridad():
    with cursor() as cur:
        t = _estado_dos_pasos(cur, g.usuario["id"])
        cur.execute("SELECT COUNT(*) AS n FROM codigos_recuperacion WHERE usuario_id=%s AND usado_en IS NULL",
                    (g.usuario["id"],))
        restantes = cur.fetchone()["n"]
        terminos = None
        if _esquema["terminos"]:
            cur.execute("SELECT terminos_aceptados_en FROM usuarios WHERE id=%s", (g.usuario["id"],))
            terminos = cur.fetchone()["terminos_aceptados_en"]
    return jsonify({"dos_pasos": bool(t.get("totp_activo")), "disponible": _esquema["totp"],
                    "codigos_restantes": restantes, "sesion_minutos": SESION_MINUTOS,
                    "terminos_aceptados": terminos.strftime("%d/%m/%Y") if terminos else None}), 200


@bp.route("/cuenta/2fa/preparar", methods=["POST"])
@requiere_login
def preparar_2fa():
    _exigir_totp()
    data = request.get_json(silent=True) or {}
    with cursor() as cur:
        _confirmar_clave(cur, data.get("password"))
        if _estado_dos_pasos(cur, g.usuario["id"]).get("totp_activo"):
            raise ApiError(409, "La verificación en dos pasos ya está activa.")
        secreto = totp.nuevo_secreto()
        cur.execute("UPDATE usuarios SET totp_secreto=%s, totp_activo=FALSE, totp_ultimo_paso=0 WHERE id=%s",
                    (totp.cifrar(secreto, current_app.secret_key), g.usuario["id"]))
    enlace = totp.uri(secreto, g.usuario["email"])
    return jsonify({"ok": True, "secreto": secreto, "uri": enlace, "qr": totp.qr_svg(enlace),
                    "mensaje": "Escanee el código con su aplicación autenticadora y escriba el código "
                               "de 6 dígitos para confirmar."}), 200


@bp.route("/cuenta/2fa/activar", methods=["POST"])
@requiere_login
def activar_2fa():
    _exigir_totp()
    data = request.get_json(silent=True) or {}
    with cursor() as cur:
        t = _estado_dos_pasos(cur, g.usuario["id"])
        if t.get("totp_activo"):
            raise ApiError(409, "La verificación en dos pasos ya está activa.")
        secreto = totp.descifrar(t.get("totp_secreto") or "", current_app.secret_key)
        if not secreto:
            raise ApiError(400, "Primero genere el código QR.")
        paso = totp.verificar(secreto, data.get("codigo"), 0)
        if paso is None:
            raise ApiError(400, "El código no es correcto. Revise la hora de su teléfono e intente de nuevo.")
        cur.execute("UPDATE usuarios SET totp_activo=TRUE, totp_ultimo_paso=%s WHERE id=%s", (paso, g.usuario["id"]))
        codigos = _generar_codigos(cur, g.usuario["id"])
        _evento("dos_pasos_activado", cur)
    return jsonify({"ok": True, "codigos": codigos,
                    "mensaje": "Verificación en dos pasos activada. Guarde estos códigos de recuperación: "
                               "no se vuelven a mostrar."}), 200


@bp.route("/cuenta/2fa/desactivar", methods=["POST"])
@requiere_login
def desactivar_2fa():
    _exigir_totp()
    data = request.get_json(silent=True) or {}
    with cursor() as cur:
        _confirmar_clave(cur, data.get("password"))
        t = _estado_dos_pasos(cur, g.usuario["id"])
        if not t.get("totp_activo"):
            raise ApiError(409, "La verificación en dos pasos no está activa.")
        codigo = data.get("codigo")
        if len(totp.normalizar_codigo(codigo)) == 10:
            gastados = cur.execute("UPDATE codigos_recuperacion SET usado_en=%s "
                                   "WHERE usuario_id=%s AND codigo_hash=%s AND usado_en IS NULL",
                                   (ahora(), g.usuario["id"], totp.hash_codigo(codigo)))
            valido = gastados == 1
        else:
            secreto = totp.descifrar(t.get("totp_secreto") or "", current_app.secret_key)
            valido = bool(secreto) and totp.verificar(secreto, codigo, t.get("totp_ultimo_paso") or 0) is not None
        if not valido:
            raise ApiError(400, "El código no es correcto.")
        cur.execute("UPDATE usuarios SET totp_activo=FALSE, totp_secreto=NULL, totp_ultimo_paso=0 WHERE id=%s",
                    (g.usuario["id"],))
        _evento("dos_pasos_desactivado", cur)
    return jsonify({"ok": True, "mensaje": "Verificación en dos pasos desactivada."}), 200


@bp.route("/cuenta/codigos-recuperacion", methods=["POST"])
@requiere_login
def regenerar_codigos():
    data = request.get_json(silent=True) or {}
    with cursor() as cur:
        _confirmar_clave(cur, data.get("password"))
        codigos = _generar_codigos(cur, g.usuario["id"])
        _evento("codigos_regenerados", cur)
    return jsonify({"ok": True, "codigos": codigos,
                    "mensaje": "Códigos nuevos. Los anteriores dejaron de valer y estos no se vuelven a mostrar."}), 200


@bp.route("/cuenta/cerrar-sesiones", methods=["POST"])
@requiere_login
def cerrar_sesiones():
    """Cierra la sesion en todos los dispositivos menos este (por ejemplo, tras perder el telefono)."""
    if not _esquema["sesion"]:
        raise ApiError(503, "Aún no está disponible: falta actualizar la base de datos.")
    data = request.get_json(silent=True) or {}
    with cursor() as cur:
        _confirmar_clave(cur, data.get("password"))
        cur.execute("UPDATE usuarios SET sesion_version = sesion_version + 1 WHERE id=%s", (g.usuario["id"],))
        cur.execute(f"SELECT {col_sesion()} FROM usuarios WHERE id=%s", (g.usuario["id"],))
        session["sv"] = int(cur.fetchone()["sesion_version"])
    return jsonify({"ok": True, "mensaje": "Se cerró la sesión en los demás dispositivos."}), 200


@bp.route("/cuenta/terminos", methods=["POST"])
@requiere_login
def aceptar_terminos():
    if _esquema["terminos"]:
        with cursor() as cur:
            cur.execute("UPDATE usuarios SET terminos_aceptados_en=%s WHERE id=%s", (ahora(), g.usuario["id"]))
    return jsonify({"ok": True, "mensaje": "Gracias. Quedó registrada su aceptación."}), 200


@bp.route("/recuperar", methods=["POST"])
def recuperar():
    """Fija una contrasena nueva con un codigo de recuperacion (sin correo). Cada codigo vale una vez."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    codigo = data.get("codigo", "")
    nueva = data.get("password", "")
    if not email or not codigo or not nueva:
        raise ApiError(400, "Ingrese su correo, un código de recuperación y la contraseña nueva.")
    if not isinstance(nueva, str):
        raise ApiError(400, "La contraseña debe ser texto.")
    problema = problema_de_password(nueva)
    if problema:
        raise ApiError(400, problema)

    llaves = [(request.remote_addr, email), (request.remote_addr, "recuperar")]
    if any(limitador.bloqueado(k) for k in llaves):
        raise ApiError(429, "Demasiados intentos. Espere un minuto e intente de nuevo.")

    with cursor() as cur:
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        u = cur.fetchone()
        gastados = 0
        if u:
            # Atomico: dos peticiones con el mismo codigo no pasan las dos.
            gastados = cur.execute("UPDATE codigos_recuperacion SET usado_en=%s "
                                   "WHERE usuario_id=%s AND codigo_hash=%s AND usado_en IS NULL",
                                   (ahora(), u["id"], totp.hash_codigo(codigo)))
        if gastados != 1:
            for k in llaves:
                limitador.anotar_fallo(k)
            raise ApiError(400, "El correo o el código de recuperación no son correctos.")
        sets = "password_hash=%s" + (", debe_cambiar_clave=FALSE" if _esquema["cambio_clave"] else "") \
            + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (generate_password_hash(nueva), u["id"]))
    for k in llaves:
        limitador.limpiar(k)
    return jsonify({"ok": True, "mensaje": "Contraseña actualizada. Ya puede iniciar sesión."}), 200
