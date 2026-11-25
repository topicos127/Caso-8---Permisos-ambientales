"""Registro propio de errores: los ultimos errores 5xx quedan en memoria para que el
administrador de la plataforma los vea, y cada peticion lleva un identificador que el
usuario puede citar al reportar un problema ("fallo con el codigo 3f9a1c2e").

No sale ningun dato a servicios externos. Se guarda el identificador del usuario (no
su nombre ni su correo) y el tipo de error; nunca el cuerpo de la peticion.
"""
import threading
import traceback
from collections import deque
from datetime import datetime

from .config import ZONA

_errores = deque(maxlen=200)
_candado = threading.Lock()
_inicio = datetime.now(ZONA).replace(tzinfo=None, microsecond=0)
_conteo = {"peticiones": 0, "errores": 0}


def anotar_peticion():
    _conteo["peticiones"] += 1


def anotar_error(rid, metodo, ruta, usuario_id, error):
    pila = "".join(traceback.format_exception(type(error), error, error.__traceback__)[-3:])
    with _candado:
        _conteo["errores"] += 1
        _errores.appendleft({
            "id": rid, "cuando": datetime.now(ZONA).strftime("%d/%m/%Y %H:%M:%S"),
            "metodo": metodo, "ruta": ruta, "usuario_id": usuario_id,
            "error": f"{type(error).__name__}: {str(error)[:300]}", "detalle": pila[-1500:],
        })


def ultimos(n=50):
    with _candado:
        return list(_errores)[:n]


def resumen():
    return {"activo_desde": _inicio.strftime("%d/%m/%Y %H:%M"), "peticiones": _conteo["peticiones"],
            "errores": _conteo["errores"]}
