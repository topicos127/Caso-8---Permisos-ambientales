"""Pruebas del Sprint 10: lo que paso del Sprint 9.

- HU-08: plazo de MiAmbiente en dias habiles desde el sometimiento, con los
  feriados de Panama, y aviso en el panel.
- HU-05: fecha de vencimiento real de cada documento y aviso de 15, 30 o 45 dias.
- HU-01: la cartografia es un ZIP con el shapefile completo (.shp, .shx, .dbf).
- Resolucion de MiAmbiente (aprobado o rechazado, con numero y fecha) y
  devolucion con observaciones del jefe.

Las reglas se prueban solas; las rutas, con una base simulada (sin MySQL).
Correr con:  python -m unittest tests/test_sprint10.py
"""
import io
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager, redirect_stdout
from datetime import date, timedelta

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with redirect_stdout(io.StringIO()):
    from app import app  # noqa: E402
from permisos import bd, reglas, seguridad  # noqa: E402
from permisos.inspeccion import problema_cartografia  # noqa: E402
from permisos.reglas import (_domingo_de_pascua, calcular_ipe, calcular_semaforo, dias_habiles_entre,  # noqa: E402
                             documentos_por_vencer, es_dia_habil, feriados_panama, hoy, sumar_dias_habiles,
                             vencimiento_documento)
from permisos.rutas import auth, dashboard, flujo  # noqa: E402

bd._estado_bd["lista"] = True


# ---------------------------------------------------------------- HU-08 ----

class DiasHabiles(unittest.TestCase):

    def test_pascua(self):
        self.assertEqual(_domingo_de_pascua(2025), date(2025, 4, 20))
        self.assertEqual(_domingo_de_pascua(2026), date(2026, 4, 5))
        self.assertEqual(_domingo_de_pascua(2027), date(2027, 3, 28))

    def test_feriados_moviles_y_fijos_2026(self):
        f = feriados_panama(2026)
        self.assertIn(date(2026, 2, 17), f)   # martes de carnaval
        self.assertIn(date(2026, 4, 3), f)    # viernes santo
        for dia in (date(2026, 1, 9), date(2026, 11, 3), date(2026, 11, 28), date(2026, 12, 25)):
            self.assertIn(dia, f)
        self.assertNotIn(date(2026, 11, 4), f)

    def test_fin_de_semana_y_feriado_no_son_habiles(self):
        self.assertFalse(es_dia_habil(date(2026, 11, 7)))   # sabado
        self.assertFalse(es_dia_habil(date(2026, 11, 3)))   # feriado
        self.assertTrue(es_dia_habil(date(2026, 11, 4)))

    def test_contar_dias_habiles(self):
        # Del lunes 02/11 al viernes 13/11 de 2026: el 3, el 5 y el 10 son feriados.
        self.assertEqual(dias_habiles_entre(date(2026, 11, 2), date(2026, 11, 13)), 6)
        self.assertEqual(dias_habiles_entre(date(2026, 11, 13), date(2026, 11, 2)), -6)
        self.assertEqual(dias_habiles_entre(date(2026, 11, 2), date(2026, 11, 2)), 0)
        # El dia del sometimiento no cuenta; un fin de semana tampoco.
        self.assertEqual(dias_habiles_entre(date(2026, 11, 20), date(2026, 11, 23)), 1)

    def test_sumar_dias_habiles(self):
        self.assertEqual(sumar_dias_habiles(date(2026, 11, 2), 5), date(2026, 11, 12))
        self.assertEqual(sumar_dias_habiles(date(2026, 11, 20), 1), date(2026, 11, 23))

    def test_feriados_extra_por_entorno(self):
        reglas._cache_feriados.pop(2031, None)
        os.environ["FERIADOS_EXTRA"] = "2031-12-20, fecha-mala"
        try:
            with redirect_stdout(io.StringIO()):
                self.assertIn(date(2031, 12, 20), feriados_panama(2031))
        finally:
            del os.environ["FERIADOS_EXTRA"]
            reglas._cache_feriados.pop(2031, None)


