"""Registro de accesos y cambios de cada consultora (lo que ve el director en "Mi consultora").

Se guarda quien hizo que y cuando, sin el contenido de los expedientes ni las contrasenas.
El registro no tiene llaves foraneas a proposito: sigue existiendo aunque una cuenta se desactive.
"""
import pymysql
from flask import has_request_context, request

from .reglas import ahora

# tipo -> texto que se muestra
TIPOS = {
    "acceso": "Inicio de sesión",
    "acceso_fallido": "Intento de acceso fallido",
    "alta_por_invitacion": "Cuenta creada por invitación",
    "invitacion_creada": "Invitación creada",
    "invitacion_revocada": "Invitación revocada",
    "marca": "Marca actualizada",
    "logo": "Logo actualizado",
    "datos": "Datos de la empresa actualizados",
    "politica": "Política de seguridad actualizada",
    "sesiones_cerradas": "Sesiones del equipo cerradas",
    "exportacion": "Exportación de todos los datos",
    "equipo_alta": "Consultor dado de alta",
    "equipo_desactivado": "Consultor desactivado",
    "equipo_activado": "Consultor reactivado",
    "equipo_reasignado": "Expedientes reasignados",
    "clave_restablecida": "Contraseña restablecida",
    "clave_cambiada": "Contraseña cambiada",
    "dos_pasos_activado": "Dos pasos activados",
    "dos_pasos_desactivado": "Dos pasos desactivados",
    "codigos_regenerados": "Códigos de recuperación nuevos",
    "titular_transferido": "Titularidad transferida",
    "rol_cambiado": "Rol cambiado",
    "admin_invitacion_creada": "Invitación de administrador creada",
    "admin_invitacion_revocada": "Invitación de administrador revocada",
    "admin_alta": "Administrador dado de alta",
    "admin_desactivado": "Administrador desactivado",
    "admin_activado": "Administrador reactivado",
    "admin_clave_restablecida": "Acceso de un administrador restablecido",
}


def registrar(cur, organizacion_id, usuario_id, tipo, detalle="", email=None):
    """Anota un evento dentro de la misma transaccion de la accion. Un fallo al anotar no rompe la accion."""
    ip = request.remote_addr if has_request_context() else None
    try:
        cur.execute("INSERT INTO eventos_cuenta (organizacion_id, usuario_id, email, tipo, detalle, ip, fecha) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (organizacion_id, usuario_id, email, tipo, (detalle or "")[:300] or None, ip, ahora()))
    except pymysql.MySQLError as e:
        print(f"AVISO: no se pudo anotar el evento {tipo}: {e!r}", flush=True)
