"""Pruebas del script de datos de demostracion (scripts/demo_produccion.py), sin base de datos:
valida que los datos definidos sean coherentes y que los archivos que genera los acepte la propia aplicacion."""
import hashlib
import importlib.util
import os
import sys
import unittest
import zlib
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from permisos import config, inspeccion  # noqa: E402
from permisos.rutas.organizaciones import _tipo_logo  # noqa: E402

_spec = importlib.util.spec_from_file_location("demo_produccion", os.path.join(RAIZ, "scripts", "demo_produccion.py"))
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

ESTADOS_QUE_PASARON_POR_APROBACION = ("aprobado_interno", "evaluacion", "aprobado", "rechazado")
ESTADOS_SOMETIDOS = ("evaluacion", "aprobado", "rechazado")


class DatosDeDemostracion(unittest.TestCase):

    def test_hay_dos_empresas_con_la_gente_prometida(self):
        self.assertEqual([e["nombre"] for e in demo.EMPRESAS], ["Consultora Ambiental Istmo", "EcoGestión del Pacífico"])
        for e in demo.EMPRESAS:
            self.assertEqual(len(e["directores"]), 2, e["nombre"])
            self.assertEqual(len(e["consultores"]), 3, e["nombre"])
            self.assertTrue(e["ruc"].startswith(demo.MARCA_DEMO), "el RUC marca lo que es demostración")
            self.assertRegex(e["color"], r"^#[0-9a-f]{6}$")
            self.assertIn(e["color"], config.COLORES_EMPRESA)
        self.assertEqual([len(e["clientes"]) for e in demo.EMPRESAS], [3, 2])
        self.assertEqual([len(demo.EXPEDIENTES[e["clave"]]) for e in demo.EMPRESAS], [12, 8])

    def test_los_correos_son_validos_y_no_se_repiten(self):
        correos = []
        for e in demo.EMPRESAS:
            gente = e["directores"] + e["consultores"] + [(n, u) for n, u, _ in e["clientes"]]
            correos += [f"{u}@{e['dominio']}" for _, u in gente]
        self.assertEqual(len(correos), len(set(correos)))
        for c in correos:
            self.assertRegex(c, config.EMAIL_RE.pattern, c)

    def test_cada_expediente_es_coherente_con_su_estado(self):
        for e in demo.EMPRESAS:
            for fila in demo.EXPEDIENTES[e["clave"]]:
                proyecto, cliente, cat, estado, dias, consultor, n_docs, somet, resol, publico, extras = fila
                with self.subTest(proyecto=proyecto):
                    total = len(config.CATEGORIAS_DOCS[cat])
                    self.assertLessEqual(n_docs, total)
                    self.assertTrue(1 <= cliente <= len(e["clientes"]))
                    self.assertTrue(1 <= consultor <= len(e["consultores"]))
                    if estado in ESTADOS_QUE_PASARON_POR_APROBACION or extras.get("devuelto"):
                        self.assertEqual(n_docs, total, "para aprobarlo internamente la documentación debe estar completa")
                    self.assertEqual(somet is not None, estado in ESTADOS_SOMETIDOS)
                    self.assertEqual(resol is not None, estado in ("aprobado", "rechazado"))
                    if resol:
                        self.assertEqual(resol[0], estado)
                        self.assertLess(resol[1], somet, "la resolución es posterior al sometimiento")
                    if somet is not None:
                        self.assertLess(somet, dias, "se somete después de ingresar")
                    if extras.get("nueva_version"):
                        self.assertEqual(estado, "pendiente", "solo se suben versiones mientras está pendiente")
                    if extras.get("responsable"):
                        self.assertTrue(1 <= extras["responsable"] <= len(e["consultores"]))

    def test_hay_variedad_de_estados_y_categorias(self):
        for e in demo.EMPRESAS:
            filas = demo.EXPEDIENTES[e["clave"]]
            estados = {f[3] for f in filas}
            self.assertEqual(estados, {"pendiente", "aprobado_interno", "evaluacion", "aprobado", "rechazado"}, e["clave"])
            self.assertEqual({f[2] for f in filas}, {"I", "II", "III"}, e["clave"])

    def test_los_comentarios_apuntan_a_expedientes_que_existen(self):
        for e in demo.EMPRESAS:
            n = len(demo.EXPEDIENTES[e["clave"]])
            for numero, autor, texto, hace in demo.COMENTARIOS[e["clave"]]:
                self.assertTrue(1 <= numero <= n)
                self.assertTrue(autor in ("direccion", "director2") or autor.startswith("consultor"))
                self.assertTrue(texto and hace >= 0)