class SemaforoDesdeElSometimiento(unittest.TestCase):

    def expediente(self, categoria, sometido, estado="evaluacion"):
        return {"codigo": "SP-S10", "categoria": categoria, "estado": estado,
                "fecha_ingreso": date(2026, 9, 1), "fecha_sometimiento": sometido}

    def test_corre_en_dias_habiles_desde_el_sometimiento(self):
        s = calcular_semaforo(self.expediente("I", date(2026, 11, 2)), date(2026, 11, 13))
        self.assertEqual(s["base_plazo"], "sometimiento")
        self.assertEqual(s["tipo_dias"], "habiles")
        self.assertEqual(s["dias_transcurridos"], 6)
        self.assertEqual(s["dias_restantes_legales"], 14)
        self.assertEqual(s["estado_semaforo"], "en_plazo")
        self.assertEqual(s["fecha_inicio"], "2026-11-02")
        self.assertEqual(s["fecha_limite"], sumar_dias_habiles(date(2026, 11, 2), 20).isoformat())

    def test_por_vencer_y_vencido_en_dias_habiles(self):
        sometido = date(2026, 11, 2)
        limite = date.fromisoformat(calcular_semaforo(self.expediente("I", sometido), sometido)["fecha_limite"])
        self.assertEqual(calcular_semaforo(self.expediente("I", sometido), limite)["estado_semaforo"], "por_vencer")
        self.assertEqual(calcular_semaforo(self.expediente("I", sometido), limite)["dias_restantes_legales"], 0)
        despues = sumar_dias_habiles(limite, 1)
        self.assertEqual(calcular_semaforo(self.expediente("I", sometido), despues)["estado_semaforo"], "vencido")

    def test_sin_sometimiento_sigue_la_regla_del_sprint_9(self):
        exp = {"codigo": "SP-S10", "categoria": "II", "estado": "pendiente", "fecha_ingreso": date(2026, 11, 1)}
        s = calcular_semaforo(exp, date(2026, 11, 11))
        self.assertEqual(s["base_plazo"], "ingreso")
        self.assertEqual(s["tipo_dias"], "calendario")
        self.assertEqual(s["dias_transcurridos"], 10)
        self.assertEqual(s["fecha_limite"], "2026-12-11")

    def test_resuelto_no_cuenta_aunque_tenga_sometimiento(self):
        s = calcular_semaforo(self.expediente("III", date(2026, 1, 5), "rechazado"), date(2026, 11, 1))
        self.assertEqual(s["estado_semaforo"], "resuelto")


# ---------------------------------------------------------------- HU-05 ----

class VencimientoReal(unittest.TestCase):
    HOY = date(2026, 11, 24)

    def doc(self, carpeta, subido_hace, vence=None):
        return {"carpeta": carpeta, "estado": "recibido",
                "fecha_subida": self.HOY - timedelta(days=subido_hace), "fecha_vencimiento": vence}

    def test_fecha_real_gana_a_la_regla_del_anio(self):
        d = self.doc("Anexos Legales", 5, vence=self.HOY + timedelta(days=12))
        self.assertEqual(vencimiento_documento(d), self.HOY + timedelta(days=12))
        self.assertEqual(documentos_por_vencer([d], self.HOY), [("Anexos Legales", 12)])

    def test_sin_fecha_se_estima_un_anio(self):
        d = self.doc("Línea Base", 340)
        self.assertEqual(vencimiento_documento(d), self.HOY + timedelta(days=25))

    def test_pendiente_no_vence(self):
        self.assertIsNone(vencimiento_documento({"carpeta": "X", "estado": "pendiente"}))

    def test_aviso_configurable(self):
        docs = [self.doc("A", 1, vence=self.HOY + timedelta(days=20)),
                self.doc("B", 1, vence=self.HOY + timedelta(days=40))]
        self.assertEqual([c for c, _ in documentos_por_vencer(docs, self.HOY, aviso=15)], [])
        self.assertEqual([c for c, _ in documentos_por_vencer(docs, self.HOY, aviso=30)], ["A"])
        self.assertEqual([c for c, _ in documentos_por_vencer(docs, self.HOY, aviso=45)], ["A", "B"])

    def test_el_ipe_usa_la_fecha_real(self):
        exp = {"codigo": "X", "categoria": "I", "estado": "pendiente", "fecha_ingreso": self.HOY}
        docs = [self.doc(c, 1) for c in ("Línea Base", "Plan de Manejo")]
        docs.append(self.doc("Anexos Legales", 1, vence=self.HOY + timedelta(days=10)))
        r = calcular_ipe(exp, docs, self.HOY)
        self.assertEqual(r["componentes"]["vigencia"], 75)
        self.assertIn("Anexos Legales vence en 10 días", [a["texto"] for a in r["acciones"]])


