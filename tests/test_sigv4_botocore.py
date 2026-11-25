"""La firma SigV4 de permisos/almacenamiento.py debe ser idéntica a la de botocore, la
implementación de referencia de AWS. Así se comprueba que un servicio S3 real (R2, Backblaze,
MinIO, AWS) aceptará las peticiones sin tener uno a mano en la prueba.

Se omite si botocore no está instalado (no es una dependencia de la aplicación).
Correr con:  python -m unittest tests/test_sigv4_botocore.py
"""
import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from permisos import almacenamiento, config  # noqa: E402

try:
    import botocore.auth
    from botocore.auth import S3SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials
except ImportError:  # pragma: no cover
    botocore = None

FIJA = datetime.datetime(2026, 11, 24, 23, 0, 0, tzinfo=datetime.timezone.utc)
AJUSTES = (("S3_ENDPOINT", "http://almacen.local:9000"), ("S3_BUCKET", "permisos"), ("S3_REGION", "us-east-1"),
           ("S3_ACCESS_KEY", "AKIAEJEMPLO"), ("S3_SECRET_KEY", "secreto-de-prueba"))

CASOS = [
    ("GET", "SP-A8-2026-001/archivo.pdf", b"", ""),
    ("PUT", "SP-A8-2026-001/Línea Base.pdf", b"%PDF-1.4 contenido", ""),
    ("PUT", "organizaciones/3/logo-ab12cd34ef.png", b"\x89PNG\r\n", ""),
    ("DELETE", "SP-A8-2026-002/Evidencia Foro Público.zip", b"", ""),
    ("HEAD", "salud.sonda", b"", ""),
    ("GET", "", b"", "list-type=2"),
    ("GET", "", b"", "list-type=2&prefix=respaldos%2F"),
    ("GET", "", b"", "continuation-token=1abc%2Bdef%3D&list-type=2&prefix=respaldos%2F"),
    ("PUT", "a/b c/ñandú (1).pdf", b"x", ""),
]


class Respuesta:
    status = 200

    def read(self):
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@unittest.skipIf(botocore is None, "botocore no está instalado")
class FirmaIgualAFirmaDeAws(unittest.TestCase):
    def setUp(self):
        self.parches = [mock.patch.object(config, n, v) for n, v in AJUSTES]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def _nuestra(self, metodo, clave, cuerpo, consulta):
        reloj = mock.Mock()
        reloj.datetime.now.return_value = FIJA
        reloj.timezone.utc = datetime.timezone.utc
        with mock.patch.object(almacenamiento, "datetime", reloj), \
                mock.patch.object(almacenamiento.urllib.request, "urlopen", return_value=Respuesta()) as u:
            almacenamiento.S3()._peticion(metodo, clave, cuerpo, None, consulta)
        req = u.call_args[0][0]
        return req.full_url, req.get_header("Authorization")

    def _referencia(self, metodo, url, cuerpo):
        req = AWSRequest(method=metodo, url=url, data=cuerpo)
        with mock.patch.object(botocore.auth, "get_current_datetime", lambda *a, **k: FIJA):
            S3SigV4Auth(Credentials("AKIAEJEMPLO", "secreto-de-prueba"), "s3", "us-east-1").add_auth(req)
        return req.headers["Authorization"]

    def test_todas_las_peticiones_coinciden_con_botocore(self):
        for metodo, clave, cuerpo, consulta in CASOS:
            with self.subTest(metodo=metodo, clave=clave, consulta=consulta):
                url, nuestra = self._nuestra(metodo, clave, cuerpo, consulta)
                self.assertEqual(nuestra, self._referencia(metodo, url, cuerpo))


if __name__ == "__main__":
    unittest.main()