class ArchivosDeDemostracion(unittest.TestCase):

    def test_el_pdf_lo_acepta_la_revision_de_seguridad_y_es_unico_por_version(self):
        a = demo.pdf_demo("Empresa", "Proyecto Ñandú", "SP-A8-2026-001", "Línea Base", 1)
        b = demo.pdf_demo("Empresa", "Proyecto Ñandú", "SP-A8-2026-001", "Línea Base", 2)
        self.assertTrue(a.startswith(b"%PDF"))
        self.assertIsNone(inspeccion.problema_archivo(".pdf", a))
        self.assertNotEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())

    def test_el_zip_de_cartografia_trae_el_shapefile_completo(self):
        datos = demo.zip_cartografia("Proyecto")
        self.assertIsNone(inspeccion.problema_archivo(".zip", datos))
        self.assertIsNone(inspeccion.problema_cartografia(".zip", datos))

    def test_cada_carpeta_recibe_el_tipo_de_archivo_que_le_toca(self):
        for cat, carpetas in config.CATEGORIAS_DOCS.items():
            for carpeta in carpetas:
                nombre, contenido = demo.archivo_de(carpeta, "E", "P", "SP-A8-2026-001", 1)
                ext = os.path.splitext(nombre)[1]
                self.assertEqual(ext, ".zip" if carpeta == config.CARPETA_CARTOGRAFIA else ".pdf", carpeta)
                self.assertIsNone(inspeccion.problema_archivo(ext, contenido), carpeta)
                if carpeta == config.CARPETA_CARTOGRAFIA:
                    self.assertIsNone(inspeccion.problema_cartografia(ext, contenido))

    def test_el_logo_es_un_png_valido_que_la_app_reconoce(self):
        datos = demo.png_logo("#2563a8", 64)
        self.assertEqual(_tipo_logo(datos)[0], "png")
        # IDAT descomprime a (ancho*4 + 1 byte de filtro) * alto
        i = datos.index(b"IDAT")
        largo = int.from_bytes(datos[i - 4:i], "big")
        crudo = zlib.decompress(datos[i + 4:i + 4 + largo])
        self.assertEqual(len(crudo), 64 * (64 * 4 + 1))


class LineaDeTiempo(unittest.TestCase):

    def _eventos(self, estado, n_docs, extras):
        ev = [("crear",)] + [("doc", f"c{i}", 1) for i in range(n_docs)]
        if extras.get("nueva_version"):
            ev.append(("doc", "c0", 2))
        if estado in ESTADOS_QUE_PASARON_POR_APROBACION or extras.get("devuelto"):
            ev.append(("aprobar",))
        if extras.get("devuelto"):
            ev.append(("devolver",))
        if estado in ESTADOS_SOMETIDOS:
            ev.append(("someter",))
        if estado in ("aprobado", "rechazado"):
            ev.append(("resolver",))
        if extras.get("responsable"):
            ev.append(("responsable",))
        return ev

    def test_el_historial_va_en_orden_y_nunca_en_el_futuro(self):
        ahora = datetime(2026, 11, 28, 10, 30)
        hoy = ahora.date()
        for e in demo.EMPRESAS:
            for fila in demo.EXPEDIENTES[e["clave"]]:
                proyecto, _, _, estado, dias, _, n_docs, somet, resol, _, extras = fila
                with self.subTest(proyecto=proyecto):
                    spec = {"dias": dias, "somet": somet, "resol": resol}
                    ev = self._eventos(estado, n_docs, extras)
                    t = demo.linea_de_tiempo(spec, ev, hoy, ahora)
                    self.assertEqual(len(t), len(ev))
                    self.assertEqual(t, sorted(t), "cronológico")
                    self.assertLess(t[-1], ahora)
                    self.assertEqual(t[0].date(), hoy - timedelta(days=dias), "la creación es el día del ingreso")
                    if somet is not None:
                        i = [x[0] for x in ev].index("someter")
                        self.assertEqual(t[i].date(), hoy - timedelta(days=somet))
                    if resol:
                        i = [x[0] for x in ev].index("resolver")
                        self.assertEqual(t[i].date(), hoy - timedelta(days=resol[1]))


if __name__ == "__main__":
    unittest.main()
