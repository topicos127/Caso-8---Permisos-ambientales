"""Innovacion del Sprint 10: calendario de plazos del expediente (.ics).

Un archivo iCalendar (RFC 5545) con el limite legal del expediente y el
vencimiento de cada documento recibido, para que el consultor o el promotor
reciban el aviso en su propio calendario (Google Calendar, Outlook) sin entrar
al sistema. Sin Flask ni base de datos: se prueba solo.

Reglas del formato que exigen Google y Outlook: lineas terminadas en CRLF,
lineas de mas de 75 octetos plegadas, texto escapado, UID estable por evento
y DTSTAMP en UTC. Los eventos son de dia completo (VALUE=DATE).
"""
from datetime import timedelta

from .reglas import como_fecha, vencimiento_documento

PRODID = "-//Permisos Ambientales//Calendario de plazos//ES"
DOMINIO_UID = "permisos-ambientales"
AVISO_PLAZO_DIAS = 3      # recordatorio antes del limite legal
AVISO_DOCUMENTO_DIAS = 7  # recordatorio antes de que venza un documento


def escapar(texto):
    """RFC 5545, 3.3.11: barra, punto y coma, coma y saltos de linea."""
    return (str(texto).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def plegar(linea):
    """RFC 5545, 3.1: maximo 75 octetos por linea; la continuacion empieza
    con un espacio. Se corta sin partir un caracter UTF-8."""
    partes, actual, tam = [], "", 0
    for c in linea:
        n = len(c.encode("utf-8"))
        limite = 75 if not partes else 74  # la continuacion ya lleva el espacio
        if tam + n > limite:
            partes.append(actual)
            actual, tam = "", 0
        actual += c
        tam += n
    partes.append(actual)
    return "\r\n ".join(partes)


def _slug(texto):
    return "".join(c if c.isalnum() else "-" for c in texto.lower()).strip("-")


def _evento(uid, dia, resumen, descripcion, aviso_dias, sello):
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}@{DOMINIO_UID}",
        f"DTSTAMP:{sello}",
        f"DTSTART;VALUE=DATE:{dia.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(dia + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{escapar(resumen)}",
        f"DESCRIPTION:{escapar(descripcion)}",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escapar(resumen)}",
        f"TRIGGER:-P{aviso_dias}D",
        "END:VALARM",
        "END:VEVENT",
    ]


def eventos_del_expediente(exp, semaforo, documentos, dia):
    """[(uid, fecha, resumen, descripcion, aviso_dias)] del expediente.
    El limite legal solo si el plazo sigue corriendo; los documentos, solo los
    recibidos que aun no vencen."""
    eventos = []
    codigo, proyecto = exp["codigo"], exp["proyecto"]
    if semaforo["estado_semaforo"] != "resuelto" and semaforo.get("fecha_limite"):
        limite = como_fecha(semaforo["fecha_limite"])
        if semaforo.get("base_plazo") == "sometimiento":
            resumen = f"Vence el plazo de MiAmbiente · {codigo}"
            detalle = (f"{proyecto} (categoría {semaforo['categoria']}): {semaforo['limite_dias']} días hábiles "
                       f"desde el sometimiento del {como_fecha(semaforo['fecha_inicio']).strftime('%d/%m/%Y')}.")
        else:
            resumen = f"Vence el plazo de preparación · {codigo}"
            detalle = (f"{proyecto} (categoría {semaforo['categoria']}): {semaforo['limite_dias']} días desde el "
                       f"ingreso. Al someterlo, el plazo de MiAmbiente corre en días hábiles y este evento cambia.")
        eventos.append((f"{codigo}-plazo", limite, resumen, detalle, AVISO_PLAZO_DIAS))
    for d in documentos:
        vence = vencimiento_documento(d)
        if not vence or vence < dia:
            continue
        origen = "fecha de vencimiento del documento" if d.get("fecha_vencimiento") else \
            "estimado: un año desde que se subió"
        eventos.append((f"{codigo}-doc-{_slug(d['carpeta'])}", vence, f"Vence {d['carpeta']} · {codigo}",
                        f"{proyecto}: renovar {d['carpeta']} ({origen}).", AVISO_DOCUMENTO_DIAS))
    return sorted(eventos, key=lambda e: e[1])


def generar_ics(exp, semaforo, documentos, dia, ahora_utc):
    """Texto del archivo .ics, con CRLF al final de cada linea."""
    sello = ahora_utc.strftime("%Y%m%dT%H%M%SZ")
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
              f"X-WR-CALNAME:{escapar('Plazos ' + exp['codigo'])}", "X-WR-TIMEZONE:America/Panama"]
    for uid, fecha, resumen, descripcion, aviso in eventos_del_expediente(exp, semaforo, documentos, dia):
        lineas += _evento(uid, fecha, resumen, descripcion, aviso, sello)
    lineas.append("END:VCALENDAR")
    return "".join(plegar(l) + "\r\n" for l in lineas)
