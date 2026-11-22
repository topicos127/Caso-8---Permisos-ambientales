"""Errores de la API: todas las respuestas de error tienen la misma forma."""
import pymysql
from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def respuesta_error(status, mensaje):
    # "error" y "mensaje" a la vez: las pantallas viejas leen uno u otro.
    return jsonify({"ok": False, "error": mensaje, "mensaje": mensaje}), status


def registrar(app):
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
        print(f"ERROR DE BASE DE DATOS: {e}", flush=True)
        return respuesta_error(500, "Error de base de datos.")

    @app.errorhandler(Exception)
    def _error_inesperado(e):
        print(f"ERROR INESPERADO: {e!r}", flush=True)
        return respuesta_error(500, "Error interno del servidor.")

    @app.after_request
    def cabeceras_de_seguridad(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp
