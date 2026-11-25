"""Sistema de Permisos Ambientales - API.

Estructura (refactor del Sprint 9; antes todo vivia en app.py):
    config.py     variables de entorno y constantes del dominio
    reglas.py     reglas puras: semaforo, verificacion, politica de contrasenas
    errores.py    ApiError, forma unica de los errores y cabeceras de seguridad
    bd.py         conexion, consultas compartidas y preparacion de la base
    seguridad.py  sesion, CSRF y permisos por rol
    utiles.py     lectura de la peticion, formato de salida y archivos
    rutas/        un blueprint por area (auth, expedientes, documentos, ...)

Historia: Sprint 7 (sesion con cookie firmada, permisos por expediente,
HU-07); Sprint 8 (HU-13 rol jefe, HU-14 historial de solo lectura).
"""
import mimetypes
import os
import secrets
from datetime import timedelta

from flask import Flask, request

from . import config, errores, respaldos
from .bd import asegurar_bd
from .rutas import BLUEPRINTS
from .seguridad import exigir_cabecera_en_escrituras


mimetypes.add_type("image/webp", ".webp")  # algunos sistemas no lo conocen y lo servirian como binario


def create_app():
    # root_path en la raiz del proyecto: "static" se resuelve como antes.
    app = Flask(__name__, root_path=config.BASE_DIR)

    secret = config.SECRET_KEY
    if not secret:
        # Sin SECRET_KEY la app arranca igual, pero las sesiones se pierden al
        # reiniciar. En el despliegue hay que definirla (ver .env.example).
        secret = secrets.token_hex(32)
        print("AVISO: SECRET_KEY no esta definida; se usa una clave temporal.", flush=True)
    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        MAX_CONTENT_LENGTH=config.MAX_FILE_SIZE + 1024 * 1024,
        # La sesion vence tras SESION_MINUTOS sin actividad (cada peticion la renueva).
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=config.SESION_MINUTOS),
    )
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)

    errores.registrar(app)

    # El orden importa: primero se prepara la base, despues se revisa CSRF.
    @app.before_request
    def preparar_bd():
        if request.path != "/health":
            asegurar_bd()

    app.before_request(exigir_cabecera_en_escrituras)

    for bp in BLUEPRINTS:
        app.register_blueprint(bp)

    asegurar_bd()
    respaldos.iniciar_planificador()
    return app
