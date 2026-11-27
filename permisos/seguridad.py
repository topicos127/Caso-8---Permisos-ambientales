"""Sesion, proteccion CSRF y reglas de acceso por rol y por empresa.

Aislamiento por empresa: todo usuario (salvo el administrador de la plataforma)
y todo expediente pertenece a una empresa. Las reglas de abajo son el UNICO
lugar donde se decide que empresa ve que: puede_ver, exigir_gestion, filtro_de
y condicion_empresa. Las rutas no comparan empresas por su cuenta.
"""
import time
from functools import wraps

from flask import g, request, session

from .bd import _esquema, col_activo, col_cambio_clave, col_org, col_sesion, cursor
from .config import ROL_ADMIN, RUTAS_SIN_CABECERA
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
        cur.execute(f"SELECT id, email, rol, nombre, {col_cambio_clave()}, {col_activo()}, {col_org('')}, "
                    f"{col_sesion()}, {'totp_activo' if _esquema['totp'] else '0 AS totp_activo'} "
                    "FROM usuarios WHERE id=%s", (uid,))
        u = cur.fetchone()
        empresa_activa = True
        politica = {}
        if u and _esquema["org"] and u.get("organizacion_id") is not None:
            columnas = "activa" + (", exigir_2fa, sesion_minutos" if _esquema["org_politica"] else "")
            cur.execute(f"SELECT {columnas} FROM organizaciones WHERE id=%s", (u["organizacion_id"],))
            fila = cur.fetchone()
            empresa_activa = bool(fila and fila["activa"])
            politica = fila or {}
    # Si el jefe desactiva a un consultor, su sesion abierta deja de valer. Lo mismo si
    # la empresa se desactiva o si el usuario cerro todas sus sesiones (sesion_version).
    if not u or not u["activo"] or not empresa_activa or session.get("sv", 0) != u.get("sesion_version", 0):
        session.clear()
        return None
    # Politica de la empresa: la sesion puede vencer antes por inactividad.
    limite = politica.get("sesion_minutos")
    ahora_s = time.time()
    if limite and session.get("ult") and ahora_s - session["ult"] > int(limite) * 60:
        session.clear()
        return None
    session["ult"] = ahora_s
    u["debe_cambiar_clave"] = bool(u["debe_cambiar_clave"])
    # Politica de la empresa: dos pasos obligatorios para consultores y directores.
    u["debe_activar_2fa"] = bool(politica.get("exigir_2fa")) and u["rol"] in ("consultor", "jefe") \
        and not u.get("totp_activo")
    u.pop("totp_activo", None)
    del u["activo"]
    u.pop("sesion_version", None)
    return u


# Con una contrasena temporal, lo unico permitido es ver la sesion y cambiarla.
# (/logout no pide login.)
ENDPOINTS_CON_CLAVE_TEMPORAL = {"auth.sesion_actual", "auth.cambiar_contrasena"}
# Si la empresa exige dos pasos y la persona aun no los activo, solo puede activarlos.
ENDPOINTS_CON_2FA_PENDIENTE = {"auth.sesion_actual", "auth.perfil", "cuenta.seguridad", "cuenta.preparar_2fa",
                               "cuenta.activar_2fa", "cuenta.aceptar_terminos"}


def requiere_login(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        u = usuario_sesion()
        if not u:
            return respuesta_error(401, "No autenticado")
        if u["debe_cambiar_clave"] and request.endpoint not in ENDPOINTS_CON_CLAVE_TEMPORAL:
            return respuesta_error(403, "Debe cambiar su contraseña temporal antes de continuar.",
                                   cambio_clave_obligatorio=True)
        if u.get("debe_activar_2fa") and request.endpoint not in ENDPOINTS_CON_2FA_PENDIENTE:
            return respuesta_error(403, "Su consultora exige la verificación en dos pasos. Actívela para continuar.",
                                   activar_2fa_obligatorio=True)
        g.usuario = u
        return f(*args, **kwargs)
    return envoltura


def requiere_admin(f):
    """Solo el administrador de la plataforma (crea empresas, respaldos, estado)."""
    @wraps(f)
    @requiere_login
    def envoltura(*args, **kwargs):
        if g.usuario["rol"] != ROL_ADMIN:
            raise ApiError(403, "Solo el administrador de la plataforma puede hacer esto.")
        return f(*args, **kwargs)
    return envoltura


# ---------- Permisos sobre expedientes ----------

def misma_empresa(u, fila):
    """True si el usuario y la fila (expediente o usuario) son de la misma empresa.
    Sin la columna de empresa (base anterior) las dos valen None y coinciden."""
    return u.get("organizacion_id") == fila.get("organizacion_id")


def puede_ver(u, exp):
    if u["rol"] == ROL_ADMIN or not misma_empresa(u, exp):
        return False  # el administrador de la plataforma no ve expedientes
    if u["rol"] == "jefe":
        return True  # HU-13: una sola consultora, el jefe ve todo
    if u["rol"] == "promotor":
        return bool(exp["promotor_email"]) and exp["promotor_email"] == u["email"]
    return u["rol"] == "consultor" and exp["usuario_id"] == u["id"]


def exigir_lectura(u, exp):
    if u["rol"] != ROL_ADMIN and not misma_empresa(u, exp):
        raise ApiError(404, "Expediente no encontrado.")  # de otra empresa: ni siquiera se confirma que existe
    if not puede_ver(u, exp):
        raise ApiError(403, "Sin acceso a este expediente.")


def exigir_gestion(u, exp):
    """Subir, borrar, someter: el consultor duenio o el jefe de la misma empresa."""
    if u["rol"] != ROL_ADMIN and not misma_empresa(u, exp):
        raise ApiError(404, "Expediente no encontrado.")
    if u["rol"] == ROL_ADMIN:
        raise ApiError(403, "No autorizado.")
    if u["rol"] == "jefe":
        return
    if u["rol"] != "consultor" or exp["usuario_id"] != u["id"]:
        raise ApiError(403, "No autorizado.")


def exigir_jefe(u, mensaje="Solo el director de proyectos puede aprobar internamente."):
    """Solo comprueba el ROL. Para actuar sobre un expediente use exigir_jefe_de: un jefe
    de otra empresa tambien tiene el rol."""
    if u["rol"] != "jefe":
        raise ApiError(403, mensaje)


def exigir_jefe_de(u, exp, mensaje="Solo el director de proyectos puede aprobar internamente."):
    """El jefe DE LA EMPRESA del expediente. De otra empresa responde 404, como si no existiera."""
    if u["rol"] != ROL_ADMIN and not misma_empresa(u, exp):
        raise ApiError(404, "Expediente no encontrado.")
    exigir_jefe(u, mensaje)


def condicion_empresa(u, alias="e"):
    """Condicion SQL de empresa sobre el alias (expedientes o usuarios), con sus
    parametros. Sin la columna de empresa no restringe nada."""
    if not _esquema["org"]:
        return "1=1", []
    if u["rol"] == ROL_ADMIN or u.get("organizacion_id") is None:
        return "1=0", []  # sin empresa no se ve nada
    return f"{alias}.organizacion_id=%s", [u["organizacion_id"]]


def filtro_de(u):
    """Condicion SQL (sobre el alias e de expedientes) de lo que ve cada rol."""
    if u["rol"] == ROL_ADMIN:
        return "1=0", []
    empresa, params = condicion_empresa(u)
    if u["rol"] == "jefe":
        return empresa, params
    if u["rol"] == "promotor":
        return f"{empresa} AND e.promotor_email=%s", params + [u["email"]]
    return f"{empresa} AND e.usuario_id=%s", params + [u["id"]]
