"""HU-01 (Sprint 9): revision de seguridad de un archivo antes de guardarlo.

- PDF: no puede traer JavaScript, acciones que lancen programas, archivos
  incrustados ni contenido multimedia activo. Se revisan tambien los objetos
  comprimidos (FlateDecode) y los nombres escritos con escapes #xx, que son las
  formas habituales de esconder un script.
- ZIP: no puede traer ejecutables ni scripts (por extension o por su firma),
  rutas que salgan de la carpeta, enlaces simbolicos, entradas cifradas, otros
  comprimidos ni ser una bomba de descompresion. Los PDF que trae se revisan
  con la misma regla.

Cada funcion devuelve None si el archivo es aceptable, o el motivo del rechazo.
"""
import io
import os
import re
import zipfile
import zlib

# Nombres de PDF que activan contenido ejecutable (los mismos que marca pdfid).
NOMBRES_ACTIVOS_PDF = {b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/EmbeddedFiles", b"/RichMedia"}
_NOMBRE_PDF = re.compile(rb"/[^\s/<>\[\]()%{}]+")
_ESCAPE_PDF = re.compile(rb"#([0-9A-Fa-f]{2})")
_STREAM_PDF = re.compile(rb"(?<!end)stream\r?\n(.*?)endstream", re.S)
MAX_DESCOMPRIMIDO_PDF = 60 * 1024 * 1024  # total que se descomprime al revisar un PDF

EXTENSIONES_BLOQUEADAS_ZIP = {
    ".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".mjs",
    ".wsf", ".wsh", ".hta", ".scr", ".pif", ".msi", ".msp", ".jar", ".class", ".sh", ".bash", ".py",
    ".pyw", ".pl", ".rb", ".php", ".asp", ".aspx", ".jsp", ".html", ".htm", ".xhtml", ".svg", ".lnk",
    ".url", ".reg", ".cpl", ".app", ".apk", ".dmg", ".iso", ".img", ".docm", ".xlsm", ".pptm",
}
COMPRIMIDOS_ZIP = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".cab"}
FIRMAS_EJECUTABLES = (b"MZ", b"\x7fELF", b"#!", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe")
MAX_ENTRADAS_ZIP = 2000
MAX_DESCOMPRIMIDO_ZIP = 200 * 1024 * 1024
# descomprimido / comprimido, por entrada de mas de 1 MB. Un .dbf con mucho relleno
# llega a 100:1 sin ser malicioso; una bomba suele pasar de 1000:1.
MAX_PROPORCION_ZIP = 500


def _nombres_pdf(datos):
    for m in _NOMBRE_PDF.finditer(datos):
        yield _ESCAPE_PDF.sub(lambda h: bytes([int(h.group(1), 16)]), m.group(0))


def problema_pdf(datos):
    if not datos.startswith(b"%PDF"):
        return "El archivo no es un PDF válido."
    partes = [datos]
    presupuesto = MAX_DESCOMPRIMIDO_PDF
    for m in _STREAM_PDF.finditer(datos):
        if presupuesto <= 0:
            break
        try:
            plano = zlib.decompressobj().decompress(m.group(1), presupuesto)
        except zlib.error:
            continue  # imagenes u otros filtros: no traen objetos PDF
        presupuesto -= len(plano)
        partes.append(plano)
    for parte in partes:
        for nombre in _nombres_pdf(parte):
            if nombre in NOMBRES_ACTIVOS_PDF:
                return (f"El PDF contiene contenido activo ({nombre[1:].decode()}) y no se acepta. "
                        "Expórtelo de nuevo como PDF simple.")
    return None


def _ruta_insegura(nombre):
    nombre = nombre.replace("\\", "/")
    return nombre.startswith("/") or re.match(r"^[A-Za-z]:", nombre) or ".." in nombre.split("/")


def problema_zip(datos):
    if not datos.startswith(b"PK\x03\x04"):
        return "El archivo no es un ZIP válido."
    try:
        zf = zipfile.ZipFile(io.BytesIO(datos))
    except zipfile.BadZipFile:
        return "El ZIP está dañado."
    with zf:
        entradas = zf.infolist()
        if len(entradas) > MAX_ENTRADAS_ZIP:
            return f"El ZIP tiene más de {MAX_ENTRADAS_ZIP} archivos."
        total = 0
        for e in entradas:
            nombre = e.filename
            if _ruta_insegura(nombre):
                return f"El ZIP tiene una ruta no permitida: {nombre}"
            if (e.external_attr >> 16) & 0o170000 == 0o120000:
                return f"El ZIP contiene un enlace simbólico: {nombre}"
            if e.flag_bits & 0x1:
                return "El ZIP está protegido con contraseña y no se puede revisar."
            if e.is_dir():
                continue
            ext = os.path.splitext(nombre)[1].lower()
            if ext in EXTENSIONES_BLOQUEADAS_ZIP:
                return f"El ZIP contiene un archivo ejecutable o script: {nombre}"
            if ext in COMPRIMIDOS_ZIP:
                return f"El ZIP no puede contener otros comprimidos: {nombre}"
            total += e.file_size
            if total > MAX_DESCOMPRIMIDO_ZIP:
                return "El contenido del ZIP descomprimido supera los 200 MB."
            if e.file_size > 1024 * 1024 and e.file_size > MAX_PROPORCION_ZIP * max(e.compress_size, 1):
                return f"El ZIP tiene una compresión anómala (posible bomba de descompresión): {nombre}"
            try:
                with zf.open(e) as f:
                    contenido = f.read() if ext == ".pdf" else f.read(4)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error):
                return f"No se pudo leer {nombre} dentro del ZIP."
            if contenido.startswith(FIRMAS_EJECUTABLES):
                return f"El ZIP contiene un archivo ejecutable o script: {nombre}"
            if ext == ".pdf":
                problema = problema_pdf(contenido)
                if problema:
                    return f"{nombre}: {problema}"
    return None


def problema_archivo(ext, datos):
    """La extension debe coincidir con el contenido y el contenido ser seguro."""
    if ext == ".pdf":
        return problema_pdf(datos)
    if ext == ".zip":
        return problema_zip(datos)
    return "Solo se aceptan archivos PDF y ZIP."
