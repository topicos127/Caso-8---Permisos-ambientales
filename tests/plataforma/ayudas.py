"""Ayudas en Python para la suite Robot de la plataforma."""
import io
import os
import re
import struct
import sys
import time
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from permisos import totp  # noqa: E402


def codigo_totp(secreto, pasos_adelante=0):
    """Codigo de 6 digitos de la app autenticadora. Con pasos_adelante=1 se obtiene el del
    siguiente periodo de 30 s (el servidor acepta +-1), util para no repetir el que ya se uso."""
    return totp.codigo_en(secreto, totp.paso_actual() + int(pasos_adelante))


def sufijo_unico():
    return str(int(time.time() * 1000))[-9:]


def png_minimo():
    """Un PNG valido de 1x1 pixel (bytes), para probar la subida del logo."""
    def trozo(tipo, datos):
        cuerpo = tipo + datos
        return struct.pack(">I", len(datos)) + cuerpo + struct.pack(">I", zlib.crc32(cuerpo) & 0xFFFFFFFF)
    cabecera = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    imagen = zlib.compress(b"\x00\x17\x80\x5a")
    return b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", cabecera) + trozo(b"IDAT", imagen) + trozo(b"IEND", b"")


def textos_de_xlsx(contenido):
    """Todo el texto de un .xlsx (hojas y cadenas compartidas), para buscar codigos dentro."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        partes = [z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml")]
    return re.sub(r"<[^>]+>", " ", " ".join(partes))


def es_zip(contenido):
    return zipfile.is_zipfile(io.BytesIO(contenido))


def nombres_en_zip(contenido):
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        return z.namelist()


def texto_del_zip(contenido, nombre):
    """Texto de un archivo dentro de un ZIP (si es un .xlsx, todo su texto; si no, el archivo decodificado)."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        datos = z.read(nombre)
    return textos_de_xlsx(datos) if nombre.endswith(".xlsx") else datos.decode("utf-8", "replace")
