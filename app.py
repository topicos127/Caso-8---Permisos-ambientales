"""
Sistema de Permisos Ambientales - Servicio de Login (HU-11)
Sprint 3 - Caso 8

Este servicio consulta una base de datos MySQL real y valida contrasenas
mediante hash (nunca en texto plano). Sirve tambien el frontend estatico.
"""

import os
import pymysql
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import check_password_hash

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "permisos123"),
    "database": os.environ.get("DB_NAME", "permisos_ambientales"),
    "cursorclass": pymysql.cursors.DictCursor,
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")


@app.route("/api", methods=["GET"])
def api_info():
    return jsonify({
        "servicio": "Sistema de Permisos Ambientales - Login API",
        "version": "0.2",
        "estado": "activo"
    }), 200


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "acceso": False,
            "mensaje": "Debe ingresar correo y contrasena."
        }), 401

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, email, password_hash, rol, nombre "
                    "FROM usuarios WHERE email = %s",
                    (email,),
                )
                usuario = cursor.fetchone()
        finally:
            conn.close()
    except pymysql.MySQLError:
        return jsonify({
            "acceso": False,
            "mensaje": "No se pudo conectar con la base de datos."
        }), 500

    if usuario and check_password_hash(usuario["password_hash"], password):
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {usuario['nombre']}. Acceso concedido a sus expedientes.",
            "rol": usuario["rol"]
        }), 200

    return jsonify({
        "acceso": False,
        "mensaje": "Credenciales incorrectas. Verifique su correo y contrasena."
    }), 401


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)