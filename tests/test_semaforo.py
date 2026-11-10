"""Pruebas unitarias del semaforo de plazos (HU-07).

No necesitan base de datos: prueban calcular_semaforo con fechas fijas.
Correr con:  python -m unittest tests/test_semaforo.py
"""
import os
import sys
import tempfile
import unittest
from datetime import date

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import calcular_semaforo  # noqa: E402

HOY = date(2026, 11, 10)


def expediente(categoria, dias_atras, estado="pendiente"):
    return {
        "codigo": "SP-PRUEBA",
        "categoria": categoria,
        "estado": estado,
        "fecha_ingreso": date.fromordinal(HOY.toordinal() - dias_atras),
    }


class SemaforoTest(unittest.TestCase):

    def test_limites_por_categoria(self):
        for categoria, limite in (("I", 20), ("II", 40), ("III", 80)):
            s = calcular_semaforo(expediente(categoria, 0), HOY)
            self.assertEqual(s["limite_dias"], limite)
            self.assertEqual(s["dias_restantes_legales"], limite)
            self.assertEqual(s["estado_semaforo"], "en_plazo")

    def test_umbral_proporcional(self):
        # 25 % del plazo: I=5, II=10, III=20 (antes era 5 para todas).
        self.assertEqual(calcular_semaforo(expediente("I", 0), HOY)["umbral_por_vencer"], 5)
        self.assertEqual(calcular_semaforo(expediente("II", 0), HOY)["umbral_por_vencer"], 10)
        self.assertEqual(calcular_semaforo(expediente("III", 0), HOY)["umbral_por_vencer"], 20)

    def test_bordes_categoria_iii(self):
        # 80 dias, por vencer con 20 o menos.
        self.assertEqual(calcular_semaforo(expediente("III", 59), HOY)["estado_semaforo"], "en_plazo")    # quedan 21
        self.assertEqual(calcular_semaforo(expediente("III", 60), HOY)["estado_semaforo"], "por_vencer")  # quedan 20
        self.assertEqual(calcular_semaforo(expediente("III", 80), HOY)["estado_semaforo"], "por_vencer")  # quedan 0
        self.assertEqual(calcular_semaforo(expediente("III", 81), HOY)["estado_semaforo"], "vencido")     # -1

    def test_resuelto_no_cuenta(self):
        for estado in ("aprobado", "rechazado"):
            s = calcular_semaforo(expediente("I", 300, estado), HOY)
            self.assertEqual(s["estado_semaforo"], "resuelto")
            self.assertIsNone(s["dias_transcurridos"])
            self.assertIsNone(s["dias_restantes_legales"])

    def test_en_tramite_si_cuenta(self):
        for estado in ("pendiente", "aprobado_interno", "evaluacion"):
            s = calcular_semaforo(expediente("I", 25, estado), HOY)
            self.assertEqual(s["estado_semaforo"], "vencido")
            self.assertEqual(s["dias_restantes_legales"], -5)

    def test_categoria_desconocida_usa_ii(self):
        self.assertEqual(calcular_semaforo(expediente("X", 0), HOY)["limite_dias"], 40)


if __name__ == "__main__":
    unittest.main()
