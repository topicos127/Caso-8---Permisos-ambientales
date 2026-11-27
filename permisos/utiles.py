"""Lectura de la peticion, formato de respuestas y archivos en disco."""
import os

from flask import request

from .config import UPLOADS_DIR
from .errores import ApiError


# ---------- Entrada ----------

def texto(data, campo, maximo, obligatorio=True):
    valor = data.get(campo, "")
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise ApiError(400, f"El campo '{campo}' debe ser texto.")
    valor = valor.strip()
    if obligatorio and not valor:
        raise ApiError(400, f"El campo '{campo}' es obligatorio.")
    if len(valor) > maximo:
        raise ApiError(400, f"El campo '{campo}' admite hasta {maximo} caracteres.")
    return valor


def entero(nombre, defecto, minimo, maximo):
    valor = request.args.get(nombre, "")
    if valor == "":
        return defecto
    try:
        n = int(valor)
    except ValueError:
        raise ApiError(400, f"'{nombre}' debe ser un numero entero.")
    if n < minimo or n > maximo:
        raise ApiError(400, f"'{nombre}' debe estar entre {minimo} y {maximo}.")
    return n


# ---------- Salida ----------

def formatear_fechas(filas, campo, patron):
    """Pasa a texto el campo de fecha de cada fila (si tiene valor)."""
    for f in filas:
        if f and f.get(campo):
            f[campo] = f[campo].strftime(patron)


def paginacion(total, page, per_page):
    return {"total": total, "page": page, "per_page": per_page,
            "pages": (total + per_page - 1) // per_page}


# ---------- Archivos subidos ----------

def ruta_segura(ruta):
    if not ruta or ".." in ruta or ruta.startswith("/") or ruta.startswith("\\"):
        return None
    return os.path.join(UPLOADS_DIR, ruta)


def borrar_archivo(ruta):
    fisica = ruta_segura(ruta)
    if fisica and os.path.exists(fisica):
        try:
            os.remove(fisica)
        except OSError:
            pass
