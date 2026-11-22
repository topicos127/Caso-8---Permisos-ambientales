"""Sesion, proteccion CSRF y reglas de acceso por rol (HU-11, HU-13)."""
from functools import wraps

from flask import g, request, session

from .bd import cursor
from .config import RUTAS_SIN_CABECERA
from .errores import ApiError, respuesta_error


def exigir_cabecera_en_escrituras():
    """Proteccion contra CSRF: un formulario de otro sitio no puede mandar
    cabeceras propias. Solo aplica si hay sesion (sin sesion sale 401)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") \
            and request.path not in RUTAS_SIN_CABECERA \
            and session.get("uid") \
            and request.headers.get("X-Requested-With") != "fetch":
        return respuesta_error(403, "Peticion rechazada: falta la cabecera X-Requested-With.")
    return None


def usuario_sesion():
    uid = session.get("uid")
    if not uid:
        return None
    with cursor() as cur:
        cur.execute("SELECT id, email, rol, nombre FROM usuarios WHERE id=%s", (uid,))
        u = cur.fetchone()
    if not u:
        session.clear()
    return u


def requiere_login(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        u = usuario_sesion()
        if not u:
            return respuesta_error(401, "No autenticado")
        g.usuario = u
        return f(*args, **kwargs)
    return envoltura


# ---------- Permisos sobre expedientes ----------

def puede_ver(u, exp):
    if u["rol"] == "jefe":
        return True  # HU-13: una sola consultora, el jefe ve todo
    if u["rol"] == "promotor":
        return bool(exp["promotor_email"]) and exp["promotor_email"] == u["email"]
    return u["rol"] == "consultor" and exp["usuario_id"] == u["id"]


def exigir_lectura(u, exp):
    if not puede_ver(u, exp):
        raise ApiError(403, "Sin acceso a este expediente.")


def exigir_gestion(u, exp):
    """Subir, borrar, someter: el consultor duenio o el jefe."""
    if u["rol"] == "jefe":
        return
    if u["rol"] != "consultor" or exp["usuario_id"] != u["id"]:
        raise ApiError(403, "No autorizado.")


def exigir_jefe(u, mensaje="Solo el jefe de la consultora puede aprobar internamente."):
    if u["rol"] != "jefe":
        raise ApiError(403, mensaje)


def filtro_de(u):
    """Condicion SQL (sobre el alias e de expedientes) de lo que ve cada rol."""
    if u["rol"] == "jefe":
        return "1=1", []
    if u["rol"] == "promotor":
        return "e.promotor_email=%s", [u["email"]]
    return "e.usuario_id=%s", [u["id"]]
