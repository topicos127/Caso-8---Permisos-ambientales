"""Archivos subidos: disco local o almacenamiento compatible con S3.

ALMACENAMIENTO=local (por defecto) guarda en UPLOADS_DIR. ALMACENAMIENTO=s3
usa cualquier servicio con la API de S3 (Cloudflare R2, Backblaze B2, MinIO,
AWS S3) con URLs por ruta (endpoint/bucket/clave) y firma SigV4 propia, sin
dependencias. Las claves son las mismas rutas relativas de siempre
("SP-A8-2026-001/archivo.pdf"), asi que cambiar de un servicio a otro no toca la base.

Todos los archivos pasan por aqui: subir, descargar, ZIP del expediente,
huellas y el logo de cada empresa.
"""
import datetime
import hashlib
import hmac
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit

from . import config


class AlmacenamientoError(Exception):
    pass


def clave_valida(clave):
    """Solo rutas relativas dentro del almacen: sin '..', sin barra inicial ni letras de unidad."""
    if not clave or not isinstance(clave, str) or len(clave) > 500:
        return False
    normal = clave.replace("\\", "/")
    return not (normal.startswith("/") or ".." in normal.split("/") or ":" in normal or "\x00" in normal)


class Local:
    def _ruta(self, clave):
        if not clave_valida(clave):
            raise AlmacenamientoError("Ruta de archivo no valida.")
        return os.path.join(config.UPLOADS_DIR, *clave.replace("\\", "/").split("/"))

    def guardar(self, clave, datos):
        ruta = self._ruta(clave)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "wb") as f:
            f.write(datos)

    def leer(self, clave):
        if not clave_valida(clave):
            return None
        ruta = self._ruta(clave)
        if not os.path.isfile(ruta):
            return None
        with open(ruta, "rb") as f:
            return f.read()

    def existe(self, clave):
        return clave_valida(clave) and os.path.isfile(self._ruta(clave))

    def borrar(self, clave):
        if clave_valida(clave):
            try:
                os.remove(self._ruta(clave))
            except OSError:
                pass

    def salud(self):
        return os.path.isdir(config.UPLOADS_DIR) and os.access(config.UPLOADS_DIR, os.W_OK)

    def listar(self, prefijo=""):
        raiz = config.UPLOADS_DIR
        for carpeta, _, archivos in os.walk(raiz):
            for nombre in archivos:
                clave = os.path.relpath(os.path.join(carpeta, nombre), raiz).replace(os.sep, "/")
                if clave.startswith(prefijo):
                    yield clave


class S3:
    def __init__(self):
        if not (config.S3_ENDPOINT and config.S3_BUCKET and config.S3_ACCESS_KEY and config.S3_SECRET_KEY):
            raise AlmacenamientoError("Falta configurar S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY y S3_SECRET_KEY.")
        self.endpoint = config.S3_ENDPOINT.rstrip("/")
        self.host = urlsplit(self.endpoint).netloc

    @staticmethod
    def _hmac(clave, texto):
        return hmac.new(clave, texto.encode(), hashlib.sha256).digest()

    def _peticion(self, metodo, clave, cuerpo=b"", tipo=None, consulta=""):
        if not clave_valida(clave) and clave != "":
            raise AlmacenamientoError("Ruta de archivo no valida.")
        ahora = datetime.datetime.now(datetime.timezone.utc)
        fecha, sello = ahora.strftime("%Y%m%d"), ahora.strftime("%Y%m%dT%H%M%SZ")
        ruta = f"/{config.S3_BUCKET}" + (f"/{quote(clave, safe='/-_.~')}" if clave else "")
        hash_cuerpo = hashlib.sha256(cuerpo).hexdigest()
        cabeceras = {"host": self.host, "x-amz-content-sha256": hash_cuerpo, "x-amz-date": sello}
        firmadas = ";".join(sorted(cabeceras))
        canonico = "\n".join([metodo, ruta, consulta,
                              "".join(f"{k}:{cabeceras[k]}\n" for k in sorted(cabeceras)), firmadas, hash_cuerpo])
        alcance = f"{fecha}/{config.S3_REGION}/s3/aws4_request"
        a_firmar = "\n".join(["AWS4-HMAC-SHA256", sello, alcance, hashlib.sha256(canonico.encode()).hexdigest()])
        k = self._hmac(("AWS4" + config.S3_SECRET_KEY).encode(), fecha)
        for parte in (config.S3_REGION, "s3", "aws4_request"):
            k = self._hmac(k, parte)
        firma = hmac.new(k, a_firmar.encode(), hashlib.sha256).hexdigest()
        enviar = {"x-amz-content-sha256": hash_cuerpo, "x-amz-date": sello,
                  "Authorization": (f"AWS4-HMAC-SHA256 Credential={config.S3_ACCESS_KEY}/{alcance}, "
                                    f"SignedHeaders={firmadas}, Signature={firma}")}
        if tipo:
            enviar["Content-Type"] = tipo
        url = f"{self.endpoint}{ruta}" + (f"?{consulta}" if consulta else "")
        req = urllib.request.Request(url, data=cuerpo if metodo in ("PUT", "POST") else None, method=metodo,
                                     headers=enviar)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, TimeoutError) as e:
            raise AlmacenamientoError(f"No se pudo conectar con el almacenamiento: {e}")

    def guardar(self, clave, datos):
        estado, cuerpo = self._peticion("PUT", clave, datos, "application/octet-stream")
        if estado not in (200, 201, 204):
            raise AlmacenamientoError(f"El almacenamiento rechazo el archivo ({estado}).")

    def leer(self, clave):
        if not clave_valida(clave):
            return None
        estado, cuerpo = self._peticion("GET", clave)
        if estado == 404:
            return None
        if estado != 200:
            raise AlmacenamientoError(f"No se pudo leer el archivo ({estado}).")
        return cuerpo

    def existe(self, clave):
        if not clave_valida(clave):
            return False
        estado, _ = self._peticion("HEAD", clave)
        return estado == 200

    def borrar(self, clave):
        if clave_valida(clave):
            try:
                self._peticion("DELETE", clave)
            except AlmacenamientoError:
                pass

    def salud(self):
        """El servicio responde y las credenciales valen (un 404 de un archivo inexistente es buena senal)."""
        try:
            estado, _ = self._peticion("HEAD", "salud.sonda")
        except AlmacenamientoError:
            return False
        return estado in (200, 404)

    def listar(self, prefijo=""):
        token = ""
        while True:
            # SigV4 exige los parametros en orden alfabetico.
            consulta = (f"continuation-token={quote(token, safe='')}&" if token else "") + "list-type=2"                 + (f"&prefix={quote(prefijo, safe='')}" if prefijo else "")
            estado, cuerpo = self._peticion("GET", "", consulta=consulta)
            if estado != 200:
                raise AlmacenamientoError(f"No se pudo listar el almacenamiento ({estado}).")
            texto = cuerpo.decode("utf-8", "replace")
            for m in re.finditer(r"<Key>(.*?)</Key>", texto):
                yield m.group(1)
            siguiente = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", texto)
            if not siguiente:
                break
            token = siguiente.group(1)


_instancia = {"almacen": None, "modo": None}


def almacen():
    """El almacen configurado (se crea una vez; cambia solo si cambia ALMACENAMIENTO)."""
    if _instancia["almacen"] is None or _instancia["modo"] != config.ALMACENAMIENTO:
        _instancia["almacen"] = S3() if config.ALMACENAMIENTO == "s3" else Local()
        _instancia["modo"] = config.ALMACENAMIENTO
    return _instancia["almacen"]


def reiniciar():
    _instancia["almacen"] = None
