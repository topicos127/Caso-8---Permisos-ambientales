"""Redaccion: singular y plural correctos (1 dia / 2 dias) y el favicon que piden los navegadores."""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from permisos import reglas  # noqa: E402
from permisos.reglas import plural  # noqa: E402


class Plural(unittest.TestCase):

    def test_singular_solo_con_uno(self):
        self.assertEqual(plural(1, "día", "días"), "1 día")
        self.assertEqual(plural(0, "día", "días"), "0 días")
        self.assertEqual(plural(2, "día", "días"), "2 días")
        self.assertEqual(plural(12, "expediente", "expedientes"), "12 expedientes")
        self.assertEqual(plural(1, "invitación vencida", "invitaciones vencidas"), "1 invitación vencida")


class TextosDeLasAcciones(unittest.TestCase):
    """«Dónde poner al equipo hoy»: el plazo legal y la vigencia de los documentos."""

    def _acciones(self, dias_restantes, estado="vencido"):
        hoy = date(2026, 11, 28)
        exp = {"codigo": "SP-PRUEBA", "estado": "pendiente", "categoria": "I",
               "fecha_ingreso": hoy - timedelta(days=20 - dias_restantes), "fecha_sometimiento": None}
        return [a["texto"] for a in reglas.calcular_ipe(exp, [], dia=hoy)["acciones"] if a["tipo"] == "plazo"]

    def test_un_dia_de_retraso_no_dice_1_dias(self):
        textos = self._acciones(-1)
        self.assertTrue(any("venció hace 1 día" in t and "1 días" not in t for t in textos), textos)

    def test_varios_dias_de_retraso(self):
        textos = self._acciones(-4)
        self.assertTrue(any("venció hace 4 días" in t for t in textos), textos)

    def test_vence_hoy_y_vence_manana(self):
        self.assertTrue(any(t == "El plazo legal vence hoy" for t in self._acciones(0)))
        self.assertTrue(any(t == "El plazo legal vence en 1 día" for t in self._acciones(1)))


class Favicon(unittest.TestCase):

    def test_el_navegador_recibe_el_icono_en_svg(self):
        from permisos.rutas import publico
        from flask import Flask
        app = Flask("prueba", root_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        app.register_blueprint(publico.bp)
        r = app.test_client().get("/favicon.ico")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "image/svg+xml")
        self.assertIn(b"<svg", r.data)

    def test_todas_las_paginas_declaran_el_icono(self):
        raiz = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
        for nombre in sorted(os.listdir(raiz)):
            if nombre.endswith(".html"):
                with open(os.path.join(raiz, nombre), encoding="utf-8") as f:
                    self.assertIn('rel="icon"', f.read(), nombre)


if __name__ == "__main__":
    unittest.main()
