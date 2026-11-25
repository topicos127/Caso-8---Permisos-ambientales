"""Login (con verificacion en dos pasos), logout, sesion, registro por invitacion,
cambio de contrasena y preferencia de aviso de vencimiento."""
import hashlib

import pymysql
from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .. import limitador, totp
from ..bd import _esquema, col_activo, col_aviso, col_cambio_clave, col_org, col_sesion, col_sometimiento, col_totp, cursor
from ..config import EMAIL_RE, ROLES_REGISTRO
from ..empresas import datos_empresa
from ..errores import ApiError
from ..limitador import _fallos  # noqa: F401  (las pruebas limpian auth._fallos)
from ..reglas import AVISOS_PERMITIDOS, ahora, calcular_semaforo, problema_de_password
from ..seguridad import filtro_de, requiere_login
from ..utiles import texto

bp = Blueprint("auth", __name__)


def hash_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def abrir_sesion(usuario_id, version):
    session.clear()
    session["uid"] = usuario_id
    session["sv"] = version or 0
    session.permanent = True  # vence por inactividad (SESION_MINUTOS)


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    password = str(data.get("password", "") or "")
    codigo = str(data.get("codigo", "") or "").strip()

    if not email or not password:
        return jsonify({"acceso": False, "mensaje": "Debe ingresar correo y contrasena."}), 401

    clave = (request.remote_addr, email)
    if limitador.bloqueado(clave):
        return jsonify({"acceso": False, "mensaje":
                        "Demasiados intentos fallidos. Espere un minuto e intente de nuevo."}), 429

    with cursor() as cur:
        cur.execute(f"SELECT id, email, password_hash, rol, nombre, {col_cambio_clave()}, {col_activo()}, "
                    f"{col_org('')}, {col_sesion()}, {col_totp()} FROM usuarios WHERE email=%s", (email,))
        u = cur.fetchone()
        empresa = datos_empresa(cur, u["organizacion_id"]) if u and _esquema["org"] else None

    if u and check_password_hash(u["password_hash"], password):
        if not u["activo"]:
            # La cuenta existe y la clave es correcta, pero el jefe la desactivo.
            limitador.limpiar(clave)
            return jsonify({"acceso": False,
                            "mensaje": "Tu cuenta está desactivada. Habla con el jefe de la consultora."}), 403
        if empresa is not None and not empresa["activa"]:
            return jsonify({"acceso": False, "mensaje": "La cuenta de su empresa está desactivada. "
                                                       "Comuníquese con el administrador de la plataforma."}), 403

        # Verificacion en dos pasos: sin el codigo no hay sesion (pero tampoco cuenta como fallo).
        if u.get("totp_activo"):
            if not codigo:
                return jsonify({"acceso": False, "requiere_2fa": True,
                                "mensaje": "Ingrese el código de su aplicación autenticadora."}), 401
            if not _codigo_valido(u, codigo):
                limitador.anotar_fallo(clave)
                return jsonify({"acceso": False, "requiere_2fa": True,
                                "mensaje": "El código no es correcto o ya se usó."}), 401

        limitador.limpiar(clave)
        abrir_sesion(u["id"], u.get("sesion_version"))
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {u['nombre']}.",
            "rol": u["rol"],
            "nombre": u["nombre"],
            "email": u["email"],
            "debe_cambiar_clave": bool(u["debe_cambiar_clave"]),
            "empresa": empresa,
        }), 200

    limitador.anotar_fallo(clave)
    return jsonify({"acceso": False, "mensaje": "Credenciales incorrectas."}), 401


def _codigo_valido(u, codigo):
    """Codigo TOTP (una sola vez) o codigo de recuperacion (una sola vez)."""
    if len(totp.normalizar_codigo(codigo)) == 10:  # un TOTP tiene 6 digitos; el de recuperacion, 10 caracteres
        with cursor() as cur:
            usados = cur.execute("UPDATE codigos_recuperacion SET usado_en=%s "
                                 "WHERE usuario_id=%s AND codigo_hash=%s AND usado_en IS NULL",
                                 (ahora(), u["id"], totp.hash_codigo(codigo)))
        return usados == 1
    secreto = totp.descifrar(u["totp_secreto"] or "", current_app.secret_key)
    paso = totp.verificar(secreto, codigo, u.get("totp_ultimo_paso") or 0) if secreto else None
    if paso is None:
        return False
    with cursor() as cur:
        # Condicional: el mismo codigo no se puede usar dos veces ni en dos pestanas a la vez.
        cambiadas = cur.execute("UPDATE usuarios SET totp_ultimo_paso=%s WHERE id=%s AND totp_ultimo_paso < %s",
                                (paso, u["id"], paso))
    return cambiadas == 1


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "mensaje": "Sesion cerrada."}), 200


