"""Reglas del negocio sin Flask ni base de datos: se prueban solas
(ver tests/test_semaforo.py)."""
import math
from datetime import datetime

from .config import CATEGORIAS_DOCS, ESTADOS_RESUELTOS, PLAZOS_LEGALES, ZONA


def hoy():
    return datetime.now(ZONA).date()


def ahora():
    # Hora de Panama sin zona: asi se guarda en DATETIME.
    return datetime.now(ZONA).replace(tzinfo=None, microsecond=0)


def como_fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        return datetime.strptime(valor, "%Y-%m-%d").date()
    return valor


def problema_de_password(password):
    """Politica del Sprint 6. Devuelve el mensaje de error o None."""
    if not isinstance(password, str):
        return "La contrasena debe ser texto."
    if len(password) < 8:
        return "La contrasena debe tener al menos 8 caracteres."
    if len(password) > 128:
        return "La contrasena admite hasta 128 caracteres."
    if not any(c.isdigit() for c in password):
        return "La contrasena debe incluir al menos un numero."
    if not any(c.isupper() for c in password):
        return "La contrasena debe incluir al menos una letra mayuscula."
    return None


def es_contenido_valido(file_stream):
    """Magic bytes: el archivo debe empezar como PDF o como ZIP."""
    header = file_stream.read(4)
    file_stream.seek(0)
    return header.startswith(b'%PDF') or header.startswith(b'PK\x03\x04')


def calcular_verificacion(categoria, documentos):
    """HU-02/03/04. Compara los documentos con los requeridos por categoria."""
    requeridos = CATEGORIAS_DOCS.get(categoria, CATEGORIAS_DOCS["II"])
    docs_por_carpeta = {d["carpeta"]: d["estado"] for d in documentos}
    completos = sum(1 for carpeta in requeridos if docs_por_carpeta.get(carpeta) == "recibido")
    faltantes = [carpeta for carpeta in requeridos if docs_por_carpeta.get(carpeta) != "recibido"]
    return {
        "categoria": categoria,
        "total_requeridos": len(requeridos),
        "completos": completos,
        "faltantes": faltantes,
        "puede_someter": len(faltantes) == 0,
    }


def calcular_semaforo(exp, dia=None):
    """HU-07. Devuelve el estado del plazo legal de un expediente."""
    categoria = exp.get("categoria") if exp.get("categoria") in PLAZOS_LEGALES else "II"
    limite = PLAZOS_LEGALES[categoria]
    umbral = max(2, math.ceil(limite * 0.25))
    base = {
        "expediente": exp["codigo"],
        "categoria": categoria,
        "estado_expediente": exp["estado"],
        "limite_dias": limite,
        "umbral_por_vencer": umbral,
    }

    if exp["estado"] in ESTADOS_RESUELTOS:
        return dict(base,
                    dias_transcurridos=None,
                    dias_restantes_legales=None,
                    estado_semaforo="resuelto",
                    alerta_vencimiento="Resuelto: el plazo legal ya no corre.")

    transcurridos = ((dia or hoy()) - como_fecha(exp["fecha_ingreso"])).days
    restantes = limite - transcurridos
    if restantes < 0:
        estado = "vencido"
        alerta = f"VENCIDO (Supero por {abs(restantes)} dias)"
    elif restantes <= umbral:
        estado = "por_vencer"
        alerta = f"ALERTA CRITICA (Quedan {restantes} dias)"
    else:
        estado = "en_plazo"
        alerta = f"Dentro del plazo legal ({restantes} dias de {limite})"

    return dict(base,
                dias_transcurridos=transcurridos,
                dias_restantes_legales=restantes,
                estado_semaforo=estado,
                alerta_vencimiento=alerta)