# ---------------------------------------------------- HU-01 cartografia ----

def zip_con(nombres):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for n in nombres:
            zf.writestr(n, b"datos")
    return buffer.getvalue()


class Cartografia(unittest.TestCase):

    def test_shapefile_completo(self):
        self.assertIsNone(problema_cartografia(".zip", zip_con(["mapa/area.shp", "mapa/area.shx", "mapa/area.dbf",
                                                                  "mapa/area.prj"])))

    def test_falta_un_archivo(self):
        problema = problema_cartografia(".zip", zip_con(["area.shp", "area.dbf"]))
        self.assertIn(".shx", problema)

    def test_nombres_distintos(self):
        problema = problema_cartografia(".zip", zip_con(["a.shp", "b.shx", "c.dbf"]))
        self.assertIn("mismo nombre", problema)

    def test_pdf_no_sirve(self):
        self.assertIn("ZIP", problema_cartografia(".pdf", b"%PDF-1.4"))


# ------------------------------------------------- rutas (base simulada) ----

class BaseFalsa:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.actual = None
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
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
    return base


def sesion(rol, uid=1):
    seguridad.usuario_sesion = lambda: {"id": uid, "email": "x@ejemplo.com", "rol": rol, "nombre": "X",
                                        "debe_cambiar_clave": False}


def expediente(estado, usuario_id=1, sometido=None):
    return {"id": 7, "codigo": "SP-S10", "proyecto": "P", "promotor": "Pr", "promotor_email": None,
            "categoria": "I", "estado": estado, "fecha_ingreso": date(2026, 9, 1), "usuario_id": usuario_id,
            "acceso_publico": 1, "fecha_sometimiento": sometido}


class Resolucion(unittest.TestCase):

    def setUp(self):
        self.cliente = app.test_client()

    def post(self, datos):
        return self.cliente.post("/expedientes/SP-S10/resolucion", json=datos)

    def test_registra_rechazo_con_numero_y_fecha(self):
        sesion("jefe")
        base = usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("evaluacion"))])
        r = self.post({"resultado": "rechazado", "numero": "DEIA-123-2026", "fecha": hoy().isoformat()})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["estado"], "rechazado")
        sqls = " ".join(s for s, _ in base.sql)
        self.assertIn("INSERT INTO resoluciones", sqls)
        historial = [p for s, p in base.sql if "historial_expediente" in s]
        self.assertEqual(historial[0][2], "registró rechazo de MiAmbiente")

    def test_valida_resultado_numero_y_fecha(self):
        sesion("jefe")
        usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("evaluacion"))])
        self.assertEqual(self.post({"resultado": "talvez", "numero": "1", "fecha": "2026-11-01"}).status_code, 400)
        self.assertEqual(self.post({"resultado": "aprobado", "fecha": "2026-11-01"}).status_code, 400)
        self.assertEqual(self.post({"resultado": "aprobado", "numero": "1", "fecha": "01/11/2026"}).status_code, 400)
        manana = (hoy() + timedelta(days=1)).isoformat()
        self.assertEqual(self.post({"resultado": "aprobado", "numero": "1", "fecha": manana}).status_code, 400)

    def test_no_antes_del_sometimiento_ni_fuera_de_evaluacion(self):
        sesion("jefe")
        usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("evaluacion", sometido=hoy()))])
        ayer = (hoy() - timedelta(days=1)).isoformat()
        self.assertEqual(self.post({"resultado": "aprobado", "numero": "1", "fecha": ayer}).status_code, 400)
        usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("pendiente"))])
        self.assertEqual(self.post({"resultado": "aprobado", "numero": "1", "fecha": hoy().isoformat()}).status_code,
                         400)

    def test_consultor_ajeno_y_promotor_no_registran(self):
        usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("evaluacion", usuario_id=99))])
        datos = {"resultado": "aprobado", "numero": "1", "fecha": hoy().isoformat()}
        sesion("consultor")
        self.assertEqual(self.post(datos).status_code, 403)
        sesion("promotor")
        self.assertEqual(self.post(datos).status_code, 403)


