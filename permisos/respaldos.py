"""Respaldos: la base de datos y los archivos en un solo ZIP, con restauracion.

Un respaldo es un ZIP con:
  manifiesto.json    fecha, version, tablas con su numero de filas, archivos incluidos y la huella
                     SHA-256 del volcado (la restauracion la comprueba antes de tocar nada)
  base_de_datos.sql  volcado completo (estructura + datos), escrito en Python puro: no hace falta
                     mysqldump en la imagen
  archivos/...       los documentos subidos (solo con almacenamiento local; con S3 los archivos
                     ya viven en el bucket y el ZIP trae la base de datos y el manifiesto)

Los ZIP se guardan en BACKUP_DIR (un volumen aparte del de uploads) y, con S3, tambien en el
bucket bajo "respaldos/". Se conservan los ultimos RESPALDOS_CONSERVAR.
Con RESPALDO_AUTOMATICO=true un hilo hace uno cada dia a RESPALDO_HORA (hora de Panama).
"""
import hashlib
import io
import json
import os
import re
import threading
import time
import zipfile
from datetime import datetime

import pymysql
from pymysql.converters import escape_item

from . import config
from .almacenamiento import AlmacenamientoError, almacen
from .config import BACKUP_DIR, DB_CONFIG, RESPALDO_HORA, RESPALDOS_CONSERVAR, ZONA

PREFIJO_REMOTO = "respaldos/"
NOMBRE_VALIDO = re.compile(r"^respaldo-\d{8}-\d{6}(-[a-z]+)?\.zip$")
LOTE_FILAS = 200

_candado = threading.Lock()  # un respaldo o una restauracion a la vez


class RespaldoError(Exception):
    pass


def _conexion():
    return pymysql.connect(**{**DB_CONFIG, "cursorclass": pymysql.cursors.Cursor})


def _ident(nombre):
    return "`" + nombre.replace("`", "``") + "`"


# ---------- Volcado y restauracion de la base ----------

def volcar_sql():
    """Devuelve (texto_sql, {tabla: filas}). Cada sentencia termina en ';' + salto de linea y
    los textos escapan sus saltos de linea, asi que separar por ';\\n' es seguro."""
    partes = ["-- Respaldo de Permisos Ambientales\n", "SET FOREIGN_KEY_CHECKS=0;\n", "SET NAMES utf8mb4;\n"]
    conteo = {}
    conn = _conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW FULL TABLES WHERE Table_type='BASE TABLE'")
            tablas = [f[0] for f in cur.fetchall()]
            for t in tablas:
                cur.execute(f"SHOW CREATE TABLE {_ident(t)}")
                partes.append(f"DROP TABLE IF EXISTS {_ident(t)};\n")
                partes.append(cur.fetchone()[1] + ";\n")
                cur.execute(f"SELECT * FROM {_ident(t)}")
                columnas = ", ".join(_ident(c[0]) for c in cur.description)
                total = 0
                while True:
                    filas = cur.fetchmany(LOTE_FILAS)
                    if not filas:
                        break
                    valores = ",\n".join("(" + ", ".join(escape_item(v, "utf8mb4") for v in fila) + ")"
                                         for fila in filas)
                    partes.append(f"INSERT INTO {_ident(t)} ({columnas}) VALUES\n{valores};\n")
                    total += len(filas)
                conteo[t] = total
        partes.append("SET FOREIGN_KEY_CHECKS=1;\n")
    finally:
        conn.close()
    return "".join(partes), conteo


def aplicar_sql(texto):
    """Ejecuta un volcado hecho por volcar_sql()."""
    sentencias = [s.strip() for s in texto.split(";\n")]
    conn = _conexion()
    try:
        with conn.cursor() as cur:
            for s in sentencias:
                if s and not all(linea.startswith("--") for linea in s.splitlines()):
                    cur.execute(s)
        conn.commit()
    finally:
        conn.close()


# ---------- Crear ----------

def _ahora():
    return datetime.now(ZONA).replace(tzinfo=None, microsecond=0)


