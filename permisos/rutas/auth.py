"""HU-11: login, logout, sesion, registro y cambio de contrasena; preferencia
de aviso de vencimiento (HU-05, Sprint 10)."""
import threading
import time
from collections import deque

import pymysql
from flask import Blueprint, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..bd import _esquema, col_activo, col_aviso, col_cambio_clave, col_sometimiento, cursor
from ..config import EMAIL_RE, LOGIN_MAX_FALLOS, LOGIN_VENTANA_SEGUNDOS, ROLES_REGISTRO
from ..errores import ApiError
from ..reglas import AVISOS_PERMITIDOS, calcular_semaforo, problema_de_password
from ..seguridad import filtro_de, requiere_login
from ..utiles import texto

bp = Blueprint("auth", __name__)

# ---------- Limite de intentos fallidos (Sprint 9) ----------
# En memoria: gunicorn corre un solo proceso con hilos. La clave es correo + IP,
# asi un atacante no bloquea a otros usuarios y un correo no se prueba sin fin.
# Solo cuentan los fallos; un login correcto limpia el contador.
_fallos = {}
_candado = threading.Lock()


def _fallos_recientes(clave, ahora):
    marcas = _fallos.get(clave)
    if not marcas:
        return 0
    while marcas and ahora - marcas[0] > LOGIN_VENTANA_SEGUNDOS:
        marcas.popleft()
    if not marcas:
        del _fallos[clave]
        return 0
    return len(marcas)


def _anotar_fallo(clave, ahora):
    _fallos.setdefault(clave, deque()).append(ahora)


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    password = str(data.get("password", "") or "")

    if not email or not password:
        return jsonify({"acceso": False, "mensaje": "Debe ingresar correo y contrasena."}), 401

    clave = (request.remote_addr, email)
    with _candado:
        if _fallos_recientes(clave, time.monotonic()) >= LOGIN_MAX_FALLOS:
            return jsonify({"acceso": False, "mensaje":
                            "Demasiados intentos fallidos. Espere un minuto e intente de nuevo."}), 429

    with cursor() as cur:
        cur.execute(f"SELECT id, email, password_hash, rol, nombre, {col_cambio_clave()}, {col_activo()} "
                    "FROM usuarios WHERE email=%s", (email,))
        u = cur.fetchone()

    if u and check_password_hash(u["password_hash"], password):
        with _candado:
            _fallos.pop(clave, None)
        if not u["activo"]:
            # Sprint 9: la cuenta existe y la clave es correcta, pero el jefe la desactivo.
            return jsonify({"acceso": False,
                            "mensaje": "Tu cuenta está desactivada. Habla con el jefe de la consultora."}), 403
        session.clear()
        session["uid"] = u["id"]
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {u['nombre']}. Acceso concedido a sus expedientes.",
            "rol": u["rol"],
            "nombre": u["nombre"],
            "email": u["email"],
            "debe_cambiar_clave": bool(u["debe_cambiar_clave"]),
        }), 200

    with _candado:
        _anotar_fallo(clave, time.monotonic())
    return jsonify({"acceso": False, "mensaje": "Credenciales incorrectas."}), 401


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "mensaje": "Sesion cerrada."}), 200


@bp.route("/sesion", methods=["GET"])
@requiere_login
def sesion_actual():
    u = g.usuario
    return jsonify({"email": u["email"], "rol": u["rol"], "nombre": u["nombre"],
                    "debe_cambiar_clave": u["debe_cambiar_clave"]}), 200


@bp.route("/registro", methods=["POST"])
def registro():
    data = request.get_json(silent=True) or {}
    nombre = texto(data, "nombre", 255, obligatorio=False)
    email = texto(data, "email", 255, obligatorio=False).lower()
    password = data.get("password", "")
    rol = data.get("rol", "consultor")

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

    try:
        with cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409
            cur.execute(
                "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
                (nombre, email, generate_password_hash(password), rol),
            )
    except pymysql.err.IntegrityError:
        return jsonify({"ok": False, "mensaje": "Ese correo ya esta registrado."}), 409

    return jsonify({"ok": True, "mensaje": "Usuario registrado correctamente."}), 201


@bp.route("/cuenta/contrasena", methods=["POST"])
@requiere_login
def cambiar_contrasena():
    """Cualquier usuario cambia su propia contrasena (por ejemplo, la temporal
    que recibe el promotor)."""
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
        cur.execute("SELECT password_hash FROM usuarios WHERE id=%s", (g.usuario["id"],))
        fila = cur.fetchone()
        if not fila or not check_password_hash(fila["password_hash"], actual):
            raise ApiError(400, "La contrasena actual no es correcta.")
        if _esquema["cambio_clave"]:
            cur.execute("UPDATE usuarios SET password_hash=%s, debe_cambiar_clave=FALSE WHERE id=%s",
                        (generate_password_hash(nueva), g.usuario["id"]))
        else:
            cur.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s",
                        (generate_password_hash(nueva), g.usuario["id"]))
    return jsonify({"ok": True, "mensaje": "Contrasena actualizada."}), 200


@bp.route("/perfil", methods=["GET", "POST"])
@requiere_login
def perfil():
    """HU-05 (Sprint 10): con cuantos dias de anticipacion se avisa que un
    documento vence (15, 30 o 45; 30 por defecto)."""
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
        cur.execute(f"SELECT {col_aviso()}, fecha_creacion FROM usuarios WHERE id=%s", (g.usuario["id"],))
        fila = cur.fetchone() or {}
        # Cifras del perfil: lo que el usuario puede ver segun su rol.
        cur.execute(f"""SELECT e.codigo, e.categoria, e.estado, e.fecha_ingreso, {col_sometimiento()}
                        FROM expedientes e WHERE {filtro}""", params)
        expedientes = cur.fetchall()
    en_tramite = [e for e in expedientes if e["estado"] not in ("aprobado", "rechazado")]
    en_alerta = sum(1 for e in en_tramite
                    if calcular_semaforo(e)["estado_semaforo"] in ("por_vencer", "vencido"))
    desde = fila.get("fecha_creacion")
    return jsonify({"email": g.usuario["email"], "nombre": g.usuario["nombre"], "rol": g.usuario["rol"],
                    "miembro_desde": desde.strftime("%d/%m/%Y") if desde else None,
                    "aviso_vencimiento_dias": int(fila.get("aviso_vencimiento_dias") or 30),
                    "opciones_aviso": list(AVISOS_PERMITIDOS),
                    "cifras": {"expedientes": len(expedientes), "en_tramite": len(en_tramite),
                               "aprobados": sum(1 for e in expedientes if e["estado"] == "aprobado"),
                               "plazos_en_alerta": en_alerta}}), 200
