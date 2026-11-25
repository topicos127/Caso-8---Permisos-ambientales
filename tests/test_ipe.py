"""Pruebas unitarias del Indice de Preparacion del Expediente (HU-15).

No necesitan base de datos: prueban calcular_ipe con fechas fijas.
Correr con:  python -m unittest tests/test_ipe.py
"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from permisos.config import CATEGORIAS_DOCS  # noqa: E402
from permisos.reglas import banda_ipe, calcular_ipe, documentos_por_vencer  # noqa: E402

HOY = date(2026, 11, 23)


def expediente(categoria="II", dias_atras=0, estado="pendiente"):
    return {"codigo": "SP-PRUEBA", "categoria": categoria, "estado": estado,
            "fecha_ingreso": HOY - timedelta(days=dias_atras)}


def documentos(categoria, recibidos, subidos_hace=1):
    """Los primeros `recibidos` documentos de la categoria quedan recibidos."""
    carpetas = CATEGORIAS_DOCS[categoria]
    return [{"carpeta": c, "estado": "recibido" if i < recibidos else "pendiente",
             "fecha_subida": HOY - timedelta(days=subidos_hace) if i < recibidos else None}
            for i, c in enumerate(carpetas)]


class FormulaDelIpe(unittest.TestCase):
    def test_expediente_nuevo_sin_documentos_vale_50(self):
        r = calcular_ipe(expediente("I"), documentos("I", 0), HOY)
        # D = 0, P = 100 (en plazo), V = 100: 0,3 * 100 + 0,2 * 100
        self.assertEqual(r["ipe"], 50)
        self.assertEqual(r["banda"], "en_preparacion")
        self.assertEqual(r["componentes"], {"documentos": 0, "plazo": 100, "vigencia": 100})

    def test_completo_y_en_plazo_vale_100(self):
        r = calcular_ipe(expediente("III"), documentos("III", 5), HOY)
        self.assertEqual(r["ipe"], 100)
        self.assertEqual(r["banda"], "listo")
        self.assertEqual(r["banda_texto"], "Listo")

    def test_pesos(self):
        # Categoria II con 2 de 4 documentos (D = 50), en plazo: 25 + 30 + 20
        r = calcular_ipe(expediente("II"), documentos("II", 2), HOY)
        self.assertEqual(r["ipe"], 75)

    def test_plazo_por_vencer_vale_50_y_vencido_0(self):
        docs = documentos("II", 4)
        por_vencer = calcular_ipe(expediente("II", dias_atras=35), docs, HOY)  # quedan 5 de 40
        self.assertEqual(por_vencer["componentes"]["plazo"], 50)
        self.assertEqual(por_vencer["ipe"], 85)  # 50 + 15 + 20
        vencido = calcular_ipe(expediente("II", dias_atras=45), docs, HOY)
        self.assertEqual(vencido["componentes"]["plazo"], 0)
        self.assertEqual(vencido["ipe"], 70)  # 50 + 0 + 20

    def test_cada_documento_por_vencer_resta_25_a_la_vigencia(self):
        docs = documentos("II", 4, subidos_hace=340)  # vencen en 25 dias
        r = calcular_ipe(expediente("II"), docs, HOY)
        self.assertEqual(r["componentes"]["vigencia"], 0)  # 4 documentos: 100 - 100
        docs[0]["fecha_subida"] = HOY - timedelta(days=10)
        docs[1]["fecha_subida"] = HOY - timedelta(days=10)
        r = calcular_ipe(expediente("II"), docs, HOY)
        self.assertEqual(r["componentes"]["vigencia"], 50)

    def test_la_vigencia_no_baja_de_cero(self):
        r = calcular_ipe(expediente("III"), documentos("III", 5, subidos_hace=400), HOY)
        self.assertEqual(r["componentes"]["vigencia"], 0)

    def test_un_documento_pendiente_no_cuenta_para_la_vigencia(self):
        docs = documentos("I", 1, subidos_hace=360)
        self.assertEqual(len(documentos_por_vencer(docs, HOY)), 1)
        docs[0]["estado"] = "pendiente"
        self.assertEqual(documentos_por_vencer(docs, HOY), [])

    def test_resuelto_vale_100_en_plazo_aunque_haya_pasado_el_limite(self):
        r = calcular_ipe(expediente("I", dias_atras=300, estado="aprobado"), documentos("I", 3), HOY)
        self.assertEqual(r["componentes"]["plazo"], 100)
        self.assertEqual(r["acciones"], [])  # nada pendiente: ya se resolvio

    def test_redondea_las_mitades_hacia_arriba(self):
        # D = 25 (1 de 4), P = 0 (vencido), V = 100: 12,5 + 0 + 20 = 32,5 -> 33
        r = calcular_ipe(expediente("II", dias_atras=60), documentos("II", 1), HOY)
        self.assertEqual(r["ipe"], 33)


class Bandas(unittest.TestCase):
    def test_bordes(self):
        self.assertEqual(banda_ipe(100), "listo")
        self.assertEqual(banda_ipe(80), "listo")
        self.assertEqual(banda_ipe(79), "en_preparacion")
        self.assertEqual(banda_ipe(50), "en_preparacion")
        self.assertEqual(banda_ipe(49), "en_riesgo")
        self.assertEqual(banda_ipe(0), "en_riesgo")

    def test_en_riesgo_con_plazo_vencido_y_documentos_faltantes(self):
        r = calcular_ipe(expediente("III", dias_atras=100), documentos("III", 1), HOY)
        self.assertEqual(r["banda"], "en_riesgo")
        self.assertLess(r["ipe"], 50)


class ProximasAcciones(unittest.TestCase):
    def test_faltantes_plazo_y_vigencia_en_ese_orden(self):
        docs = documentos("II", 3, subidos_hace=350)  # 3 por vencer en 15 dias; falta Cartografia
        r = calcular_ipe(expediente("II", dias_atras=50), docs, HOY)
        tipos = [a["tipo"] for a in r["acciones"]]
        self.assertEqual(tipos, ["documento", "plazo", "vigencia", "vigencia", "vigencia"])
        self.assertEqual(r["acciones"][0]["texto"], "Subir Cartografía")
        self.assertEqual(r["acciones"][1]["texto"], "El plazo legal venció hace 10 días")
        self.assertIn("vence en 15 días", r["acciones"][2]["texto"])

    def test_completo_pendiente_pide_la_aprobacion_del_jefe(self):
        r = calcular_ipe(expediente("I"), documentos("I", 3), HOY)
        self.assertEqual([a["texto"] for a in r["acciones"]], ["Pedir la aprobación interna al director de proyectos"])

    def test_el_flujo_siguiente_segun_el_estado(self):
        docs = documentos("I", 3)
        interno = calcular_ipe(expediente("I", estado="aprobado_interno"), docs, HOY)
        self.assertEqual(interno["acciones"][0]["texto"], "Someter el expediente a MiAmbiente")
        evaluacion = calcular_ipe(expediente("I", estado="evaluacion"), docs, HOY)
        self.assertIn("resolución de MiAmbiente", evaluacion["acciones"][0]["texto"])

    def test_plazo_por_vencer_dice_en_cuantos_dias(self):
        r = calcular_ipe(expediente("I", dias_atras=17), documentos("I", 3), HOY)  # quedan 3 de 20
        self.assertIn("El plazo legal vence en 3 días", [a["texto"] for a in r["acciones"]])


if __name__ == "__main__":
    unittest.main()
