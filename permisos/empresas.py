"""Datos de la empresa (organizacion) a la que pertenece un usuario."""
import os

from .bd import _esquema


def datos_empresa(cur, org_id):
    """{id, nombre, color, logo, activa} o None si la base no tiene empresas."""
    if org_id is None or not _esquema["org"]:
        return None
    cur.execute("SELECT id, nombre, color, logo_ruta, activa FROM organizaciones WHERE id=%s", (org_id,))
    o = cur.fetchone()
    if not o:
        return None
    logo = None
    if o["logo_ruta"]:
        # El nombre del archivo cambia con cada logo nuevo: sirve para renovar la cache.
        logo = f"/organizacion/logo/{o['id']}?v={os.path.basename(o['logo_ruta']).split('.')[0]}"
    return {"id": o["id"], "nombre": o["nombre"], "color": o["color"], "logo": logo, "activa": bool(o["activa"])}
