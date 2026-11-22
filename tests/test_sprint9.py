"""Pruebas unitarias del Sprint 9 que no necesitan MySQL: se reemplaza la
conexion por una base simulada en memoria.

Correr con:  python -m unittest tests/test_sprint9.py
"""
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"  # sin base real: lo que la toque usa el simulador
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io  # noqa: E402

with __import__("contextlib").redirect_stdout(io.StringIO()):
    from app import app  # noqa: E402
from permisos import bd  # noqa: E402
from permisos.config import ESTADO_PUBLICO, LOGIN_MAX_FALLOS  # noqa: E402
from permisos import seguridad  # noqa: E402
from permisos.rutas import auth, expedientes, publico  # noqa: E402

bd._estado_bd["lista"] = True  # no intentar preparar la base en cada peticion


class CursorFalso:
    """Devuelve, en orden, las filas que la prueba le preparo."""

    def __init__(self, filas):
        self.filas = list(filas)
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        return 1

    def fetchone(self):
        return self.filas.pop(0) if self.filas else None

    def fetchall(self):
        return []


def base_falsa(*filas):
    cur = CursorFalso(filas)

    @contextmanager
    def _cursor():
        yield cur
    return _cursor, cur


class LimiteDeLogin(unittest.TestCase):
    def setUp(self):
        auth._fallos.clear()
        self.original = auth.cursor
        self.cliente = app.test_client()

    def tearDown(self):
        auth.cursor = self.original

    def login(self, email="nadie@ejemplo.com", password="Mala1234"):
        auth.cursor, _ = base_falsa(None)  # usuario inexistente
        return self.cliente.post("/login", json={"email": email, "password": password})

    def test_bloquea_tras_el_maximo_de_fallos(self):
        for _ in range(LOGIN_MAX_FALLOS):
            self.assertEqual(self.login().status_code, 401)
        r = self.login()
        self.assertEqual(r.status_code, 429)
        self.assertIn("Demasiados intentos", r.get_json()["mensaje"])

    def test_otro_correo_no_queda_bloqueado(self):
        for _ in range(LOGIN_MAX_FALLOS):
            self.login("victima@ejemplo.com")
        self.assertEqual(self.login("otra@ejemplo.com").status_code, 401)


class ConsultaPublica(unittest.TestCase):
    def setUp(self):
        self.original = publico.cursor
        self.cliente = app.test_client()

    def tearDown(self):
        publico.cursor = self.original

    def fila(self, acceso):
        return {"codigo": "SP-A8-2026-001", "proyecto": "Planta Solar Azuero", "promotor": "Energía Verde S.A.",
                "categoria": "II", "estado": "aprobado_interno", "acceso_publico": acceso,
                "consultor": "Consultor Uno"}

    def test_sin_acceso_publico_no_entrega_datos(self):
        publico.cursor, _ = base_falsa(self.fila(0))
        r = self.cliente.get("/consulta/SP-A8-2026-001")
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("expediente", r.get_json())

    def test_con_acceso_publico_muestra_consultor_y_estado_publico(self):
        publico.cursor, _ = base_falsa(self.fila(1))
        exp = self.cliente.get("/consulta/SP-A8-2026-001").get_json()["expediente"]
        self.assertEqual(exp["consultor"], "Consultor Uno")
        self.assertEqual(exp["estado_publico"], "Pendiente de subsanación")
        self.assertTrue(exp["acceso_publico"])

    def test_tres_estados_de_hu07(self):
        self.assertEqual({ESTADO_PUBLICO[e] for e in ("pendiente", "aprobado_interno", "evaluacion", "aprobado")},
                         {"Pendiente de subsanación", "En evaluación", "Aprobado"})


class RegistroYCuentas(unittest.TestCase):
    def test_el_promotor_no_se_registra_solo(self):
        r = app.test_client().post("/registro", json={"nombre": "P", "email": "p@ejemplo.com",
                                                      "password": "Clave1234", "rol": "promotor"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Rol no permitido", r.get_json()["mensaje"])

    def test_contrasena_temporal_cumple_la_politica(self):
        from permisos.reglas import problema_de_password
        claves = {expedientes.contrasena_temporal() for _ in range(50)}
        self.assertEqual(len(claves), 50)  # no se repiten
        for c in claves:
            self.assertIsNone(problema_de_password(c), c)


class ContrasenaTemporal(unittest.TestCase):
    """Un promotor con contrasena temporal solo puede ver su sesion y cambiarla."""

    def setUp(self):
        self.original = seguridad.usuario_sesion
        self.cliente = app.test_client()

    def tearDown(self):
        seguridad.usuario_sesion = self.original

    def como(self, debe_cambiar):
        seguridad.usuario_sesion = lambda: {"id": 7, "email": "p@ejemplo.com", "rol": "promotor",
                                            "nombre": "Promotor", "debe_cambiar_clave": debe_cambiar}

    def test_bloquea_el_resto_de_la_api(self):
        self.como(True)
        for ruta in ("/dashboard", "/expedientes", "/expedientes/SP-A8-2026-001"):
            r = self.cliente.get(ruta)
            self.assertEqual(r.status_code, 403, ruta)
            self.assertTrue(r.get_json()["cambio_clave_obligatorio"], ruta)

    def test_deja_ver_la_sesion_y_avisa_que_debe_cambiarla(self):
        self.como(True)
        r = self.cliente.get("/sesion")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["debe_cambiar_clave"])

    def test_deja_llegar_al_cambio_de_contrasena(self):
        self.como(True)
        r = self.cliente.post("/cuenta/contrasena", json={})  # 400 por datos, no 403: la ruta esta permitida
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("cambio_clave_obligatorio", r.get_json())

    def test_la_contrasena_nueva_debe_ser_distinta(self):
        self.como(True)
        r = self.cliente.post("/cuenta/contrasena", json={"actual": "Temporal123", "nueva": "Temporal123"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("distinta", r.get_json()["mensaje"])

    def test_sin_la_marca_no_se_bloquea(self):
        self.como(False)
        r = self.cliente.get("/sesion")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["debe_cambiar_clave"])


if __name__ == "__main__":
    unittest.main()
