"""Configuracion leida del entorno y constantes del dominio."""
import os
import re
import ssl
from zoneinfo import ZoneInfo

import pymysql

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- Archivos ----------

UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/app/uploads")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
EXTENSIONES_PERMITIDAS = {".pdf", ".zip"}
ZONA = ZoneInfo("America/Panama")

# ---------- Sesion ----------

SECRET_KEY = os.environ.get("SECRET_KEY")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

# ---------- Base de datos ----------

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_CONFIG = {
    "host": DB_HOST,
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "permisos_ambientales"),
    "cursorclass": pymysql.cursors.DictCursor,
}

# Aiven exige SSL. Con DB_SSL_CA (el ca.pem de Aiven) se verifica el
# certificado; sin el, se mantiene la conexion cifrada sin verificar.
_ca = os.environ.get("DB_SSL_CA")
if _ca:
    DB_CONFIG["ssl"] = ssl.create_default_context(cafile=_ca)
elif "aivencloud" in DB_HOST:
    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE
    DB_CONFIG["ssl"] = _ctx
    print("AVISO: conexion a Aiven sin verificar el certificado; defina DB_SSL_CA.", flush=True)

# ---------- Dominio ----------

CATEGORIAS_DOCS = {
    "I":   ["Línea Base", "Plan de Manejo", "Anexos Legales"],
    "II":  ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía"],
    "III": ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía", "Evidencia Foro Público"],
}
PLAZOS_LEGALES = {"I": 20, "II": 40, "III": 80}
ESTADOS_RESUELTOS = {"aprobado", "rechazado"}
# Sprint 9: el promotor ya no se registra solo. Si pudiera, cualquiera que se
# registrara primero con el correo de un promotor veria sus expedientes. Su
# cuenta la crea el consultor (o el jefe) desde el expediente.
ROLES_REGISTRO = {"consultor"}  # el jefe tampoco se registra solo
ROLES_INTERNOS = {"consultor", "jefe"}

# HU-07: los tres estados que ven el promotor y el publico.
ESTADO_PUBLICO = {
    "pendiente": "Pendiente de subsanación",
    "aprobado_interno": "Pendiente de subsanación",
    "evaluacion": "En evaluación",
    "aprobado": "Aprobado",
    "rechazado": "Rechazado",
}

# Limite de intentos fallidos de login por correo e IP (Sprint 9).
LOGIN_MAX_FALLOS = int(os.environ.get("LOGIN_MAX_FALLOS", 5))
LOGIN_VENTANA_SEGUNDOS = int(os.environ.get("LOGIN_VENTANA_SEGUNDOS", 60))

# HU-13: usuario jefe de prueba. En Railway conviene definir JEFE_PASSWORD.
JEFE_EMAIL = os.environ.get("JEFE_EMAIL", "jefe1@ejemplo.com").strip().lower()
JEFE_NOMBRE = os.environ.get("JEFE_NOMBRE", "Jefa de la Consultora")
JEFE_PASSWORD = os.environ.get("JEFE_PASSWORD", "Jefe2026*")

# HU-14: acciones que quedan en el historial.
ACCION_CREAR = "creó"
ACCION_SUBIR = "subió documento"
ACCION_APROBAR = "aprobó"
# Sprint 9: el historial cubre todas las acciones que cambian el expediente.
ACCION_ELIMINAR = "eliminó documento"
ACCION_SOMETER = "sometió"
ACCION_RESOLUCION = "registró aprobación de MiAmbiente"
ACCION_ACCESO = "cambió acceso público"
ACCION_CUENTA_PROMOTOR = "creó cuenta del promotor"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RUTAS_SIN_CABECERA = {"/login", "/registro"}
