"""Prueba las rutas que usan el IPE (lista, detalle y panel) ejecutando el codigo
real con una base simulada, sin MySQL. Complementa las suites de Robot, que si
usan la base de verdad.

Correr con:  python -m unittest tests/test_ipe_api.py
"""
import io
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timedelta

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with redirect_stdout(io.StringIO()):
    from app import app  # noqa: E402
from permisos import bd, seguridad  # noqa: E402
from permisos.reglas import hoy  # noqa: E402
from permisos.rutas import dashboard, expedientes  # noqa: E402

bd._estado_bd["lista"] = True

HOY = hoy()


def fecha(dias_atras):
    return HOY - timedelta(days=dias_atras)


class BaseFalsa:
    """Responde segun un trozo del SQL, en el orden en que se declararon."""

    def __init__(self, respuestas):
        self.respuestas = respuestas  # [(trozo de SQL, "uno" | "todos", valor)]
        self.actual = None

    def execute(self, sql, params=None):
        self.actual = next((r for r in self.respuestas if r[0] in sql), None)
        return 1

    def fetchone(self):
        return self.actual[2] if self.actual and self.actual[1] == "uno" else None

    def fetchall(self):
        return self.actual[2] if self.actual and self.actual[1] == "todos" else []


def usar(modulo, respuestas):
    base = BaseFalsa(respuestas)

    @contextmanager
    def _cursor():
        yield base
    modulo.cursor = _cursor


def sesion(rol, email="x@ejemplo.com"):
    seguridad.usuario_sesion = lambda: {"id": 1, "email": email, "rol": rol, "nombre": "X",
                                        "debe_cambiar_clave": False}


# Tres expedientes (categoria I, 20 dias de plazo):
#   1 completo y en plazo -> IPE 100; 2 sin documentos y en plazo -> 50; 3 aprobado (resuelto)
FILAS = [
    {"id": 1, "codigo": "A-1", "proyecto": "Completo", "promotor": "P", "categoria": "I", "estado": "pendiente",
     "fecha_ingreso": fecha(2), "consultor": "C1"},
    {"id": 2, "codigo": "A-2", "proyecto": "Vacio", "promotor": "P", "categoria": "I", "estado": "pendiente",
     "fecha_ingreso": fecha(3), "consultor": "C1"},
    {"id": 3, "codigo": "A-3", "proyecto": "Resuelto", "promotor": "P", "categoria": "I", "estado": "aprobado",
     "fecha_ingreso": fecha(30), "consultor": "C2"},
]


def doc(expediente_id, carpeta, recibido):
    return {"expediente_id": expediente_id, "carpeta": carpeta, "estado": "recibido" if recibido else "pendiente",
            "fecha_subida": datetime.now() - timedelta(days=1) if recibido else None}


DOCS = ([doc(1, c, True) for c in ("Línea Base", "Plan de Manejo", "Anexos Legales")]
        + [doc(2, c, False) for c in ("Línea Base", "Plan de Manejo", "Anexos Legales")]
        + [doc(3, c, True) for c in ("Línea Base", "Plan de Manejo", "Anexos Legales")])


class ListaConIpe(unittest.TestCase):
    def setUp(self):
        self.cliente = app.test_client()
        self.cursor = expedientes.cursor
        self.sesion = seguridad.usuario_sesion
        usar(expedientes, [("COUNT(*)", "uno", {"total": 3}), ("FROM expedientes e LEFT JOIN", "todos",
                                                              [dict(f) for f in FILAS]),
                           ("FROM documentos", "todos", DOCS)])

    def tearDown(self):
        expedientes.cursor = self.cursor
        seguridad.usuario_sesion = self.sesion

    def test_ordena_de_menor_a_mayor_y_deja_los_resueltos_al_final(self):
        sesion("jefe")
        r = self.cliente.get("/expedientes?orden=ipe")
        self.assertEqual(r.status_code, 200)
        filas = r.get_json()["expedientes"]
        self.assertEqual([f["codigo"] for f in filas], ["A-2", "A-1", "A-3"])
        self.assertEqual([f["ipe"]["valor"] for f in filas], [50, 100, 100])
        self.assertEqual(filas[0]["ipe"]["banda"], "en_preparacion")
        self.assertEqual(filas[1]["ipe"]["banda_texto"], "Listo")
        self.assertNotIn("id", filas[0])  # el id interno no sale

    def test_pagina_despues_de_ordenar(self):
        sesion("consultor")
        r = self.cliente.get("/expedientes?orden=ipe&per_page=1&page=2")
        self.assertEqual([f["codigo"] for f in r.get_json()["expedientes"]], ["A-1"])
        self.assertEqual(r.get_json()["paginacion"]["total"], 3)

    def test_sin_orden_trae_el_ipe_pero_no_reordena(self):
        sesion("consultor")
        filas = self.cliente.get("/expedientes").get_json()["expedientes"]
        self.assertEqual([f["codigo"] for f in filas], ["A-1", "A-2", "A-3"])
        self.assertTrue(all("ipe" in f for f in filas))

    def test_el_promotor_no_recibe_el_ipe(self):
        sesion("promotor")
        filas = self.cliente.get("/expedientes?orden=ipe").get_json()["expedientes"]
        self.assertEqual(len(filas), 3)
        self.assertTrue(all("ipe" not in f for f in filas))

    def test_orden_invalido_da_400(self):
        sesion("jefe")
        self.assertEqual(self.cliente.get("/expedientes?orden=inventado").status_code, 400)


