"""Equipo de consultores (Sprint 9): alta, baja logica y reasignacion, ejecutando
el codigo real con una base simulada, sin MySQL. Complementa los casos de Robot,
que si usan la base de verdad.

Correr con:  python -m unittest tests/test_equipo.py
"""
import io
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from datetime import datetime

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with redirect_stdout(io.StringIO()):
    from app import app  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

from permisos import bd, seguridad  # noqa: E402
from permisos.config import ACCION_REASIGNAR  # noqa: E402
from permisos.rutas import auth, equipo  # noqa: E402

bd._estado_bd["lista"] = True
USUARIO_SESION_REAL = seguridad.usuario_sesion  # otras pruebas lo reemplazan y lo restauran
H = {"X-Requested-With": "fetch"}


class CursorFalso:
    """Responde en el orden en que la prueba preparo las filas y anota el SQL."""

    def __init__(self, uno=(), todos=(), lastrowid=77):
        self.uno = list(uno)
        self.todos = list(todos)
        self.ejecutadas = []  # [(sql, params)]
        self.lastrowid = lastrowid

    def execute(self, sql, params=None):
        self.ejecutadas.append((" ".join(sql.split()), params))
        return 1

    def fetchone(self):
        return self.uno.pop(0) if self.uno else None

    def fetchall(self):
        return self.todos.pop(0) if self.todos else []

    def sql_con(self, trozo):
        return [(s, p) for s, p in self.ejecutadas if trozo in s]


def usar(modulo, cursor_falso):
    @contextmanager
    def _cursor():
        yield cursor_falso
    modulo.cursor = _cursor


def sesion(rol):
    seguridad.usuario_sesion = lambda: {"id": 1, "email": "x@ejemplo.com", "rol": rol, "nombre": "X",
                                        "debe_cambiar_clave": False}


class Base(unittest.TestCase):
    def setUp(self):
        self.cliente = app.test_client()
        self.cursor_equipo = equipo.cursor
        self.cursor_auth = auth.cursor
        self.cursor_seguridad = seguridad.cursor
        self.esquema = dict(bd._esquema)
        bd._esquema.update(activo=True, cambio_clave=True)
        auth._fallos.clear()

    def tearDown(self):
        equipo.cursor = self.cursor_equipo
        auth.cursor = self.cursor_auth
        seguridad.cursor = self.cursor_seguridad
        seguridad.usuario_sesion = USUARIO_SESION_REAL
        bd._esquema.clear()
        bd._esquema.update(self.esquema)


class SoloElJefe(Base):
    def test_consultor_y_promotor_reciben_403_en_todas_las_rutas(self):
        for rol in ("consultor", "promotor"):
            sesion(rol)
            for metodo, ruta, cuerpo in [("get", "/consultores", None),
                                         ("post", "/consultores", {"nombre": "A", "email": "a@b.co"}),
                                         ("post", "/consultores/5/desactivar", None),
                                         ("post", "/consultores/5/activar", None),
                                         ("post", "/consultores/5/reasignar", {"destino_id": 6})]:
                r = getattr(self.cliente, metodo)(ruta, headers=H, **({"json": cuerpo} if cuerpo else {}))
                self.assertEqual(r.status_code, 403, f"{rol} {metodo} {ruta}")

    def test_sin_sesion_recibe_401(self):
        seguridad.usuario_sesion = lambda: None
        self.assertEqual(self.cliente.get("/consultores").status_code, 401)


