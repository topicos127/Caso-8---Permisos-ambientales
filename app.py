"""
Sistema de Permisos Ambientales - Servicio de Login (HU-11)
Sprint 2 - Caso 8

Historia de Usuario: Como usuario del sistema (consultor o promotor),
quiero iniciar sesion con mis credenciales, para acceder unicamente
a los expedientes asociados a mi perfil.
"""

from flask import Flask, request, jsonify

app = Flask(__name__)

# Base de datos simulada de usuarios (en memoria, solo para esta etapa del sprint)
USERS_DB = {
    "consultor1@ejemplo.com": "clave123",
    "promotor1@ejemplo.com": "clave456",
}


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "servicio": "Sistema de Permisos Ambientales - Login API",
        "version": "0.1",
        "estado": "activo"
    }), 200


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    password = data.get("password", "")

    if email in USERS_DB and USERS_DB[email] == password:
        return jsonify({
            "acceso": True,
            "mensaje": f"Bienvenido, {email}. Acceso concedido a sus expedientes."
        }), 200
    else:
        return jsonify({
            "acceso": False,
            "mensaje": "Credenciales incorrectas. Verifique su correo y contrasena."
        }), 401


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) 