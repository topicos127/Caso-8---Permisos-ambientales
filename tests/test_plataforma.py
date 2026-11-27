"""Pruebas unitarias de la plataforma multiempresa que no necesitan MySQL:
verificacion en dos pasos (con los vectores del RFC 6238), codigos de recuperacion,
limite de intentos, almacenamiento de archivos (local y firma S3), nombres de
respaldos y la regla de aislamiento entre empresas.

Correr con:  python -m unittest tests/test_plataforma.py
"""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SECRET_KEY", "pruebas")
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from permisos import almacenamiento, bd, config, limitador, respaldos, seguridad, totp  # noqa: E402
from permisos.errores import ApiError  # noqa: E402

# Secreto de prueba del RFC 6238: la cadena ASCII "12345678901234567890" en base32.
SECRETO_RFC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


class TotpRfc6238(unittest.TestCase):
    def test_vectores_del_rfc(self):
        # RFC 6238, apendice B (SHA-1), los ultimos 6 digitos del codigo de 8.
        casos = {59: "287082", 1111111109: "081804", 1111111111: "050471",
                 1234567890: "005924", 2000000000: "279037"}
        for segundos, esperado in casos.items():
            self.assertEqual(totp.codigo_en(SECRETO_RFC, segundos // 30), esperado, segundos)

    def test_acepta_el_codigo_actual_y_la_ventana(self):
        ahora = 1111111109
        actual = totp.paso_actual(ahora)
        for paso in (actual - 1, actual, actual + 1):
            self.assertEqual(totp.verificar(SECRETO_RFC, totp.codigo_en(SECRETO_RFC, paso), 0, ahora), paso)

    def test_rechaza_un_codigo_fuera_de_la_ventana(self):
        ahora = 1111111109
        viejo = totp.codigo_en(SECRETO_RFC, totp.paso_actual(ahora) - 3)
        self.assertIsNone(totp.verificar(SECRETO_RFC, viejo, 0, ahora))

    def test_un_codigo_no_se_puede_reutilizar(self):
        ahora = 1111111109
        paso = totp.paso_actual(ahora)
        codigo = totp.codigo_en(SECRETO_RFC, paso)
        self.assertEqual(totp.verificar(SECRETO_RFC, codigo, 0, ahora), paso)
        self.assertIsNone(totp.verificar(SECRETO_RFC, codigo, paso, ahora))

    def test_rechaza_entradas_mal_formadas(self):
        for basura in ("", None, "12345", "1234567", "abcdef", "12 34"):
            self.assertIsNone(totp.verificar(SECRETO_RFC, basura, 0, 59), basura)

    def test_acepta_el_codigo_con_espacio_o_guion(self):
        ahora = 59
        codigo = totp.codigo_en(SECRETO_RFC, totp.paso_actual(ahora))
        self.assertIsNotNone(totp.verificar(SECRETO_RFC, f"{codigo[:3]} {codigo[3:]}", 0, ahora))

    def test_el_secreto_nuevo_es_base32_de_160_bits(self):
        s = totp.nuevo_secreto()
        self.assertEqual(len(s), 32)
        self.assertEqual(len(totp._clave(s)), 20)
        self.assertNotEqual(s, totp.nuevo_secreto())

    def test_uri_para_la_app_autenticadora(self):
        uri = totp.uri(SECRETO_RFC, "ana@ejemplo.com")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("secret=" + SECRETO_RFC, uri)
        self.assertIn("ana%40ejemplo.com", uri)
        self.assertIn("digits=6", uri)

    def test_el_qr_es_un_svg(self):
        self.assertIn("<svg", totp.qr_svg(totp.uri(SECRETO_RFC, "ana@ejemplo.com")))


class SecretoCifrado(unittest.TestCase):
    def test_ida_y_vuelta(self):
        self.assertEqual(totp.descifrar(totp.cifrar(SECRETO_RFC, "clave-a"), "clave-a"), SECRETO_RFC)

    def test_no_se_guarda_en_claro(self):
        self.assertNotIn(SECRETO_RFC, totp.cifrar(SECRETO_RFC, "clave-a"))

    def test_con_otra_clave_no_se_abre(self):
        self.assertIsNone(totp.descifrar(totp.cifrar(SECRETO_RFC, "clave-a"), "clave-b"))

    def test_texto_invalido_no_revienta(self):
        self.assertIsNone(totp.descifrar("no-es-fernet", "clave-a"))
        self.assertIsNone(totp.descifrar(None, "clave-a"))


class CodigosDeRecuperacion(unittest.TestCase):
    def test_formato_y_alfabeto(self):
        for _ in range(50):
            c = totp.nuevo_codigo_recuperacion()
            self.assertRegex(c, r"^[2-9A-HJKMNP-Z]{5}-[2-9A-HJKMNP-Z]{5}$")  # sin 0, 1, I, L, O
            self.assertTrue(totp.parece_codigo_recuperacion(c))

    def test_se_comparan_sin_importar_guion_ni_mayusculas(self):
        self.assertEqual(totp.hash_codigo("ab2cd-3efgh"), totp.hash_codigo(" AB2CD3EFGH "))

    def test_el_hash_es_sha256(self):
        self.assertEqual(len(totp.hash_codigo("AB2CD-3EFGH")), 64)

    def test_un_codigo_totp_no_se_confunde_con_uno_de_recuperacion(self):
        self.assertFalse(totp.parece_codigo_recuperacion("287082"))

    def test_son_distintos(self):
        self.assertEqual(len({totp.nuevo_codigo_recuperacion() for _ in range(200)}), 200)


class LimiteDeIntentos(unittest.TestCase):
    def setUp(self):
        limitador._fallos.clear()

    def test_bloquea_al_llegar_al_maximo(self):
        for _ in range(config.LOGIN_MAX_FALLOS - 1):
            limitador.anotar_fallo(("1.1.1.1", "a@b.c"))
        self.assertFalse(limitador.bloqueado(("1.1.1.1", "a@b.c")))
        limitador.anotar_fallo(("1.1.1.1", "a@b.c"))
        self.assertTrue(limitador.bloqueado(("1.1.1.1", "a@b.c")))

    def test_otra_clave_no_se_ve_afectada(self):
        for _ in range(config.LOGIN_MAX_FALLOS):
            limitador.anotar_fallo(("1.1.1.1", "a@b.c"))
        self.assertFalse(limitador.bloqueado(("1.1.1.1", "otro@b.c")))
        self.assertFalse(limitador.bloqueado(("2.2.2.2", "a@b.c")))

    def test_un_exito_limpia_el_contador(self):
        for _ in range(config.LOGIN_MAX_FALLOS):
            limitador.anotar_fallo("k")
        limitador.limpiar("k")
        self.assertFalse(limitador.bloqueado("k"))

    def test_el_bloqueo_vence_con_la_ventana(self):
        for _ in range(config.LOGIN_MAX_FALLOS):
            limitador.anotar_fallo("k")
        with mock.patch.object(limitador.time, "monotonic", return_value=limitador.time.monotonic() +
                               config.LOGIN_VENTANA_SEGUNDOS + 1):
            self.assertFalse(limitador.bloqueado("k"))


class RutasDeArchivos(unittest.TestCase):
    def test_claves_validas(self):
        for ok in ("SP-A8-2026-001/archivo.pdf", "organizaciones/3/logo-ab12.png", "respaldos/x.zip"):
            self.assertTrue(almacenamiento.clave_valida(ok), ok)

    def test_claves_peligrosas(self):
        for mala in ("", None, "../etc/passwd", "a/../../b", "/abs/ruta", "\\\\red\\recurso", "C:\\x", "a\x00b", "x" * 501):
            self.assertFalse(almacenamiento.clave_valida(mala), repr(mala))


class AlmacenLocal(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.parche = mock.patch.object(config, "UPLOADS_DIR", self.dir)
        self.parche.start()
        self.almacen = almacenamiento.Local()

    def tearDown(self):
        self.parche.stop()

    def test_guardar_leer_borrar(self):
        self.almacen.guardar("EXP-1/a.pdf", b"contenido")
        self.assertTrue(self.almacen.existe("EXP-1/a.pdf"))
        self.assertEqual(self.almacen.leer("EXP-1/a.pdf"), b"contenido")
        self.almacen.borrar("EXP-1/a.pdf")
        self.assertIsNone(self.almacen.leer("EXP-1/a.pdf"))
        self.assertFalse(self.almacen.existe("EXP-1/a.pdf"))

    def test_leer_una_ruta_peligrosa_devuelve_nada(self):
        self.assertIsNone(self.almacen.leer("../fuera.txt"))

    def test_guardar_una_ruta_peligrosa_falla(self):
        with self.assertRaises(almacenamiento.AlmacenamientoError):
            self.almacen.guardar("../fuera.txt", b"x")

    def test_listar_con_prefijo(self):
        self.almacen.guardar("A/1.pdf", b"1")
        self.almacen.guardar("B/2.pdf", b"2")
        self.assertEqual(sorted(self.almacen.listar()), ["A/1.pdf", "B/2.pdf"])
        self.assertEqual(list(self.almacen.listar("B/")), ["B/2.pdf"])

    def test_salud(self):
        self.assertTrue(self.almacen.salud())


class AlmacenS3(unittest.TestCase):
    """La firma SigV4 se comprueba de verdad contra un MinIO real en la verificacion de la
    plataforma; aqui se revisa la forma de la peticion sin red."""

    def setUp(self):
        self.parches = [mock.patch.object(config, nombre, valor) for nombre, valor in (
            ("S3_ENDPOINT", "http://almacen.local:9000"), ("S3_BUCKET", "permisos"), ("S3_REGION", "us-east-1"),
            ("S3_ACCESS_KEY", "AKIAEJEMPLO"), ("S3_SECRET_KEY", "secreto-de-prueba"))]
        for p in self.parches:
            p.start()
        self.s3 = almacenamiento.S3()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def _capturar(self, accion):
        class Respuesta:
            status = 200

            def read(self):
                return b""

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        with mock.patch.object(almacenamiento.urllib.request, "urlopen", return_value=Respuesta()) as u:
            accion()
        return u.call_args[0][0]

    def test_la_peticion_va_firmada_y_con_ruta_por_bucket(self):
        req = self._capturar(lambda: self.s3.guardar("SP-A8-2026-001/Línea Base.pdf", b"datos"))
        self.assertEqual(req.get_method(), "PUT")
        self.assertTrue(req.full_url.startswith("http://almacen.local:9000/permisos/SP-A8-2026-001/"))
        self.assertNotIn(" ", req.full_url)  # los espacios y tildes van codificados
        auth = req.get_header("Authorization")
        self.assertTrue(auth.startswith("AWS4-HMAC-SHA256 Credential=AKIAEJEMPLO/"))
        self.assertIn("/us-east-1/s3/aws4_request", auth)
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", auth)
        self.assertRegex(auth, r"Signature=[0-9a-f]{64}$")

    def test_el_cuerpo_se_declara_con_su_sha256(self):
        import hashlib
        req = self._capturar(lambda: self.s3.guardar("a/b.pdf", b"datos"))
        self.assertEqual(req.get_header("X-amz-content-sha256"), hashlib.sha256(b"datos").hexdigest())

    def test_listar_ordena_los_parametros(self):
        req = self._capturar(lambda: list(self.s3.listar("respaldos/")))
        self.assertTrue(req.full_url.endswith("?list-type=2&prefix=respaldos%2F"))

    def test_rechaza_una_clave_peligrosa(self):
        with self.assertRaises(almacenamiento.AlmacenamientoError):
            self.s3.guardar("../x", b"")

    def test_sin_configuracion_no_arranca(self):
        with mock.patch.object(config, "S3_BUCKET", ""):
            with self.assertRaises(almacenamiento.AlmacenamientoError):
                almacenamiento.S3()


class NombresDeRespaldo(unittest.TestCase):
    def test_nombres_validos(self):
        for n in ("respaldo-20261124-020000.zip", "respaldo-20261124-020000-auto.zip",
                  "respaldo-20261124-020000-previo.zip"):
            self.assertTrue(respaldos.NOMBRE_VALIDO.match(n), n)

    def test_nombres_peligrosos_no_se_resuelven_a_una_ruta(self):
        for n in ("../respaldo-20261124-020000.zip", "respaldo-20261124-020000.zip/../x", "x.zip", "", None,
                  "respaldo-1-2.zip", "/etc/passwd"):
            self.assertIsNone(respaldos.ruta_de(n), n)


def usuario(rol, org, uid=1, email="u@x.com"):
    return {"id": uid, "rol": rol, "organizacion_id": org, "email": email}


def expediente(org, dueno=10, promotor="prom@x.com"):
    return {"organizacion_id": org, "usuario_id": dueno, "promotor_email": promotor}


class AislamientoEntreEmpresas(unittest.TestCase):
    """Una consultora no ve ni toca lo de otra, tenga el rol que tenga."""

    def setUp(self):
        self.antes = bd._esquema["org"]
        bd._esquema["org"] = True

    def tearDown(self):
        bd._esquema["org"] = self.antes

    def test_el_jefe_ve_todo_lo_de_su_empresa_y_nada_de_otra(self):
        jefe = usuario("jefe", 1)
        self.assertTrue(seguridad.puede_ver(jefe, expediente(1)))
        self.assertFalse(seguridad.puede_ver(jefe, expediente(2)))

    def test_el_consultor_solo_ve_los_suyos_y_de_su_empresa(self):
        c = usuario("consultor", 1, uid=10)
        self.assertTrue(seguridad.puede_ver(c, expediente(1, dueno=10)))
        self.assertFalse(seguridad.puede_ver(c, expediente(1, dueno=11)))
        self.assertFalse(seguridad.puede_ver(c, expediente(2, dueno=10)))  # mismo id de usuario, otra empresa

    def test_el_promotor_ve_su_expediente_pero_no_el_de_otra_empresa_con_su_correo(self):
        p = usuario("promotor", 1, email="prom@x.com")
        self.assertTrue(seguridad.puede_ver(p, expediente(1)))
        self.assertFalse(seguridad.puede_ver(p, expediente(2)))

    def test_el_administrador_no_ve_expedientes(self):
        admin = usuario("admin", None)
        for org in (None, 1, 2):
            self.assertFalse(seguridad.puede_ver(admin, expediente(org)))

    def test_un_usuario_sin_empresa_no_ve_nada(self):
        self.assertFalse(seguridad.puede_ver(usuario("jefe", None), expediente(1)))

    def test_gestion_solo_dentro_de_la_empresa(self):
        seguridad.exigir_gestion(usuario("jefe", 1), expediente(1))  # no lanza
        with self.assertRaises(ApiError) as ctx:
            seguridad.exigir_gestion(usuario("jefe", 1), expediente(2))
        self.assertEqual(ctx.exception.status, 404)  # no confirma que el expediente existe
        with self.assertRaises(ApiError):
            seguridad.exigir_gestion(usuario("consultor", 1, uid=10), expediente(1, dueno=11))

    def test_leer_un_expediente_de_otra_empresa_responde_404_no_403(self):
        with self.assertRaises(ApiError) as ctx:
            seguridad.exigir_lectura(usuario("jefe", 1), expediente(2))
        self.assertEqual(ctx.exception.status, 404)
        with self.assertRaises(ApiError) as ctx:  # de la misma empresa pero ajeno: ahi si es 403
            seguridad.exigir_lectura(usuario("consultor", 1, uid=10), expediente(1, dueno=11))
        self.assertEqual(ctx.exception.status, 403)

    def test_el_jefe_de_otra_empresa_no_aprueba_ni_cambia_el_acceso(self):
        seguridad.exigir_jefe_de(usuario("jefe", 1), expediente(1))  # de su empresa: pasa
        with self.assertRaises(ApiError) as ctx:
            seguridad.exigir_jefe_de(usuario("jefe", 2), expediente(1))
        self.assertEqual(ctx.exception.status, 404)  # tiene el rol de jefe, pero no es SU empresa
        with self.assertRaises(ApiError) as ctx:
            seguridad.exigir_jefe_de(usuario("consultor", 1), expediente(1))
        self.assertEqual(ctx.exception.status, 403)

    def test_el_filtro_sql_incluye_siempre_la_empresa(self):
        sql, params = seguridad.filtro_de(usuario("jefe", 7))
        self.assertIn("organizacion_id=%s", sql)
        self.assertEqual(params, [7])
        sql, params = seguridad.filtro_de(usuario("consultor", 7, uid=3))
        self.assertIn("organizacion_id=%s", sql)
        self.assertEqual(params, [7, 3])
        sql, params = seguridad.filtro_de(usuario("promotor", 7, email="p@x.com"))
        self.assertEqual(params, [7, "p@x.com"])

    def test_el_filtro_del_administrador_o_sin_empresa_no_devuelve_nada(self):
        self.assertEqual(seguridad.filtro_de(usuario("admin", None))[0], "1=0")
        self.assertEqual(seguridad.filtro_de(usuario("jefe", None))[0], "1=0")
        self.assertEqual(seguridad.condicion_empresa(usuario("jefe", None), "u")[0], "1=0")

    def test_condicion_sobre_otro_alias(self):
        sql, params = seguridad.condicion_empresa(usuario("jefe", 4), "u")
        self.assertEqual((sql, params), ("u.organizacion_id=%s", [4]))

    def test_sin_columna_de_empresa_no_restringe_nada(self):
        bd._esquema["org"] = False
        self.assertEqual(seguridad.condicion_empresa(usuario("jefe", None)), ("1=1", []))
        self.assertTrue(seguridad.puede_ver(usuario("jefe", None), expediente(None)))


class PoliticaDeLaEmpresa(unittest.TestCase):
    """La sesion vence antes si la empresa lo pide, y los dos pasos pueden ser obligatorios."""

    def setUp(self):
        from contextlib import contextmanager

        from flask import Flask
        self.app = Flask("prueba")
        self.app.secret_key = "pruebas"
        self.antes = {k: bd._esquema[k] for k in ("org", "org_politica", "totp", "sesion")}
        for k in self.antes:
            bd._esquema[k] = True
        self.cursor = seguridad.cursor
        self.filas = []

        class Falso:
            def __init__(self, filas):
                self.filas = filas

            def execute(self, sql, params=None):
                return 1

            def fetchone(self):
                return self.filas.pop(0) if self.filas else None

        @contextmanager
        def _cursor():
            yield Falso(self.filas)
        seguridad.cursor = _cursor

    def tearDown(self):
        seguridad.cursor = self.cursor
        bd._esquema.update(self.antes)

    def _preparar(self, rol="consultor", totp_activo=0, **politica):
        usuario = {"id": 5, "email": "c@x.com", "rol": rol, "nombre": "C", "debe_cambiar_clave": 0, "activo": 1,
                   "organizacion_id": 1, "sesion_version": 0, "totp_activo": totp_activo}
        self.filas[:] = [usuario, dict({"activa": 1, "exigir_2fa": 0, "sesion_minutos": None}, **politica)]

    def _admin(self, totp_activo):
        self.filas[:] = [{"id": 1, "email": "a@x.com", "rol": "admin", "nombre": "A", "debe_cambiar_clave": 0,
                          "activo": 1, "organizacion_id": None, "sesion_version": 0, "totp_activo": totp_activo}]

    def test_administrador_sin_dos_pasos_debe_activarlos_si_se_exige(self):
        with self.app.test_request_context(), mock.patch.object(config, "ADMIN_EXIGE_2FA", True):
            from flask import session
            session.update({"uid": 1, "sv": 0})
            self._admin(totp_activo=0)
            self.assertTrue(seguridad.usuario_sesion()["debe_activar_2fa"])

    def test_administrador_con_dos_pasos_no_debe_activarlos(self):
        with self.app.test_request_context(), mock.patch.object(config, "ADMIN_EXIGE_2FA", True):
            from flask import session
            session.update({"uid": 1, "sv": 0})
            self._admin(totp_activo=1)
            self.assertFalse(seguridad.usuario_sesion()["debe_activar_2fa"])

    def test_sin_la_exigencia_el_administrador_no_los_necesita(self):
        with self.app.test_request_context(), mock.patch.object(config, "ADMIN_EXIGE_2FA", False):
            from flask import session
            session.update({"uid": 1, "sv": 0})
            self._admin(totp_activo=0)
            self.assertFalse(seguridad.usuario_sesion()["debe_activar_2fa"])

    def test_la_sesion_vence_por_inactividad_segun_la_empresa(self):
        with self.app.test_request_context():
            from flask import session
            session.update({"uid": 5, "sv": 0, "ult": time.time() - 16 * 60})
            self._preparar(sesion_minutos=15)
            self.assertIsNone(seguridad.usuario_sesion())
            self.assertNotIn("uid", session)

    def test_con_actividad_reciente_sigue_abierta_y_se_renueva(self):
        with self.app.test_request_context():
            from flask import session
            hace = time.time() - 5 * 60
            session.update({"uid": 5, "sv": 0, "ult": hace})
            self._preparar(sesion_minutos=15)
            self.assertIsNotNone(seguridad.usuario_sesion())
            self.assertGreater(session["ult"], hace)

    def test_sin_politica_de_inactividad_no_se_cierra(self):
        with self.app.test_request_context():
            from flask import session
            session.update({"uid": 5, "sv": 0, "ult": time.time() - 99 * 60})
            self._preparar(sesion_minutos=None)
            self.assertIsNotNone(seguridad.usuario_sesion())

    def test_dos_pasos_obligatorios_para_consultores_y_directores_sin_ellos(self):
        for rol, activo, debe in (("consultor", 0, True), ("jefe", 0, True), ("consultor", 1, False),
                                  ("promotor", 0, False)):
            with self.subTest(rol=rol, activo=activo), self.app.test_request_context():
                from flask import session
                session.update({"uid": 5, "sv": 0})
                self._preparar(rol=rol, totp_activo=activo, exigir_2fa=1)
                self.assertEqual(seguridad.usuario_sesion()["debe_activar_2fa"], debe)

    def test_sin_la_politica_nadie_debe_activarlos(self):
        with self.app.test_request_context():
            from flask import session
            session.update({"uid": 5, "sv": 0})
            self._preparar(exigir_2fa=0)
            self.assertFalse(seguridad.usuario_sesion()["debe_activar_2fa"])


class ArranqueEnProduccion(unittest.TestCase):
    """Con HTTPS (produccion) no se arranca con claves de prueba ni sin SECRET_KEY."""

    BUENA = {"secure": True, "secret": "x" * 40, "admin_password": "Una-Clave-Propia-1", "jefe_password": "Otra-Clave-Propia-2",
             "jefe_inicial": True}

    def test_en_local_no_se_exige_nada(self):
        self.assertEqual(config.problemas_de_produccion(secure=False, secret=None,
                                                         admin_password=config.ADMIN_PASSWORD_DEFECTO,
                                                         jefe_password=config.JEFE_PASSWORD_DEFECTO), [])

    def test_produccion_bien_configurada_no_tiene_problemas(self):
        self.assertEqual(config.problemas_de_produccion(**self.BUENA), [])

    def test_sin_secret_key_o_muy_corta(self):
        for secreto in (None, "", "corta"):
            with self.subTest(secreto=secreto):
                p = config.problemas_de_produccion(**{**self.BUENA, "secret": secreto})
                self.assertEqual(len(p), 1)
                self.assertIn("SECRET_KEY", p[0])

    def test_claves_de_prueba_no_valen(self):
        p = config.problemas_de_produccion(**{**self.BUENA, "admin_password": config.ADMIN_PASSWORD_DEFECTO})
        self.assertEqual([x.split(":")[0] for x in p], ["ADMIN_PASSWORD"])
        p = config.problemas_de_produccion(**{**self.BUENA, "jefe_password": config.JEFE_PASSWORD_DEFECTO})
        self.assertEqual([x.split(":")[0] for x in p], ["JEFE_PASSWORD"])

    def test_todo_mal_lista_todos_los_problemas(self):
        p = config.problemas_de_produccion(secure=True, secret=None, admin_password=config.ADMIN_PASSWORD_DEFECTO,
                                           jefe_password=config.JEFE_PASSWORD_DEFECTO, jefe_inicial=True)
        self.assertEqual(len(p), 3)

    def test_sin_director_inicial_no_se_pide_su_contrasena(self):
        # En produccion los directores los crea el administrador: JEFE_PASSWORD no se usa.
        p = config.problemas_de_produccion(**{**self.BUENA, "jefe_inicial": False,
                                              "jefe_password": config.JEFE_PASSWORD_DEFECTO})
        self.assertEqual(p, [])

    def test_en_produccion_el_director_inicial_va_apagado_por_defecto(self):
        import importlib
        entorno = {"SESSION_COOKIE_SECURE": "true"}
        with mock.patch.dict(os.environ, entorno):
            os.environ.pop("JEFE_INICIAL", None)
            self.assertFalse(importlib.reload(config).JEFE_INICIAL)
            os.environ["JEFE_INICIAL"] = "true"
            self.assertTrue(importlib.reload(config).JEFE_INICIAL)
        with mock.patch.dict(os.environ, {"SESSION_COOKIE_SECURE": "false"}):
            os.environ.pop("JEFE_INICIAL", None)
            self.assertTrue(importlib.reload(config).JEFE_INICIAL)
        importlib.reload(config)

    def test_la_app_se_niega_a_arrancar_en_produccion_con_claves_de_prueba(self):
        from permisos import create_app
        with mock.patch.object(config, "SESSION_COOKIE_SECURE", True), mock.patch.object(config, "SECRET_KEY", None):
            with self.assertRaises(RuntimeError) as ctx:
                create_app()
        self.assertIn("SECRET_KEY", str(ctx.exception))


class DetrasDeUnProxy(unittest.TestCase):
    """En Railway la IP del cliente llega en X-Forwarded-For; en local esa cabecera no se cree."""

    def _ip(self, saltos, cabecera):
        from flask import Flask, request
        from permisos import aplicar_proxy
        app = aplicar_proxy(Flask(__name__), saltos)

        @app.route("/ip")
        def ip():
            return request.remote_addr or ""
        return app.test_client().get("/ip", headers={"X-Forwarded-For": cabecera},
                                     environ_base={"REMOTE_ADDR": "10.0.0.1"}).get_data(as_text=True)

    def test_sin_proxy_se_ignora_la_cabecera(self):
        self.assertEqual(self._ip(0, "203.0.113.9"), "10.0.0.1")

    def test_con_un_proxy_se_usa_la_ip_del_cliente(self):
        self.assertEqual(self._ip(1, "203.0.113.9"), "203.0.113.9")

    def test_un_cliente_no_puede_falsificar_su_ip(self):
        # el proxy anade la IP real al final: lo que el cliente puso antes no cuenta
        self.assertEqual(self._ip(1, "1.2.3.4, 203.0.113.9"), "203.0.113.9")


class EmpresaPorDefecto(unittest.TestCase):
    """En una base nueva de produccion no se crea ninguna empresa: las crea el administrador."""

    def _correr(self, jefe_inicial, sin_empresa, hay_empresa=False):
        from contextlib import contextmanager
        sentencias = []

        class Falso:
            lastrowid = 9

            def execute(self, sql, params=None):
                sentencias.append(sql.strip().split()[0] + " " + " ".join(sql.split()[1:4]))
                self.ultimo = sql

            def fetchone(self):
                if "FROM organizaciones ORDER BY" in self.ultimo:
                    return {"id": 3} if hay_empresa else None
                return {"n": sin_empresa}

        @contextmanager
        def _cursor():
            yield Falso()
        with mock.patch.object(bd, "cursor", _cursor), mock.patch.object(bd, "JEFE_INICIAL", jefe_inicial),                 mock.patch.dict(bd._esquema, {"org": True}):
            return bd._preparar_empresa_por_defecto(), sentencias

    def test_base_nueva_en_produccion_no_crea_empresa(self):
        org, sentencias = self._correr(jefe_inicial=False, sin_empresa=0)
        self.assertIsNone(org)
        self.assertFalse(any(s.startswith("INSERT") for s in sentencias))

    def test_con_datos_antiguos_si_se_crea_para_no_dejarlos_huerfanos(self):
        org, sentencias = self._correr(jefe_inicial=False, sin_empresa=4)
        self.assertEqual(org, 9)
        self.assertTrue(any(s.startswith("INSERT") for s in sentencias))

    def test_en_local_se_crea_siempre(self):
        org, _ = self._correr(jefe_inicial=True, sin_empresa=0)
        self.assertEqual(org, 9)

    def test_si_ya_hay_empresa_se_usa_esa(self):
        org, sentencias = self._correr(jefe_inicial=False, sin_empresa=0, hay_empresa=True)
        self.assertEqual(org, 3)
        self.assertFalse(any(s.startswith("INSERT") for s in sentencias))


class GestionDeAdministradores(unittest.TestCase):
    """La plataforma nunca se queda sin un administrador activo y nadie se desactiva a si mismo."""

    def setUp(self):
        from contextlib import contextmanager

        from flask import Flask, g

        from permisos.rutas import administradores as adm
        self.adm = adm
        self.app = Flask("prueba")
        self.app.secret_key = "pruebas"
        self.sentencias = []
        yo = self

        class Falso:
            def execute(self, sql, params=None):
                yo.sentencias.append(sql)
                self.ultimo = sql

            def fetchone(self):
                if "COUNT(*)" in self.ultimo:
                    return {"n": yo.activos}
                return yo.objetivo

        @contextmanager
        def _cursor():
            yield Falso()
        self.cursor = adm.cursor
        adm.cursor = _cursor
        self.esquema = dict(bd._esquema)
        bd._esquema.update(activo=True, sesion=True, cambio_clave=True, totp=True)
        self.activos = 3
        self.objetivo = {"id": 9, "nombre": "Otra Persona", "email": "o@x.com", "rol": "admin", "activo": 1}
        self.g = g

    def tearDown(self):
        self.adm.cursor = self.cursor
        bd._esquema.clear()
        bd._esquema.update(self.esquema)

    def _llamar(self, funcion, usuario_id, cuerpo, yo=1):
        # requiere_admin consulta la sesion: se salta llamando a la funcion sin decorar
        original = getattr(funcion, "__wrapped__", funcion)
        with self.app.test_request_context(json=cuerpo):
            self.g.usuario = {"id": yo, "rol": "admin"}
            return original(usuario_id)

    def test_no_se_puede_desactivar_a_uno_mismo(self):
        with self.assertRaises(ApiError) as e:
            self._llamar(self.adm.cambiar_estado, 1, {"activo": False}, yo=1)
        self.assertEqual(e.exception.status, 409)

    def test_no_se_puede_dejar_la_plataforma_sin_administradores_activos(self):
        self.activos = 1
        with self.assertRaises(ApiError) as e:
            self._llamar(self.adm.cambiar_estado, 9, {"activo": False})
        self.assertEqual(e.exception.status, 409)
        self.assertIn("sin un administrador activo", e.exception.mensaje)

    def test_con_otros_activos_se_puede_desactivar(self):
        r, codigo = self._llamar(self.adm.cambiar_estado, 9, {"activo": False})
        self.assertEqual(codigo, 200)
        self.assertTrue(any(s.strip().startswith("UPDATE usuarios SET activo") for s in self.sentencias))

    def test_solo_actua_sobre_administradores(self):
        self.objetivo = {"id": 9, "nombre": "Director", "email": "d@x.com", "rol": "jefe", "activo": 1}
        for funcion, cuerpo in ((self.adm.cambiar_estado, {"activo": False}), (self.adm.restablecer, {})):
            with self.subTest(funcion=funcion.__name__):
                with self.assertRaises(ApiError) as e:
                    self._llamar(funcion, 9, cuerpo)
                self.assertEqual(e.exception.status, 404)

    def test_no_se_restablece_el_acceso_propio(self):
        with self.assertRaises(ApiError) as e:
            self._llamar(self.adm.restablecer, 1, {}, yo=1)
        self.assertEqual(e.exception.status, 409)

    def test_el_valor_de_activo_debe_ser_booleano(self):
        with self.assertRaises(ApiError) as e:
            self._llamar(self.adm.cambiar_estado, 9, {"activo": "no"})
        self.assertEqual(e.exception.status, 400)


class DominioDeAdministradores(unittest.TestCase):
    """Los administradores de la plataforma solo pueden usar correos de los dominios autorizados."""

    DOMINIOS = ("apto.com.pa",)

    def test_lee_la_lista_de_dominios(self):
        self.assertEqual(config.dominios_de("apto.com.pa, @Otro.com ; x.org"), ("apto.com.pa", "otro.com", "x.org"))
        self.assertEqual(config.dominios_de(""), ())
        self.assertEqual(config.dominios_de(None), ())

    def test_sin_dominios_no_hay_restriccion(self):
        self.assertTrue(config.correo_en_dominios("cualquiera@gmail.com", ()))

    def test_solo_el_dominio_exacto_cuenta(self):
        validos = ("helio@apto.com.pa", "HELIO@APTO.COM.PA", "  a@apto.com.pa ")
        invalidos = ("helio@gmail.com", "helio@mail.apto.com.pa", "helio@apto.com.pa.evil.com",
                     "helio@evilapto.com.pa", "apto.com.pa", "", None)
        for correo in validos:
            self.assertTrue(config.correo_en_dominios(correo, self.DOMINIOS), correo)
        for correo in invalidos:
            self.assertFalse(config.correo_en_dominios(correo, self.DOMINIOS), correo)

    def test_en_produccion_no_arranca_con_un_correo_de_otro_dominio(self):
        buena = {"secure": True, "secret": "x" * 40, "admin_password": "Una-Clave-Propia-1", "jefe_inicial": False}
        p = config.problemas_de_produccion(**buena, admin_email="helio@gmail.com", admin_dominios=self.DOMINIOS)
        self.assertEqual(len(p), 1)
        self.assertIn("ADMIN_EMAIL", p[0])
        self.assertIn("@apto.com.pa", p[0])
        self.assertEqual(config.problemas_de_produccion(**buena, admin_email="helio@apto.com.pa",
                                                        admin_dominios=self.DOMINIOS), [])
        self.assertEqual(config.problemas_de_produccion(**buena, admin_email="helio@gmail.com", admin_dominios=()), [])

    # --- invitar
    def test_no_se_invita_a_un_correo_de_otro_dominio(self):
        from contextlib import contextmanager

        from flask import Flask, g

        from permisos.rutas import administradores as adm

        class Falso:
            def execute(self, sql, params=None):
                self.ultimo = sql

            def fetchone(self):
                return None

        @contextmanager
        def _cursor():
            yield Falso()
        app = Flask("prueba")
        original = adm.cursor
        adm.cursor = _cursor
        try:
            with mock.patch.object(adm, "ADMIN_DOMINIOS", self.DOMINIOS):
                invitar = getattr(adm.invitar, "__wrapped__", adm.invitar)
                with app.test_request_context(json={"email": "persona@gmail.com"}):
                    g.usuario = {"id": 1, "rol": "admin"}
                    with self.assertRaises(ApiError) as e:
                        invitar()
                self.assertEqual(e.exception.status, 400)
                self.assertIn("@apto.com.pa", e.exception.mensaje)
                with app.test_request_context(json={"email": "persona@apto.com.pa"}):
                    g.usuario = {"id": 1, "rol": "admin"}
                    _, codigo = invitar()
                self.assertEqual(codigo, 201)
        finally:
            adm.cursor = original

    # --- registro y login de administracion
    def _app_auth(self, fila):
        from contextlib import contextmanager

        from flask import Flask

        from permisos.rutas import auth

        class Falso:
            def execute(self, sql, params=None):
                self.ultimo = sql

            def fetchone(self):
                if isinstance(fila, list):
                    return fila.pop(0) if len(fila) > 1 else fila[0]
                return fila

        @contextmanager
        def _cursor():
            yield Falso()
        app = Flask("prueba")
        app.secret_key = "pruebas"
        app.register_blueprint(auth.bp)
        self.addCleanup(setattr, auth, "cursor", auth.cursor)
        self.addCleanup(bd._esquema.update, dict(bd._esquema))
        auth.cursor = _cursor
        bd._esquema.update({k: False for k in bd._esquema})
        return app, auth

    def test_el_registro_por_invitacion_de_administrador_exige_el_dominio(self):
        from datetime import timedelta

        from permisos.reglas import ahora
        inv = {"id": 1, "organizacion_id": None, "rol": "admin", "email": None, "expira": ahora() + timedelta(hours=1),
               "usada_en": None, "revocada": 0}
        app, auth = self._app_auth(inv)
        cuerpo = {"nombre": "Persona", "email": "persona@gmail.com", "password": "Clave-Larga-Admin-91!",
                  "invitacion": "tokencualquiera", "acepto_terminos": True}
        with mock.patch.object(auth, "ADMIN_DOMINIOS", self.DOMINIOS):
            r = app.test_client().post("/registro", json=cuerpo)
        self.assertEqual(r.status_code, 400)
        self.assertIn("@apto.com.pa", r.get_json()["mensaje"])

    def test_la_invitacion_de_una_consultora_no_exige_ese_dominio(self):
        # La regla es solo de los administradores; "el resto" se decide aparte.
        from datetime import timedelta

        from permisos.reglas import ahora
        inv = {"id": 1, "organizacion_id": 3, "rol": "consultor", "email": None, "expira": ahora() + timedelta(hours=1),
               "usada_en": None, "revocada": 0}
        # invitacion, empresa activa y "ese correo ya existe" (asi se corta sin tocar mas la base)
        app, auth = self._app_auth([inv, {"activa": 1}, {"id": 5}])
        cuerpo = {"nombre": "Persona", "email": "persona@gmail.com", "password": "Clave-Larga-Admin-91!",
                  "invitacion": "tokencualquiera", "acepto_terminos": True}
        with mock.patch.object(auth, "ADMIN_DOMINIOS", self.DOMINIOS):
            r = app.test_client().post("/registro", json=cuerpo)
        self.assertEqual(r.status_code, 409)
        self.assertNotIn("apto.com.pa", r.get_json()["mensaje"])

    def test_el_login_de_administracion_rechaza_una_cuenta_de_otro_dominio(self):
        from werkzeug.security import generate_password_hash
        fila = {"id": 1, "email": "viejo@gmail.com", "password_hash": generate_password_hash("Clave-Larga-1!"),
                "rol": "admin", "nombre": "V", "debe_cambiar_clave": 0, "activo": 1, "organizacion_id": None,
                "sesion_version": 0, "totp_activo": 0}
        app, auth = self._app_auth(fila)
        with mock.patch.object(auth, "ADMIN_DOMINIOS", self.DOMINIOS):
            r = app.test_client().post("/admin/login", json={"email": "viejo@gmail.com", "password": "Clave-Larga-1!"})
            self.assertEqual(r.status_code, 403)
            self.assertFalse(r.get_json()["acceso"])
            self.assertIn("@apto.com.pa", r.get_json()["mensaje"])
            fila["email"] = "nuevo@apto.com.pa"
            r = app.test_client().post("/admin/login", json={"email": "nuevo@apto.com.pa", "password": "Clave-Larga-1!"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["acceso"])


if __name__ == "__main__":
    unittest.main()