class Alta(Base):
    def alta(self, cuerpo, existente=None):
        sesion("jefe")
        cur = CursorFalso(uno=[existente])
        usar(equipo, cur)
        return self.cliente.post("/consultores", json=cuerpo, headers=H), cur

    def test_alta_sin_clave_genera_una_temporal_y_la_muestra_una_vez(self):
        r, cur = self.alta({"nombre": " Ana Perez ", "email": "ANA@Ejemplo.com"})
        self.assertEqual(r.status_code, 201)
        cuerpo = r.get_json()
        self.assertEqual(cuerpo["email"], "ana@ejemplo.com")
        self.assertTrue(cuerpo["password_temporal"])
        insert, params = cur.sql_con("INSERT INTO usuarios")[0]
        self.assertIn("debe_cambiar_clave", insert)  # debe cambiarla en su primer ingreso
        self.assertEqual(params[0:2], ("Ana Perez", "ana@ejemplo.com"))
        self.assertTrue(check_password_hash(params[2], cuerpo["password_temporal"]))
        self.assertIn("'consultor'", insert)

    def test_alta_con_clave_propia_no_la_devuelve(self):
        r, cur = self.alta({"nombre": "Ana", "email": "ana@ejemplo.com", "password": "Segura2026x"})
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("password_temporal", r.get_json())
        self.assertTrue(check_password_hash(cur.sql_con("INSERT INTO usuarios")[0][1][2], "Segura2026x"))

    def test_clave_debil_se_rechaza_y_no_inserta(self):
        r, cur = self.alta({"nombre": "Ana", "email": "ana@ejemplo.com", "password": "123"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(cur.sql_con("INSERT"), [])

    def test_datos_incompletos_o_correo_invalido(self):
        self.assertEqual(self.alta({})[0].status_code, 400)
        self.assertEqual(self.alta({"nombre": "Ana"})[0].status_code, 400)
        self.assertEqual(self.alta({"nombre": "Ana", "email": "no-es-correo"})[0].status_code, 400)

    def test_correo_repetido_da_409(self):
        r, cur = self.alta({"nombre": "Ana", "email": "ana@ejemplo.com"}, existente={"id": 3})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(cur.sql_con("INSERT"), [])

    def test_sin_la_columna_de_cambio_de_clave_el_alta_igual_funciona(self):
        bd._esquema["cambio_clave"] = False
        r, cur = self.alta({"nombre": "Ana", "email": "ana@ejemplo.com"})
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("debe_cambiar_clave", cur.sql_con("INSERT INTO usuarios")[0][0])


class Listado(Base):
    def test_activos_primero_y_cada_grupo_por_nombre(self):
        sesion("jefe")
        fecha = datetime(2026, 11, 1)
        usar(equipo, CursorFalso(todos=[[
            {"id": 1, "nombre": "Zoe", "email": "z@e.com", "fecha_creacion": fecha, "activo": 1, "expedientes": 2},
            {"id": 2, "nombre": "Ana", "email": "a@e.com", "fecha_creacion": fecha, "activo": 0, "expedientes": 4},
            {"id": 3, "nombre": "Beto", "email": "b@e.com", "fecha_creacion": None, "activo": 1, "expedientes": 0},
        ]]))
        r = self.cliente.get("/consultores", headers=H)
        self.assertEqual(r.status_code, 200)
        lista = r.get_json()["consultores"]
        self.assertEqual([c["nombre"] for c in lista], ["Beto", "Zoe", "Ana"])
        self.assertEqual([c["activo"] for c in lista], [True, True, False])
        self.assertEqual(lista[0]["fecha_creacion"], None)
        self.assertEqual(lista[2]["expedientes"], 4)


class BajaLogica(Base):
    def cambiar(self, accion, activo_actual):
        sesion("jefe")
        cur = CursorFalso(uno=[{"id": 5, "nombre": "Ana", "email": "a@e.com", "activo": activo_actual}])
        usar(equipo, cur)
        return self.cliente.post(f"/consultores/5/{accion}", headers=H), cur

    def test_desactivar_marca_activo_en_falso_y_no_borra(self):
        r, cur = self.cambiar("desactivar", 1)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cur.sql_con("UPDATE usuarios SET activo")[0][1], (False, 5))
        self.assertEqual(cur.sql_con("DELETE"), [])  # baja logica: nada se borra

    def test_activar_marca_activo_en_verdadero(self):
        r, cur = self.cambiar("activar", 0)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cur.sql_con("UPDATE usuarios SET activo")[0][1], (True, 5))

    def test_repetir_la_accion_da_409_y_no_actualiza(self):
        r, cur = self.cambiar("desactivar", 0)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(cur.sql_con("UPDATE"), [])
        r, cur = self.cambiar("activar", 1)
        self.assertEqual(r.status_code, 409)

    def test_consultor_inexistente_da_404(self):
        sesion("jefe")
        usar(equipo, CursorFalso(uno=[None]))
        self.assertEqual(self.cliente.post("/consultores/99/desactivar", headers=H).status_code, 404)

    def test_sin_la_columna_activo_responde_503(self):
        bd._esquema["activo"] = False
        r, _ = self.cambiar("desactivar", 1)
        self.assertEqual(r.status_code, 503)
        self.assertIn("sprint9_manual.sql", r.get_json()["mensaje"])


