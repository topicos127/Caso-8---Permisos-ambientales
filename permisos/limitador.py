"""Limite de intentos fallidos (login, codigos de recuperacion, invitaciones).

En memoria: gunicorn corre un solo proceso con hilos. La clave combina IP y un
identificador (el correo), asi un atacante no bloquea a otros usuarios y un
correo no se prueba sin fin. Solo cuentan los fallos; un exito limpia el contador.
"""
import threading
import time
from collections import deque

from .config import LOGIN_MAX_FALLOS, LOGIN_VENTANA_SEGUNDOS

_fallos = {}
_candado = threading.Lock()


def _recientes(clave, ahora):
    marcas = _fallos.get(clave)
    if not marcas:
        return 0
    while marcas and ahora - marcas[0] > LOGIN_VENTANA_SEGUNDOS:
        marcas.popleft()
    if not marcas:
        del _fallos[clave]
        return 0
    return len(marcas)


def bloqueado(clave):
    with _candado:
        return _recientes(clave, time.monotonic()) >= LOGIN_MAX_FALLOS


def anotar_fallo(clave):
    with _candado:
        _fallos.setdefault(clave, deque()).append(time.monotonic())


def limpiar(clave):
    with _candado:
        _fallos.pop(clave, None)


def fallos(clave):
    """Cuantos fallos recientes tiene la clave (para decidir que se anota en el registro)."""
    with _candado:
        return _recientes(clave, time.monotonic())
