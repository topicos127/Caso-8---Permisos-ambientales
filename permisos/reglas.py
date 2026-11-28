"""Reglas del negocio sin Flask ni base de datos: se prueban solas
(ver tests/test_semaforo.py)."""
import math
import os
from datetime import date, datetime, timedelta

from .config import CATEGORIAS_DOCS, ESTADOS_RESUELTOS, PLAZOS_LEGALES, ZONA


# HU-05 (Sprint 10): cada documento puede traer su fecha de vencimiento real.
# Si no la trae, se supone que vence al ano de subido (regla del Sprint 9).
# El aviso es de 30 dias por defecto; cada usuario puede elegir 15, 30 o 45.
VIGENCIA_DOCUMENTO_DIAS = 365
AVISO_VENCIMIENTO_DIAS = 30
AVISOS_PERMITIDOS = (15, 30, 45)

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
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        return datetime.strptime(valor[:10], "%Y-%m-%d").date()
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


def vencimiento_documento(d):
    """HU-05. Fecha de vencimiento real si el documento la trae; si no, un ano
    despues de subido. None si el documento no se ha recibido."""
    if d.get("estado") != "recibido":
        return None
    if d.get("fecha_vencimiento"):
        return como_fecha(d["fecha_vencimiento"])
    if d.get("fecha_subida"):
        return como_fecha(d["fecha_subida"]) + timedelta(days=VIGENCIA_DOCUMENTO_DIAS)
    return None


def documentos_por_vencer(documentos, dia=None, aviso=AVISO_VENCIMIENTO_DIAS):
    """HU-05. Documentos recibidos que vencen dentro del aviso (o ya vencieron):
    [(carpeta, dias_restantes)] del mas urgente al menos."""
    dia = dia or hoy()
    salida = []
    for d in documentos:
        vence = vencimiento_documento(d)
        if not vence:
            continue
        restantes = (vence - dia).days
        if restantes < aviso:
            salida.append((d["carpeta"], restantes))
    return sorted(salida, key=lambda x: x[1])


def plural(n, uno, varios):
    """La cantidad con su palabra en singular o plural: plural(1, 'dia', 'dias') -> '1 dia'; plural(3, ...) -> '3 dias'."""
    return f"{n} {uno if n == 1 else varios}"


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
            acciones.append({"tipo": "plazo", "texto": f"El plazo legal venció hace {plural(abs(restantes), 'día', 'días')}"})
        elif semaforo["estado_semaforo"] == "por_vencer":
            acciones.append({"tipo": "plazo", "texto": "El plazo legal vence hoy" if restantes == 0
                             else f"El plazo legal vence en {plural(restantes, 'día', 'días')}"})
        for carpeta, restan in vencen:
            texto = (f"{carpeta} venció hace {plural(abs(restan), 'día', 'días')}" if restan < 0
                     else f"{carpeta} vence hoy" if restan == 0
                     else f"{carpeta} vence en {plural(restan, 'día', 'días')}")
            acciones.append({"tipo": "vigencia", "texto": texto})
        if exp["estado"] == "pendiente" and verif["puede_someter"]:
            acciones.append({"tipo": "flujo", "texto": "Pedir la aprobación interna al director de proyectos"})
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


# ---------- HU-08 (Sprint 10): dias habiles con los feriados de Panama ----------

def _domingo_de_pascua(anio):
    """Algoritmo anonimo gregoriano (Meeus/Jones/Butcher)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes = (h + m - 7 * n + 114) // 31
    dia = (h + m - 7 * n + 114) % 31 + 1
    return date(anio, mes, dia)


# Dias de fiesta nacional del Codigo de Trabajo de Panama (art. 46), mes y dia.
FERIADOS_FIJOS = ((1, 1), (1, 9), (5, 1), (11, 3), (11, 5), (11, 10), (11, 28), (12, 8), (12, 25))


def _feriados_extra():
    """FERIADOS_EXTRA=2026-12-20,2026-11-04: dias que decrete el gobierno."""
    salida = set()
    for parte in os.environ.get("FERIADOS_EXTRA", "").split(","):
        parte = parte.strip()
        if parte:
            try:
                salida.add(datetime.strptime(parte, "%Y-%m-%d").date())
            except ValueError:
                print(f"AVISO: FERIADOS_EXTRA tiene una fecha invalida: {parte!r}", flush=True)
    return salida


_cache_feriados = {}


def feriados_panama(anio):
    """Feriados nacionales del anio: los fijos, el martes de carnaval y el
    viernes santo (moviles, segun la Pascua), mas FERIADOS_EXTRA."""
    if anio not in _cache_feriados:
        pascua = _domingo_de_pascua(anio)
        dias = {date(anio, m, d) for m, d in FERIADOS_FIJOS}
        dias.add(pascua - timedelta(days=47))  # martes de carnaval
        dias.add(pascua - timedelta(days=2))   # viernes santo
        dias |= {f for f in _feriados_extra() if f.year == anio}
        _cache_feriados[anio] = dias
    return _cache_feriados[anio]


def es_dia_habil(dia):
    return dia.weekday() < 5 and dia not in feriados_panama(dia.year)


def dias_habiles_entre(inicio, fin):
    """Dias habiles despues de inicio y hasta fin (incluido). Negativo si fin
    es anterior a inicio. El dia del sometimiento no cuenta."""
    if fin == inicio:
        return 0
    signo, desde, hasta = (1, inicio, fin) if fin > inicio else (-1, fin, inicio)
    n, d = 0, desde
    while d < hasta:
        d += timedelta(days=1)
        if es_dia_habil(d):
            n += 1
    return signo * n


def sumar_dias_habiles(inicio, cantidad):
    d, n = inicio, 0
    while n < cantidad:
        d += timedelta(days=1)
        if es_dia_habil(d):
            n += 1
    return d


def calcular_semaforo(exp, dia=None):
    """HU-07 y HU-08. Devuelve el estado del plazo legal de un expediente.

    Sprint 10 (HU-08): desde que el expediente se somete, el plazo es el de
    MiAmbiente y corre en dias habiles desde la fecha de sometimiento (sin
    fines de semana ni feriados). Antes de someter se mantiene la medida del
    Sprint 9: dias calendario desde el ingreso, como plazo de preparacion, para
    que el semaforo y el IPE sigan avisando a la consultora."""
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

    dia = dia or hoy()
    sometido = como_fecha(exp.get("fecha_sometimiento"))
    if sometido:
        transcurridos = dias_habiles_entre(sometido, dia)
        base.update(base_plazo="sometimiento", tipo_dias="habiles", fecha_inicio=sometido.isoformat(),
                    fecha_limite=sumar_dias_habiles(sometido, limite).isoformat())
    else:
        inicio = como_fecha(exp["fecha_ingreso"])
        transcurridos = (dia - inicio).days
        base.update(base_plazo="ingreso", tipo_dias="calendario", fecha_inicio=inicio.isoformat(),
                    fecha_limite=(inicio + timedelta(days=limite)).isoformat())
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
