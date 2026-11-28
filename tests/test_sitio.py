"""El sitio publico (landing) repartido en paginas: estructura, menu y que ningun enlace quede roto."""
import os
import re
import unittest

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
PAGINAS = ["index", "producto", "planes", "seguridad", "consultar", "preguntas"]


def leer(nombre):
    with open(os.path.join(STATIC, nombre), encoding="utf-8") as f:
        return f.read()


class SitioPorPaginas(unittest.TestCase):

    def test_cada_pagina_tiene_lo_basico(self):
        for p in PAGINAS:
            with self.subTest(pagina=p):
                html = leer(p + ".html")
                self.assertEqual(html.count("<h1"), 1, "un solo h1")
                self.assertIn('<meta name="description"', html)
                self.assertIn('rel="icon"', html)
                self.assertIn('lang="es"', html)
                self.assertIn('id="acceso"', html, "todas cierran con el acceso (el boton «Obtener acceso» apunta ahi)")

    def test_el_menu_es_el_mismo_y_marca_la_pagina_actual(self):
        for p in PAGINAS:
            with self.subTest(pagina=p):
                nav = re.search(r'<nav class="l-nav".*?</nav>', leer(p + ".html"), re.S).group(0)
                for destino in PAGINAS:
                    self.assertIn(f'href="{destino}.html"', nav)
                actuales = re.findall(r'<a href="([^"]+)" class="activo" aria-current="page"', nav)
                self.assertEqual(actuales, [p + ".html"])

    def test_ningun_enlace_ni_ancla_esta_roto(self):
        for p in PAGINAS:
            html = leer(p + ".html")
            for destino in re.findall(r'href="([^"#]*\.html)(?:#([^"]*))?"', html):
                archivo, ancla = destino
                with self.subTest(pagina=p, enlace=archivo + ("#" + ancla if ancla else "")):
                    self.assertTrue(os.path.isfile(os.path.join(STATIC, archivo)), f"{archivo} no existe")
                    if ancla:
                        self.assertIn(f'id="{ancla}"', leer(archivo), f"{archivo} no tiene #{ancla}")
            for ancla in re.findall(r'href="#([^"]+)"', html):
                with self.subTest(pagina=p, ancla=ancla):
                    self.assertIn(f'id="{ancla}"', html)

    def test_scripts_e_imagenes_existen_y_no_hay_scripts_en_linea(self):
        for p in PAGINAS:
            html = leer(p + ".html")
            with self.subTest(pagina=p):
                self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)[^>]*>", "la politica de contenido no permite scripts en linea")
                for ruta in re.findall(r'<script src="([^"]+)"', html) + re.findall(r'<img[^>]+src="([^"]+)"', html):
                    self.assertTrue(os.path.isfile(os.path.join(STATIC, ruta)), f"{ruta} no existe")

    def test_consultar_trae_sus_scripts_y_las_demas_no_los_necesitan(self):
        self.assertIn("js/pag-index-1.js", leer("consultar.html"))
        for p in PAGINAS:
            if p != "consultar":
                self.assertNotIn("pag-index-1.js", leer(p + ".html"), p)
        self.assertIn("js/pag-planes.js", leer("planes.html"))

    def test_los_planes_muestran_los_tres_precios_y_la_aclaracion_academica(self):
        for p in ("planes", "index"):
            html = leer(p + ".html")
            with self.subTest(pagina=p):
                for precio in ("US$ 49", "US$ 99", "US$ 199"):
                    self.assertIn(precio, html)
                self.assertIn("ningún cobro real", html)

    def test_no_se_perdio_ningun_texto_del_landing_original(self):
        """Los textos de las secciones que se movieron de pagina siguen en el sitio."""
        todo = "".join(leer(p + ".html") for p in PAGINAS)
        for frase in ("Los problemas de todos los días", "Una plataforma, tres personas que ganan",
                      "Cada consultora trabaja en su propio espacio", "Así trabaja una consultora en la plataforma",
                      "Hecha para consultoras que trabajan en campo", "Del registro al sometimiento, en cuatro pasos",
                      "Pensado para expedientes que deben resistir una revisión",
                      "Consulte el estado de un estudio de impacto ambiental", "Lo lo que acaba de llegar".replace("Lo lo", "Lo"),
                      "Lo que suelen preguntarnos", "Ponga orden en su consultora desde hoy"):
            self.assertIn(frase, todo, frase)


if __name__ == "__main__":
    unittest.main()