def _archivos_de_usuarios():
    return [k for k in almacen().listar() if not k.startswith(PREFIJO_REMOTO)]


def crear(motivo=""):
    """Hace un respaldo ahora. `motivo` ("auto", "previo") se agrega al nombre. Devuelve su ficha."""
    with _candado:
        return _crear(motivo)


def _crear(motivo=""):
    ahora = _ahora()
    nombre = f"respaldo-{ahora:%Y%m%d-%H%M%S}" + (f"-{motivo}" if motivo else "") + ".zip"
    sql, conteo = volcar_sql()
    datos_sql = sql.encode("utf-8")
    incluir = config.ALMACENAMIENTO == "local"
    archivos = _archivos_de_usuarios() if incluir else []

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("base_de_datos.sql", datos_sql)
        copiados = 0
        for clave in archivos:
            contenido = almacen().leer(clave)
            if contenido is not None:
                z.writestr(f"archivos/{clave}", contenido)
                copiados += 1
        z.writestr("manifiesto.json", json.dumps({
            "creado": ahora.strftime("%Y-%m-%d %H:%M:%S"), "motivo": motivo or "manual",
            "almacenamiento": config.ALMACENAMIENTO, "tablas": conteo, "archivos": copiados,
            "archivos_incluidos": incluir, "huella_sql": hashlib.sha256(datos_sql).hexdigest(),
        }, ensure_ascii=False, indent=2))
    datos = buffer.getvalue()

    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(os.path.join(BACKUP_DIR, nombre), "wb") as f:
        f.write(datos)
    remoto = False
    if config.ALMACENAMIENTO == "s3":
        try:
            almacen().guardar(PREFIJO_REMOTO + nombre, datos)
            remoto = True
        except AlmacenamientoError as e:
            print(f"AVISO: el respaldo quedo solo en disco local ({e})", flush=True)
    _aplicar_retencion()
    return {"nombre": nombre, "tamano": len(datos), "tablas": len(conteo), "archivos": copiados,
            "filas": sum(conteo.values()), "copia_remota": remoto}


def _aplicar_retencion():
    """Borra los respaldos mas viejos (local y remoto) y deja los ultimos RESPALDOS_CONSERVAR."""
    for nombre in listar_nombres()[RESPALDOS_CONSERVAR:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, nombre))
        except OSError:
            pass
        if config.ALMACENAMIENTO == "s3":
            almacen().borrar(PREFIJO_REMOTO + nombre)


# ---------- Consultar ----------

def listar_nombres():
    """Nombres de respaldos, del mas nuevo al mas viejo (el nombre lleva la fecha)."""
    nombres = set()
    if os.path.isdir(BACKUP_DIR):
        nombres.update(n for n in os.listdir(BACKUP_DIR) if NOMBRE_VALIDO.match(n))
    if config.ALMACENAMIENTO == "s3":
        try:  # los que solo estan en el bucket (por ejemplo, tras reconstruir el servidor)
            nombres.update(k[len(PREFIJO_REMOTO):] for k in almacen().listar(PREFIJO_REMOTO)
                           if NOMBRE_VALIDO.match(k[len(PREFIJO_REMOTO):]))
        except AlmacenamientoError:
            pass
    return sorted(nombres, reverse=True)


def listar():
    fichas = []
    for n in listar_nombres():
        ruta = os.path.join(BACKUP_DIR, n)
        try:
            tamano = os.path.getsize(ruta)
        except OSError:
            tamano = None  # solo en el bucket: se baja al descargarlo o restaurarlo
        creado = datetime.strptime(n[9:24], "%Y%m%d-%H%M%S")
        fichas.append({"nombre": n, "creado": creado.strftime("%d/%m/%Y %H:%M"), "tamano": tamano,
                       "tipo": "automático" if n.endswith("-auto.zip") else
                       "previo a restaurar" if n.endswith("-previo.zip") else "manual"})
    return fichas