class Reasignacion(Base):
    ORIGEN_BAJA = {"id": 5, "nombre": "Ana", "email": "a@e.com", "activo": 0}
    DESTINO = {"id": 6, "nombre": "Beto", "activo": 1}

    def reasignar(self, cuerpo, uno, todos=()):
        sesion("jefe")
        cur = CursorFalso(uno=uno, todos=todos)
        usar(equipo, cur)
        return self.cliente.post("/consultores/5/reasignar", json=cuerpo, headers=H), cur

    def test_pasa_los_expedientes_y_deja_una_entrada_de_historial_por_cada_uno(self):
        r, cur = self.reasignar({"destino_id": 6}, [self.ORIGEN_BAJA, self.DESTINO],
                                todos=[[{"id": 10}, {"id": 11}, {"id": 12}]])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["reasignados"], 3)
        self.assertEqual(cur.sql_con("UPDATE expedientes SET usuario_id")[0][1], (6, 5))
        historial = cur.sql_con("INSERT INTO historial_expediente")
        self.assertEqual([p[0] for _, p in historial], [10, 11, 12])
        self.assertTrue(all(p[1] == 1 and p[2] == ACCION_REASIGNAR for _, p in historial))  # a nombre del jefe

    def test_sin_expedientes_no_actualiza_nada(self):
        r, cur = self.reasignar({"destino_id": 6}, [self.ORIGEN_BAJA, self.DESTINO], todos=[[]])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["reasignados"], 0)
        self.assertEqual(cur.sql_con("UPDATE"), [])

    def test_si_el_consultor_sigue_activo_primero_hay_que_desactivarlo(self):
        r, cur = self.reasignar({"destino_id": 6}, [dict(self.ORIGEN_BAJA, activo=1)])
        self.assertEqual(r.status_code, 409)
        self.assertEqual(cur.sql_con("UPDATE"), [])

    def test_el_destino_debe_ser_otro_activo_y_existir(self):
        self.assertEqual(self.reasignar({"destino_id": 5}, [self.ORIGEN_BAJA])[0].status_code, 400)
        self.assertEqual(self.reasignar({"destino_id": 6}, [self.ORIGEN_BAJA, None])[0].status_code, 400)
        r, cur = self.reasignar({"destino_id": 6}, [self.ORIGEN_BAJA, dict(self.DESTINO, activo=0)])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(cur.sql_con("UPDATE"), [])

    def test_destino_faltante_o_que_no_es_numero_da_400(self):
        self.assertEqual(self.reasignar({}, [])[0].status_code, 400)
        self.assertEqual(self.reasignar({"destino_id": "abc"}, [])[0].status_code, 400)


class CuentaDesactivada(Base):
    def usuario(self, activo):
        return {"id": 5, "email": "ana@ejemplo.com", "password_hash": generate_password_hash("Clave1234x"),
                "rol": "consultor", "nombre": "Ana", "debe_cambiar_clave": 0, "activo": activo}

    def login(self, activo, password="Clave1234x"):
        auth.cursor = lambda: _cm(CursorFalso(uno=[self.usuario(activo)]))
        return self.cliente.post("/login", json={"email": "ana@ejemplo.com", "password": password})

    def test_cuenta_desactivada_no_inicia_sesion_ni_deja_cookie(self):
        r = self.login(activo=0)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.get_json()["acceso"])
        self.assertIn("desactivada", r.get_json()["mensaje"])
        with self.cliente.session_transaction() as s:
            self.assertNotIn("uid", s)

    def test_cuenta_activa_inicia_sesion(self):
        self.assertEqual(self.login(activo=1).status_code, 200)

    def test_con_clave_incorrecta_no_revela_que_esta_desactivada(self):
        self.assertEqual(self.login(activo=0, password="Otra1234x").status_code, 401)

    def test_la_sesion_abierta_de_un_consultor_desactivado_deja_de_valer(self):
        seguridad.cursor = lambda: _cm(CursorFalso(uno=[{"id": 5, "email": "a@e.com", "rol": "consultor",
                                                         "nombre": "Ana", "debe_cambiar_clave": 0, "activo": 0}]))
        with app.test_request_context():
            from flask import session
            session["uid"] = 5
            self.assertIsNone(USUARIO_SESION_REAL())
            self.assertNotIn("uid", session)

    def test_la_sesion_de_un_consultor_activo_sigue_valiendo(self):
        seguridad.cursor = lambda: _cm(CursorFalso(uno=[{"id": 5, "email": "a@e.com", "rol": "consultor",
                                                         "nombre": "Ana", "debe_cambiar_clave": 0, "activo": 1}]))
        with app.test_request_context():
            from flask import session
            session["uid"] = 5
            u = USUARIO_SESION_REAL()
            self.assertEqual(u["id"], 5)
            self.assertNotIn("activo", u)  # el dato interno no sale al resto de la app


@contextmanager
def _cm(cur):
    yield cur


if __name__ == "__main__":
    unittest.main()