class Devolver(unittest.TestCase):

    def setUp(self):
        self.cliente = app.test_client()

    def post(self, datos):
        return self.cliente.post("/expedientes/SP-S10/devolver", json=datos)

    def test_jefe_devuelve_un_aprobado_internamente(self):
        sesion("jefe")
        base = usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("aprobado_interno"))])
        r = self.post({"observaciones": "Falta la firma del promotor."})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["estado"], "pendiente")
        sqls = " ".join(s for s, _ in base.sql)
        self.assertIn("UPDATE expedientes SET estado='pendiente'", sqls)
        self.assertIn("INSERT INTO observaciones", sqls)

    def test_solo_el_jefe_y_con_observaciones(self):
        usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("pendiente"))])
        sesion("consultor")
        self.assertEqual(self.post({"observaciones": "x"}).status_code, 403)
        sesion("jefe")
        self.assertEqual(self.post({"observaciones": "  "}).status_code, 400)

    def test_no_se_devuelve_lo_ya_sometido(self):
        sesion("jefe")
        usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("evaluacion"))])
        self.assertEqual(self.post({"observaciones": "x"}).status_code, 400)


class Someter(unittest.TestCase):

    def test_guarda_la_fecha_de_sometimiento(self):
        sesion("jefe")
        base = usar(flujo, [("FROM expedientes WHERE codigo", "uno", expediente("aprobado_interno"))])
        bd._esquema["sometimiento"] = True
        try:
            r = app.test_client().post("/expedientes/SP-S10/someter", json={})
        finally:
            bd._esquema["sometimiento"] = False
        self.assertEqual(r.status_code, 200, r.get_json())
        update = next((s, p) for s, p in base.sql if s.startswith("UPDATE expedientes"))
        self.assertIn("fecha_sometimiento=%s", update[0])
        self.assertIn(hoy().isoformat(), update[1])


class Perfil(unittest.TestCase):

    def test_lee_el_aviso_por_defecto(self):
        sesion("consultor")
        usar(auth, [("FROM usuarios WHERE id", "uno", {"aviso_vencimiento_dias": 30})])
        r = app.test_client().get("/perfil")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["aviso_vencimiento_dias"], 30)
        self.assertEqual(r.get_json()["opciones_aviso"], [15, 30, 45])

    def test_cifras_reales_del_perfil(self):
        sesion("consultor")
        expedientes = [
            {"codigo": "A", "categoria": "I", "estado": "aprobado", "fecha_ingreso": hoy(), "fecha_sometimiento": None},
            {"codigo": "B", "categoria": "I", "estado": "pendiente", "fecha_ingreso": hoy() - timedelta(days=30),
             "fecha_sometimiento": None},  # vencido
            {"codigo": "C", "categoria": "III", "estado": "pendiente", "fecha_ingreso": hoy(), "fecha_sometimiento": None},
        ]
        usar(auth, [("FROM usuarios WHERE id", "uno", {"aviso_vencimiento_dias": 30, "fecha_creacion": None}),
                    ("FROM expedientes e WHERE", "todos", expedientes)])
        cifras = app.test_client().get("/perfil").get_json()["cifras"]
        self.assertEqual(cifras, {"expedientes": 3, "en_tramite": 2, "aprobados": 1, "plazos_en_alerta": 1})

    def test_solo_15_30_o_45(self):
        sesion("consultor")
        usar(auth, [])
        bd._esquema["aviso"] = True
        try:
            cliente = app.test_client()
            for malo in (10, "30", True, None):
                self.assertEqual(cliente.post("/perfil", json={"aviso_vencimiento_dias": malo}).status_code, 400)
            r = cliente.post("/perfil", json={"aviso_vencimiento_dias": 45})
        finally:
            bd._esquema["aviso"] = False
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["aviso_vencimiento_dias"], 45)


