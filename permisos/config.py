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
EXTENSIONES_PERMITIDAS = {".pdf", ".zip"}  # HU-01: solo PDF y ZIP (la cartografia va en ZIP)
ZONA = ZoneInfo("America/Panama")

# ---------- Sesion ----------

SECRET_KEY = os.environ.get("SECRET_KEY")
# La sesion se cierra tras estos minutos sin actividad (cada peticion la renueva).
SESION_MINUTOS = int(os.environ.get("SESION_MINUTOS", 120))
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
# El administrador de la plataforma crea las empresas y no ve expedientes.
ROL_ADMIN = "admin"
ROLES_CON_EMPRESA = {"consultor", "jefe", "promotor"}

# Empresa que recibe los datos anteriores a la separacion por empresa.
ORG_POR_DEFECTO = os.environ.get("ORG_POR_DEFECTO", "Consultora Demo")
# Colores que una empresa puede elegir (se validan: nada de CSS libre).
COLORES_EMPRESA = ("#17805a", "#2563a8", "#6a3dbf", "#b4261c", "#9a5b00", "#0e7c86", "#3e4650", "#c2410c")
INVITACION_HORAS = int(os.environ.get("INVITACION_HORAS", 72))
CODIGOS_RECUPERACION = 8

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
JEFE_NOMBRE = os.environ.get("JEFE_NOMBRE", "Mariela Quintero")
JEFE_PASSWORD = os.environ.get("JEFE_PASSWORD", "Jefe2026*")
# Administrador de la plataforma. En el despliegue definir ADMIN_PASSWORD.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ejemplo.com").strip().lower()
ADMIN_NOMBRE = os.environ.get("ADMIN_NOMBRE", "Administración de la plataforma")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin2026*")

# ---------- Archivos y respaldos ----------

# local: disco (UPLOADS_DIR). s3: cualquier servicio compatible (R2, Backblaze, MinIO, AWS).
ALMACENAMIENTO = os.environ.get("ALMACENAMIENTO", "local").lower()
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
S3_REGION = os.environ.get("S3_REGION", "auto")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/app/respaldos")
RESPALDO_AUTOMATICO = os.environ.get("RESPALDO_AUTOMATICO", "false").lower() == "true"
RESPALDO_HORA = int(os.environ.get("RESPALDO_HORA", 2))        # hora de Panama
RESPALDOS_CONSERVAR = int(os.environ.get("RESPALDOS_CONSERVAR", 14))

# HU-14: acciones que quedan en el historial.
ACCION_CREAR = "creó"
ACCION_SUBIR = "subió documento"
ACCION_APROBAR = "aprobó"
# Sprint 9: el historial cubre todas las acciones que cambian el expediente.
ACCION_ELIMINAR = "eliminó documento"  # ya no ocurre (HU-01 versiona); queda en historiales viejos
ACCION_VERSION = "subió nueva versión"
ACCION_SOMETER = "sometió"
ACCION_RESOLUCION = "registró aprobación de MiAmbiente"
ACCION_ACCESO = "cambió acceso público"
ACCION_CUENTA_PROMOTOR = "creó cuenta del promotor"
ACCION_REASIGNAR = "reasignó"  # Sprint 9: el jefe pasa el expediente a otro consultor
ACCION_RESPONSABLE = "cambió el responsable"
# Sprint 10: resolucion real de MiAmbiente y devolucion con observaciones.
ACCION_RECHAZO = "registró rechazo de MiAmbiente"
ACCION_DEVOLVER = "devolvió con observaciones"

# HU-01 (Sprint 10): la cartografia es un shapefile: el ZIP trae estos tres.
CARPETA_CARTOGRAFIA = "Cartografía"
EXTENSIONES_SHAPEFILE = (".shp", ".shx", ".dbf")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RUTAS_SIN_CABECERA = {"/login", "/registro", "/recuperar"}
