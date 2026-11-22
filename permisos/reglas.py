"""Reglas del negocio sin Flask ni base de datos: se prueban solas
(ver tests/test_semaforo.py)."""
import math
from datetime import datetime

from .config import CATEGORIAS_DOCS, ESTADOS_RESUELTOS, PLAZOS_LEGALES, ZONA


# HU-05: supuesto actual (fecha de vencimiento real: Sprint 10). Todo documento
# vence al ano de subido y se avisa 30 dias antes.
VIGENCIA_DOCUMENTO_DIAS = 365
AVISO_VENCIMIENTO_DIAS = 30

# HU-15: pesos del Indice de Preparacion del Expediente (suman 1) y bandas.
PESO_DOCUMENTOS, PESO_PLAZO, PESO_VIGENCIA = 0.5, 0.3, 0.2
PUNTOS_PLAZO = {"en_plazo": 100, "resuelto": 100, "por_vencer": 50, "vencido": 0}
PENALIZACION_VIGENCIA = 25
BANDA_LISTO, BANDA_PREPARACION = 80, 50
BANDAS_TEXTO = {"listo": "Listo", "en_preparacion": "En preparación", "en_riesgo": "En riesgo"}


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


def documentos_por_vencer(documentos, dia=None):
    """HU-05. Documentos recibidos que vencen dentro del aviso (o ya vencieron):
    [(carpeta, dias_restantes)] del mas urgente al menos."""
    dia = dia or hoy()
    salida = []
    for d in documentos:
        if d.get("estado") != "recibido" or not d.get("fecha_subida"):
            continue
        restantes = VIGENCIA_DOCUMENTO_DIAS - (dia - como_fecha(d["fecha_subida"])).days
        if restantes < AVISO_VENCIMIENTO_DIAS:
            salida.append((d["carpeta"], restantes))
    return sorted(salida, key=lambda x: x[1])


def _redondear(x):
    return int(math.floor(x + 0.5))  # mitades hacia arriba (round() de Python va al par)


def banda_ipe(ipe):
    if ipe >= BANDA_LISTO:
        return "listo"
    if ipe >= BANDA_PREPARACION:
        return "en_preparacion"
    return "en_riesgo"


def calcular_ipe(exp, documentos, dia=None):
    """HU-15. Indice de Preparacion del Expediente, de 0 a 100:

        IPE = 0,5 * D + 0,3 * P + 0,2 * V

    D = documentos recibidos / requeridos por la categoria.
    P = plazo: en plazo o resuelto 100, por vencer 50, vencido 0 (semaforo HU-07).
    V = vigencia: 100 menos 25 por cada documento que vence en menos de 30 dias.

    Devuelve el indice, su banda (listo >= 80, en preparacion 50 a 79, en riesgo
    < 50), el desglose y las proximas acciones que salen de esas mismas reglas.
    """
    dia = dia or hoy()
    verif = calcular_verificacion(exp["categoria"], documentos)
    semaforo = calcular_semaforo(exp, dia)
    vencen = documentos_por_vencer(documentos, dia)

    d = 100 * verif["completos"] / verif["total_requeridos"]
    p = PUNTOS_PLAZO[semaforo["estado_semaforo"]]
    v = max(0, 100 - PENALIZACION_VIGENCIA * len(vencen))
    ipe = _redondear(PESO_DOCUMENTOS * d + PESO_PLAZO * p + PESO_VIGENCIA * v)
    banda = banda_ipe(ipe)

    acciones = []
    if exp["estado"] not in ESTADOS_RESUELTOS:
        for carpeta in verif["faltantes"]:
            acciones.append({"tipo": "documento", "texto": f"Subir {carpeta}"})
        restantes = semaforo["dias_restantes_legales"]
        if semaforo["estado_semaforo"] == "vencido":
            acciones.append({"tipo": "plazo", "texto": f"El plazo legal venció hace {abs(restantes)} días"})
        elif semaforo["estado_semaforo"] == "por_vencer":
            acciones.append({"tipo": "plazo", "texto": f"El plazo legal vence en {restantes} días"})
        for carpeta, restan in vencen:
            texto = (f"{carpeta} venció hace {abs(restan)} días" if restan < 0
                     else f"{carpeta} vence en {restan} días")
            acciones.append({"tipo": "vigencia", "texto": texto})
        if exp["estado"] == "pendiente" and verif["puede_someter"]:
            acciones.append({"tipo": "flujo", "texto": "Pedir la aprobación interna al jefe"})
        elif exp["estado"] == "aprobado_interno":
            acciones.append({"tipo": "flujo", "texto": "Someter el expediente a MiAmbiente"})
        elif exp["estado"] == "evaluacion":
            acciones.append({"tipo": "flujo", "texto": "Esperar y registrar la resolución de MiAmbiente"})

    return {
        "ipe": ipe,
        "banda": banda,
        "banda_texto": BANDAS_TEXTO[banda],
        "componentes": {"documentos": _redondear(d), "plazo": p, "vigencia": v},
        "acciones": acciones,
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