class AvisosDePlazo(unittest.TestCase):

    def test_el_promotor_recibe_el_aviso_del_plazo(self):
        sesion("promotor")
        abierto = {"id": 7, "codigo": "SP-S10", "proyecto": "Hotel", "categoria": "I", "estado": "evaluacion",
                   "fecha_ingreso": hoy() - timedelta(days=60),
                   "fecha_sometimiento": hoy() - timedelta(days=60)}  # muchos dias habiles: vencido
        usar(dashboard, [
            ("COUNT(*) AS activos", "uno", {"activos": 1, "pendientes": 0, "aprobados": 0}),
            ("ORDER BY e.fecha_ingreso DESC", "todos", []),
            ("FROM documentos d JOIN", "todos", []),
            ("FROM usuarios WHERE id", "uno", {"aviso_vencimiento_dias": 30}),
            ("NOT IN ('aprobado', 'rechazado')", "todos", [abierto]),
        ])
        r = app.test_client().get("/dashboard")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["prioridades"], [])  # el IPE sigue siendo solo de la consultora
        self.assertEqual(len(d["avisos_plazo"]), 1)
        self.assertEqual(d["avisos_plazo"][0]["estado_semaforo"], "vencido")
        self.assertEqual(d["avisos_plazo"][0]["base_plazo"], "sometimiento")

    def test_alertas_de_documentos_con_el_aviso_del_usuario(self):
        sesion("consultor")
        recibido = {"carpeta": "Anexos Legales", "estado": "recibido", "fecha_subida": hoy() - timedelta(days=2),
                    "fecha_vencimiento": hoy() + timedelta(days=40), "codigo": "SP-S10"}
        respuestas = [
            ("COUNT(*) AS activos", "uno", {"activos": 1, "pendientes": 1, "aprobados": 0}),
            ("ORDER BY e.fecha_ingreso DESC", "todos", []),
            ("FROM documentos d JOIN", "todos", [recibido]),
            ("FROM usuarios WHERE id", "uno", {"aviso_vencimiento_dias": 30}),
            ("NOT IN ('aprobado', 'rechazado')", "todos", []),
        ]
        usar(dashboard, respuestas)
        self.assertEqual(app.test_client().get("/dashboard").get_json()["alertas"], [])
        respuestas[3] = ("FROM usuarios WHERE id", "uno", {"aviso_vencimiento_dias": 45})
        usar(dashboard, respuestas)
        alertas = app.test_client().get("/dashboard").get_json()["alertas"]
        self.assertEqual(len(alertas), 1)
        self.assertTrue(alertas[0]["vencimiento_real"])


# ------------------------------------------- calendario de plazos (.ics) ----

class CalendarioDePlazos(unittest.TestCase):
    from datetime import datetime as _dt
    HOY = date(2026, 11, 24)
    AHORA = _dt(2026, 11, 24, 23, 0, 0)

    def exp(self, estado="evaluacion", sometido=date(2026, 11, 2)):
        return {"codigo": "SP-A8-2026-104", "proyecto": "Puerto Seco Colón, fase 1", "categoria": "III",
                "estado": estado, "fecha_ingreso": date(2026, 10, 1), "fecha_sometimiento": sometido}

    def ics(self, exp, docs=()):
        from permisos.calendario import generar_ics
        return generar_ics(exp, calcular_semaforo(exp, self.HOY), list(docs), self.HOY, self.AHORA)

    def test_estructura_rfc_5545(self):
        texto = self.ics(self.exp())
        self.assertTrue(texto.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"))
        self.assertTrue(texto.endswith("END:VCALENDAR\r\n"))
        self.assertNotIn("\n", texto.replace("\r\n", ""))  # solo CRLF
        for linea in texto.split("\r\n"):
            self.assertLessEqual(len(linea.encode("utf-8")), 75, linea)
        self.assertIn("DTSTAMP:20261124T230000Z", texto)
        self.assertEqual(texto.count("BEGIN:VEVENT"), texto.count("END:VEVENT"))

    def test_limite_legal_en_dias_habiles(self):
        limite = sumar_dias_habiles(date(2026, 11, 2), 80)
        texto = self.ics(self.exp())
        self.assertIn(f"DTSTART;VALUE=DATE:{limite.strftime('%Y%m%d')}", texto)
        self.assertIn("UID:SP-A8-2026-104-plazo@permisos-ambientales", texto)
        self.assertIn("plazo de MiAmbiente", texto.replace("\r\n ", ""))
        self.assertIn("Colón\\, fase 1", texto.replace("\r\n ", ""))  # la coma va escapada

    def test_resuelto_sin_evento_de_plazo(self):
        self.assertNotIn("-plazo@", self.ics(self.exp(estado="aprobado")))

    def test_documentos_por_vencer_y_vencidos(self):
        docs = [{"carpeta": "Anexos Legales", "estado": "recibido", "fecha_subida": date(2026, 11, 1),
                 "fecha_vencimiento": date(2026, 12, 15)},
                {"carpeta": "Línea Base", "estado": "recibido", "fecha_subida": date(2025, 1, 1)},  # ya vencio
                {"carpeta": "Cartografía", "estado": "pendiente"}]
        texto = self.ics(self.exp(), docs).replace("\r\n ", "")
        self.assertIn("UID:SP-A8-2026-104-doc-anexos-legales@permisos-ambientales", texto)
        self.assertIn("DTSTART;VALUE=DATE:20261215", texto)
        self.assertNotIn("doc-línea-base", texto)
        self.assertNotIn("Cartografía", texto)

    def test_plegado_no_parte_caracteres(self):
        from permisos.calendario import plegar
        linea = "DESCRIPTION:" + "ñ" * 80
        plegada = plegar(linea)
        for parte in plegada.split("\r\n"):
            self.assertLessEqual(len(parte.encode("utf-8")), 75)
        self.assertEqual(plegada.replace("\r\n ", ""), linea)


class RutaCalendario(unittest.TestCase):

    def respuestas(self, promotor_email=None):
        exp = expediente("pendiente")
        exp["promotor_email"] = promotor_email
        return [("FROM expedientes WHERE codigo", "uno", exp), ("FROM documentos", "todos", [])]

    def test_descarga_con_permiso(self):
        from permisos.rutas import expedientes as rutas_expedientes
        sesion("jefe")
        usar(rutas_expedientes, self.respuestas())
        r = app.test_client().get("/expedientes/SP-S10/plazos.ics")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["Content-Type"].startswith("text/calendar"))
        self.assertIn("SP-S10_plazos.ics", r.headers["Content-Disposition"])
        self.assertIn(b"BEGIN:VCALENDAR", r.data)

    def test_promotor_ajeno_no_descarga(self):
        from permisos.rutas import expedientes as rutas_expedientes
        sesion("promotor")
        usar(rutas_expedientes, self.respuestas(promotor_email="otro@ejemplo.com"))
        self.assertEqual(app.test_client().get("/expedientes/SP-S10/plazos.ics").status_code, 403)

    def test_sin_sesion(self):
        seguridad.usuario_sesion = lambda: None
        self.assertEqual(app.test_client().get("/expedientes/SP-S10/plazos.ics").status_code, 401)


if __name__ == "__main__":
    unittest.main()
