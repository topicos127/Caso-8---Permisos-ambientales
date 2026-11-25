"""Errores de la API: todas las respuestas de error tienen la misma forma, y las
cabeceras de seguridad de cada respuesta."""
import secrets

import pymysql
from flask import g, jsonify, request, session
from werkzeug.exceptions import HTTPException

from . import registro_errores
from .config import SESSION_COOKIE_SECURE


class ApiError(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def respuesta_error(status, mensaje, **extra):
    # "error" y "mensaje" a la vez: las pantallas viejas leen uno u otro.
    return jsonify({"ok": False, "error": mensaje, "mensaje": mensaje, **extra}), status


# Politica de contenido: solo se carga lo que sirve esta misma aplicacion, salvo las
# tipografias de Google Fonts. Nada de frames, plugins ni formularios hacia otros sitios.
CSP = ("default-src 'self'; "
       "script-src 'self'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; "
       "img-src 'self' data: blob:; "
       "connect-src 'self'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def _usuario_id():
    return session.get("uid")


def _error_grave(e, mensaje):
    rid = getattr(g, "rid", "sin-id")
    registro_errores.anotar_error(rid, request.method, request.path, _usuario_id(), e)
    print(f"ERROR {rid} {request.method} {request.path}: {e!r}", flush=True)
    return respuesta_error(500, mensaje, id=rid)


def registrar(app):
    @app.before_request
    def identificar_peticion():
        g.rid = secrets.token_hex(4)
        registro_errores.anotar_peticion()

    @app.errorhandler(ApiError)
    def _api_error(e):
        return respuesta_error(e.status, e.mensaje)

    @app.errorhandler(HTTPException)
    def _http_error(e):
        if e.code == 413:
            return respuesta_error(413, "El archivo supera el limite de 20 MB.")
        return respuesta_error(e.code, e.name)

    @app.errorhandler(pymysql.MySQLError)
    def _db_error(e):
        return _error_grave(e, "Error de base de datos.")

    @app.errorhandler(Exception)
    def _error_inesperado(e):
        return _error_grave(e, "Error interno del servidor.")

    @app.after_request
    def cabeceras_de_seguridad(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = CSP
        if SESSION_COOKIE_SECURE:
            # Solo con HTTPS: el navegador recordara no volver a usar http para este sitio.
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if hasattr(g, "rid"):
            resp.headers["X-Request-Id"] = g.rid
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp
