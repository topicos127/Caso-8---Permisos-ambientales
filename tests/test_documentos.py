"""HU-01 (Sprint 9): revision de seguridad de los archivos, codigo de
trazabilidad y regla de que un documento no se elimina.

Correr con:  python -m unittest tests/test_documentos.py
"""
import io
import os
import sys
import tempfile
import unittest
import zipfile
import zlib
from contextlib import redirect_stdout

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with redirect_stdout(io.StringIO()):
    from app import app  # noqa: E402
from permisos import bd, seguridad  # noqa: E402
from permisos.inspeccion import problema_archivo, problema_pdf, problema_zip  # noqa: E402
from permisos.rutas.documentos import codigo_trazabilidad  # noqa: E402

bd._estado_bd["lista"] = True

PDF_LIMPIO = (b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /Fit] >>\nendobj\n"
              b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n%%EOF\n")


def pdf_con(texto):
    return b"%PDF-1.4\n1 0 obj\n" + texto + b"\nendobj\n%%EOF\n"


def pdf_con_stream(contenido):
    comprimido = zlib.compress(contenido)
    return (b"%PDF-1.5\n1 0 obj\n<< /Type /ObjStm /Filter /FlateDecode /Length "
            + str(len(comprimido)).encode() + b" >>\nstream\n" + comprimido + b"\nendstream\nendobj\n%%EOF\n")


def zip_con(entradas, comprimir=zipfile.ZIP_DEFLATED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", comprimir) as zf:
        for nombre, datos in entradas:
            if isinstance(nombre, zipfile.ZipInfo):
                zf.writestr(nombre, datos)
            else:
                zf.writestr(nombre, datos)
    return buf.getvalue()


SHAPEFILE = [("mapa/area.shp", b"\x00\x00\x27\x0a" + b"0" * 100), ("mapa/area.shx", b"\x00\x00\x27\x0a"),
             ("mapa/area.dbf", b"\x03dbf"), ("mapa/area.prj", b"GEOGCS[...]")]


class RevisionPdf(unittest.TestCase):
    def test_un_pdf_normal_se_acepta(self):
        self.assertIsNone(problema_pdf(PDF_LIMPIO))  # /OpenAction solo para el zoom es normal

    def test_javascript_se_rechaza(self):
        self.assertIn("JavaScript", problema_pdf(pdf_con(b"<< /S /JavaScript /JS (app.alert(1)) >>")))

    def test_launch_se_rechaza(self):
        self.assertIn("Launch", problema_pdf(pdf_con(b"<< /S /Launch /F (cmd.exe) >>")))

    def test_archivo_incrustado_se_rechaza(self):
        self.assertIsNotNone(problema_pdf(pdf_con(b"<< /Type /EmbeddedFile /Length 10 >>")))

    def test_nombre_camuflado_con_escapes_se_rechaza(self):
        self.assertIsNotNone(problema_pdf(pdf_con(b"<< /S /Java#53cript /J#53 (x) >>")))

    def test_script_dentro_de_un_objeto_comprimido_se_rechaza(self):
        self.assertIsNotNone(problema_pdf(pdf_con_stream(b"<< /S /JavaScript /JS (app.alert(1)) >>")))

    def test_stream_comprimido_normal_se_acepta(self):
        self.assertIsNone(problema_pdf(pdf_con_stream(b"BT /F1 12 Tf (Linea base) Tj ET")))

    def test_un_nombre_parecido_no_es_falso_positivo(self):
        self.assertIsNone(problema_pdf(pdf_con(b"<< /JSON (dato) /JSX 1 >>")))

    def test_extension_pdf_con_contenido_zip_se_rechaza(self):
        self.assertIn("no es un PDF", problema_archivo(".pdf", zip_con(SHAPEFILE)))


class RevisionZip(unittest.TestCase):
    def test_cartografia_normal_se_acepta(self):
        self.assertIsNone(problema_zip(zip_con(SHAPEFILE + [("informe.pdf", PDF_LIMPIO)])))

    def test_ejecutable_se_rechaza(self):
        self.assertIn("ejecutable", problema_zip(zip_con(SHAPEFILE + [("setup.exe", b"MZ\x90\x00")])))

    def test_script_se_rechaza(self):
        self.assertIn("script", problema_zip(zip_con([("mapa/ver.js", b"alert(1)")])))
        self.assertIn("script", problema_zip(zip_con([("leeme.html", b"<script>")])))

    def test_ejecutable_renombrado_se_rechaza_por_su_firma(self):
        self.assertIn("ejecutable", problema_zip(zip_con([("datos.txt", b"MZ\x90\x00\x03")])))
        self.assertIn("ejecutable", problema_zip(zip_con([("notas.txt", b"#!/bin/sh\nrm -rf /")])))

    def test_ruta_que_sale_de_la_carpeta_se_rechaza(self):
        self.assertIn("ruta", problema_zip(zip_con([("../../app.py", b"x")])))

    def test_comprimido_dentro_se_rechaza(self):
        self.assertIn("comprimidos", problema_zip(zip_con([("otro.zip", b"PK\x03\x04")])))

    def test_pdf_con_script_dentro_del_zip_se_rechaza(self):
        problema = problema_zip(zip_con([("anexo.pdf", pdf_con(b"<< /JS (x) >>"))]))
        self.assertTrue(problema.startswith("anexo.pdf:"))

    def test_bomba_de_descompresion_se_rechaza(self):
        self.assertIn("bomba", problema_zip(zip_con([("relleno.dbf", b"\x00" * (5 * 1024 * 1024))])))

    def test_enlace_simbolico_se_rechaza(self):
        info = zipfile.ZipInfo("enlace")
        info.external_attr = 0o120777 << 16
        self.assertIn("enlace", problema_zip(zip_con([(info, b"/etc/passwd")])))

    def test_zip_danado_se_rechaza(self):
        self.assertIsNotNone(problema_zip(b"PK\x03\x04basura"))

    def test_extension_zip_con_contenido_pdf_se_rechaza(self):
        self.assertIn("no es un ZIP", problema_archivo(".zip", PDF_LIMPIO))


class Trazabilidad(unittest.TestCase):
    def test_formato_del_codigo(self):
        self.assertEqual(codigo_trazabilidad("SP-A8-2026-001", 12, 3, "7f3a9c1b" + "0" * 56),
                         "SP-A8-2026-001-D12-V3-7F3A9C1B")

    def test_dos_versiones_del_mismo_archivo_tienen_codigos_distintos(self):
        sha = "ab" * 32
        self.assertNotEqual(codigo_trazabilidad("X", 1, 1, sha), codigo_trazabilidad("X", 1, 2, sha))


class NoSeElimina(unittest.TestCase):
    def setUp(self):
        self.sesion = seguridad.usuario_sesion
        seguridad.usuario_sesion = lambda: {"id": 1, "email": "c@ejemplo.com", "rol": "consultor",
                                            "nombre": "C", "debe_cambiar_clave": False}

    def tearDown(self):
        seguridad.usuario_sesion = self.sesion

    def test_eliminar_responde_405(self):
        r = app.test_client().delete("/expedientes/SP-A8-2026-001/documentos/Plan%20de%20Manejo/eliminar",
                                     headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.status_code, 405)
        self.assertIn("nueva versión", r.get_json()["mensaje"])


if __name__ == "__main__":
    unittest.main()