@bp.route("/sesion", methods=["GET"])
@requiere_login
def sesion_actual():
    u = g.usuario
    with cursor() as cur:
        empresa = datos_empresa(cur, u.get("organizacion_id"))
        pendientes = False
        if _esquema["terminos"]:
            cur.execute("SELECT terminos_aceptados_en FROM usuarios WHERE id=%s", (u["id"],))
            pendientes = cur.fetchone()["terminos_aceptados_en"] is None
    return jsonify({"email": u["email"], "rol": u["rol"], "nombre": u["nombre"],
                    "debe_cambiar_clave": u["debe_cambiar_clave"], "empresa": empresa,
                    "terminos_pendientes": pendientes}), 200


@bp.route("/registro", methods=["POST"])
def registro():
    """El registro es solo por invitacion: el jefe invita a su equipo y el administrador
    de la plataforma invita al jefe de cada empresa nueva. El rol y la empresa salen de
    la invitacion; el cuerpo no los decide."""
    data = request.get_json(silent=True) or {}
    nombre = texto(data, "nombre", 255, obligatorio=False)
    email = texto(data, "email", 255, obligatorio=False).lower()
    password = data.get("password", "")
    rol = data.get("rol", "consultor")
    token = str(data.get("invitacion", "") or "").strip()

    if not nombre or not email or not password:
        return jsonify({"ok": False, "mensaje": "Todos los campos son obligatorios."}), 400
    if not isinstance(password, str):
        return jsonify({"ok": False, "mensaje": "La contrasena debe ser texto."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"ok": False, "mensaje": "El correo no es valido."}), 400
    if rol == "promotor":
        return jsonify({"ok": False, "mensaje": "Rol no permitido: la cuenta del promotor la crea su "
                                                "consultor desde el expediente."}), 400
    if rol not in ROLES_REGISTRO:
        return jsonify({"ok": False, "mensaje": "Rol no permitido. Use consultor."}), 400
    problema = problema_de_password(password)
    if problema:
        return jsonify({"ok": False, "mensaje": problema}), 400
    if not token:
        return jsonify({"ok": False, "mensaje": "El registro es solo por invitación. Pida una a su jefe de "
                                                "consultora."}), 403
    if data.get("acepto_terminos") is not True:
        return jsonify({"ok": False, "mensaje": "Debe aceptar los términos y la política de privacidad."}), 400

    clave = (request.remote_addr, "invitacion")
    if limitador.bloqueado(clave):
        return jsonify({"ok": False, "mensaje": "Demasiados intentos. Espere un minuto."}), 429

    try:
        with cursor() as cur:
            cur.execute("SELECT id, organizacion_id, rol, email, expira, usada_en, revocada FROM invitaciones "
                        "WHERE token_hash=%s", (hash_token(token),))
            inv = cur.fetchone()
            if not inv or inv["revocada"] or inv["usada_en"] or inv["expira"] < ahora():
                limitador.anotar_fallo(clave)
                return jsonify({"ok": False, "mensaje": "La invitación no es válida, ya se usó o venció. "
                                                        "Pida una nueva."}), 400
            if inv["email"] and inv["email"].lower() != email:
                return jsonify({"ok": False, "mensaje": "Esta invitación es para otro correo."}), 400
            cur.execute("SELECT activa FROM organizaciones WHERE id=%s", (inv["organizacion_id"],))
            org = cur.fetchone()
            if not org or not org["activa"]:
                return jsonify({"ok": False, "mensaje": "La empresa de esta invitación está desactivada."}), 400
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409
            columna, marca = ", organizacion_id", ", %s"
            valores = [inv["organizacion_id"]]
            if _esquema["terminos"]:
                columna, marca = columna + ", terminos_aceptados_en", marca + ", %s"
                valores.append(ahora())
            cur.execute(f"INSERT INTO usuarios (nombre, email, password_hash, rol{columna}) "
                        f"VALUES (%s, %s, %s, %s{marca})",
                        (nombre, email, generate_password_hash(password), inv["rol"], *valores))
            nuevo = cur.lastrowid
            usadas = cur.execute("UPDATE invitaciones SET usada_en=%s, usada_por=%s WHERE id=%s AND usada_en IS NULL",
                                 (ahora(), nuevo, inv["id"]))
            if usadas != 1:
                raise ApiError(409, "La invitación acaba de usarse.")
    except pymysql.err.IntegrityError:
        return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409

    return jsonify({"ok": True, "mensaje": "Cuenta creada. Ya puede iniciar sesión."}), 201