def ruta_de(nombre):
    """Ruta del ZIP, o None si el nombre no es de un respaldo (evita ../ y rutas ajenas)."""
    if not isinstance(nombre, str) or not NOMBRE_VALIDO.match(nombre):
        return None
    ruta = os.path.join(BACKUP_DIR, nombre)
    if not os.path.isfile(ruta) and config.ALMACENAMIENTO == "s3":
        try:  # solo estaba en el bucket: se baja a disco
            datos = almacen().leer(PREFIJO_REMOTO + nombre)
        except AlmacenamientoError:
            datos = None
        if datos:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            with open(ruta, "wb") as f:
                f.write(datos)
    return ruta if os.path.isfile(ruta) else None


def eliminar(nombre):
    if not isinstance(nombre, str) or not NOMBRE_VALIDO.match(nombre) or nombre not in listar_nombres():
        return False
    try:
        os.remove(os.path.join(BACKUP_DIR, nombre))
    except OSError:
        pass
    if config.ALMACENAMIENTO == "s3":
        almacen().borrar(PREFIJO_REMOTO + nombre)
    return True


def ultimo():
    f = listar()
    return f[0] if f else None


# ---------- Restaurar ----------

def _reconocer_esquema():
    """Un respaldo viejo puede traer tablas sin las columnas nuevas: se completan y se
    vuelven a leer las banderas de funciones."""
    from . import bd
    try:
        bd.inicializar_bd()
    except Exception as e:
        print(f"AVISO: no se pudo completar el esquema tras restaurar: {e!r}", flush=True)


def verificar(nombre):
    """Abre el ZIP y comprueba que esta completo y que el volcado no cambio. Devuelve el manifiesto."""
    ruta = ruta_de(nombre)
    if not ruta:
        raise RespaldoError("Respaldo no encontrado.")
    try:
        with zipfile.ZipFile(ruta) as z:
            if z.testzip() is not None:
                raise RespaldoError("El respaldo está dañado.")
            manifiesto = json.loads(z.read("manifiesto.json"))
            if hashlib.sha256(z.read("base_de_datos.sql")).hexdigest() != manifiesto.get("huella_sql"):
                raise RespaldoError("La huella del respaldo no coincide: el archivo fue alterado.")
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        raise RespaldoError(f"El respaldo no es válido ({e}).")
    return manifiesto


def restaurar(nombre):
    """Reemplaza la base y los archivos por los del respaldo. Antes hace un respaldo "previo"."""
    with _candado:
        manifiesto = verificar(nombre)
        previo = _crear("previo")
        with zipfile.ZipFile(ruta_de(nombre)) as z:
            aplicar_sql(z.read("base_de_datos.sql").decode("utf-8"))
            _reconocer_esquema()
            restaurados = 0
            if manifiesto.get("archivos_incluidos"):
                for item in z.namelist():
                    if item.startswith("archivos/") and not item.endswith("/"):
                        almacen().guardar(item[len("archivos/"):], z.read(item))
                        restaurados += 1
    return {"restaurado": nombre, "respaldo_previo": previo["nombre"], "archivos": restaurados,
            "tablas": len(manifiesto.get("tablas", {}))}


# ---------- Respaldo automatico ----------

_planificador = {"hilo": None}


def _hacer_si_toca():
    ahora = _ahora()
    if ahora.hour != RESPALDO_HORA:
        return
    hoy = f"respaldo-{ahora:%Y%m%d}-"
    if any(n.startswith(hoy) and n.endswith("-auto.zip") for n in listar_nombres()):
        return
    try:
        ficha = crear("auto")
        print(f"Respaldo automatico listo: {ficha['nombre']} ({ficha['tamano']} bytes)", flush=True)
    except Exception as e:  # el hilo no debe morir por un fallo puntual
        print(f"ERROR en el respaldo automatico: {e!r}", flush=True)


def iniciar_planificador():
    if _planificador["hilo"] is not None or not config.RESPALDO_AUTOMATICO:
        return

    def bucle():
        while True:
            time.sleep(60)
            _hacer_si_toca()

    hilo = threading.Thread(target=bucle, name="respaldo-automatico", daemon=True)
    hilo.start()
    _planificador["hilo"] = hilo
