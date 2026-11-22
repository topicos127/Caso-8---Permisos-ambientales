"""HU-11: login, logout, sesion y registro."""
import pymysql
from flask import Blueprint, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..bd import cursor
from ..config import EMAIL_RE, ROLES_REGISTRO
from ..reglas import problema_de_password
from ..seguridad import requiere_login
from ..utiles import texto

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "") or "").strip().lower()
    password = str(data.get("password", "") or "")

    if not email or not password:
        return jsonify({"acceso": False, "mensaje": "Debe ingresar correo y contrasena."}), 401

    with cursor() as cur:
        cur.execute("SELECT id, email, password_hash, rol, nombre FROM usuarios WHERE email=%s", (email,))
        u = cur.fetchone()

    if u and check_password_hash(u["password_hash"], password):
        session.clear()
        session["uid"] = u["id"]
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {u['nombre']}. Acceso concedido a sus expedientes.",
            "rol": u["rol"],
            "nombre": u["nombre"],
            "email": u["email"],
        }), 200

    return jsonify({"acceso": False, "mensaje": "Credenciales incorrectas."}), 401


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "mensaje": "Sesion cerrada."}), 200


@bp.route("/sesion", methods=["GET"])
@requiere_login
def sesion_actual():
    u = g.usuario
    return jsonify({"email": u["email"], "rol": u["rol"], "nombre": u["nombre"]}), 200


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
    if rol not in ROLES_REGISTRO:
        return jsonify({"ok": False, "mensaje": "Rol no permitido. Use consultor o promotor."}), 400
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