class DetalleConIpe(unittest.TestCase):
    def setUp(self):
        self.cliente = app.test_client()
        self.cursor = expedientes.cursor
        self.sesion = seguridad.usuario_sesion
        self.original_cargar = expedientes.cargar_expediente
        exp = {"id": 2, "codigo": "A-2", "proyecto": "Vacio", "promotor": "P", "promotor_email": "p@ejemplo.com",
               "categoria": "I", "estado": "pendiente", "fecha_ingreso": fecha(3), "usuario_id": 1,
               "acceso_publico": 1}
        expedientes.cargar_expediente = lambda cur, codigo: dict(exp)
        usar(expedientes, [("FROM documentos", "todos",
                            [dict(d, id=i) for i, d in enumerate(DOCS[3:6])]),
                           ("FROM aprobaciones", "uno", None)])

    def tearDown(self):
        expedientes.cursor = self.cursor
        expedientes.cargar_expediente = self.original_cargar
        seguridad.usuario_sesion = self.sesion

    def test_la_consultora_ve_el_ipe_con_sus_acciones(self):
        sesion("consultor")
        r = self.cliente.get("/expedientes/A-2")
        self.assertEqual(r.status_code, 200)
        ipe = r.get_json()["ipe"]
        self.assertEqual(ipe["ipe"], 50)
        self.assertEqual([a["texto"] for a in ipe["acciones"]],
                         ["Subir Línea Base", "Subir Plan de Manejo", "Subir Anexos Legales"])
        self.assertEqual(r.get_json()["expediente"]["fecha_ingreso"], fecha(3).strftime("%d/%m/%Y"))
        self.assertEqual(r.get_json()["expediente"]["promotor_email"], "p@ejemplo.com")

    def test_el_promotor_ni_el_ipe_ni_el_correo(self):
        sesion("promotor", "p@ejemplo.com")  # el promotor del expediente
        cuerpo = self.cliente.get("/expedientes/A-2").get_json()
        self.assertIsNone(cuerpo["ipe"])
        self.assertNotIn("promotor_email", cuerpo["expediente"])


class PanelConPrioridades(unittest.TestCase):
    def setUp(self):
        self.cliente = app.test_client()
        self.cursor = dashboard.cursor
        self.sesion = seguridad.usuario_sesion
        abiertos = [dict(f) for f in FILAS if f["estado"] != "aprobado"]
        usar(dashboard, [
            ("COUNT(*) AS activos", "uno", {"activos": 3, "pendientes": 2, "aprobados": 1}),
            ("ORDER BY e.fecha_ingreso DESC", "todos", [{"codigo": "A-1", "proyecto": "Completo", "estado": "pendiente"}]),
            ("NOT IN ('aprobado'", "todos", abiertos),
            ("WHERE expediente_id IN", "todos", [d for d in DOCS if d["expediente_id"] != 3]),  # solo los pedidos
            ("FROM documentos d JOIN", "todos", []),
        ])

    def tearDown(self):
        dashboard.cursor = self.cursor
        seguridad.usuario_sesion = self.sesion

    def test_el_jefe_recibe_las_prioridades_ordenadas(self):
        sesion("jefe")
        r = self.cliente.get("/dashboard")
        self.assertEqual(r.status_code, 200)
        p = r.get_json()["prioridades"]
        self.assertEqual([x["codigo"] for x in p], ["A-2", "A-1"])
        self.assertEqual(p[0]["proxima_accion"], "Subir Línea Base")
        self.assertEqual(p[1]["proxima_accion"], "Pedir la aprobación interna al jefe")
        self.assertEqual(r.get_json()["metricas"]["activos"], 3)

    def test_el_promotor_recibe_la_lista_vacia(self):
        sesion("promotor")
        self.assertEqual(self.cliente.get("/dashboard").get_json()["prioridades"], [])


if __name__ == "__main__":
    unittest.main()