@bp.route("/cuenta/contrasena", methods=["POST"])
@requiere_login
def cambiar_contrasena():
    """Cualquier usuario cambia su propia contrasena (por ejemplo, la temporal
    que recibe el promotor). Las demas sesiones del usuario se cierran."""
    data = request.get_json(silent=True) or {}
    actual = data.get("actual", "")
    nueva = data.get("nueva", "")
    if not isinstance(actual, str) or not actual:
        raise ApiError(400, "Ingrese su contrasena actual.")
    problema = problema_de_password(nueva)
    if problema:
        raise ApiError(400, problema)
    if nueva == actual:
        raise ApiError(400, "La contrasena nueva debe ser distinta de la actual.")

    with cursor() as cur:
        cur.execute(f"SELECT password_hash, {col_sesion()} FROM usuarios WHERE id=%s", (g.usuario["id"],))
        fila = cur.fetchone()
        if not fila or not check_password_hash(fila["password_hash"], actual):
            raise ApiError(400, "La contrasena actual no es correcta.")
        sets = "password_hash=%s" + (", debe_cambiar_clave=FALSE" if _esquema["cambio_clave"] else "") \
            + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (generate_password_hash(nueva), g.usuario["id"]))
    session["sv"] = int(fila.get("sesion_version") or 0) + (1 if _esquema["sesion"] else 0)
    return jsonify({"ok": True, "mensaje": "Contrasena actualizada."}), 200


@bp.route("/perfil", methods=["GET", "POST"])
@requiere_login
def perfil():
    """Con cuantos dias de anticipacion se avisa que un documento vence (15, 30 o 45; 30 por
    defecto) y las cifras del usuario segun su rol."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        dias = data.get("aviso_vencimiento_dias")
        if isinstance(dias, bool) or dias not in AVISOS_PERMITIDOS:
            raise ApiError(400, "El aviso debe ser de 15, 30 o 45 días.")
        if not _esquema["aviso"]:
            raise ApiError(503, "La preferencia aún no está disponible: falta actualizar la base de datos.")
        with cursor() as cur:
            cur.execute("UPDATE usuarios SET aviso_vencimiento_dias=%s WHERE id=%s", (dias, g.usuario["id"]))
        return jsonify({"ok": True, "aviso_vencimiento_dias": dias,
                        "mensaje": f"Le avisaremos {dias} días antes de que venza un documento."}), 200
    filtro, params = filtro_de(g.usuario)
    with cursor() as cur:
        cur.execute(f"SELECT {col_aviso()}, fecha_creacion, {col_totp()} FROM usuarios WHERE id=%s",
                    (g.usuario["id"],))
        fila = cur.fetchone() or {}
        # Cifras del perfil: lo que el usuario puede ver segun su rol.
        cur.execute(f"""SELECT e.codigo, e.categoria, e.estado, e.fecha_ingreso, {col_sometimiento()}
                        FROM expedientes e WHERE {filtro}""", params)
        expedientes = cur.fetchall()
        empresa = datos_empresa(cur, g.usuario.get("organizacion_id"))
    en_tramite = [e for e in expedientes if e["estado"] not in ("aprobado", "rechazado")]
    en_alerta = sum(1 for e in en_tramite
                    if calcular_semaforo(e)["estado_semaforo"] in ("por_vencer", "vencido"))
    desde = fila.get("fecha_creacion")
    return jsonify({"email": g.usuario["email"], "nombre": g.usuario["nombre"], "rol": g.usuario["rol"],
                    "empresa": empresa, "dos_pasos": bool(fila.get("totp_activo")),
                    "miembro_desde": desde.strftime("%d/%m/%Y") if desde else None,
                    "aviso_vencimiento_dias": int(fila.get("aviso_vencimiento_dias") or 30),
                    "opciones_aviso": list(AVISOS_PERMITIDOS),
                    "cifras": {"expedientes": len(expedientes), "en_tramite": len(en_tramite),
                               "aprobados": sum(1 for e in expedientes if e["estado"] == "aprobado"),
                               "plazos_en_alerta": en_alerta}}), 200
