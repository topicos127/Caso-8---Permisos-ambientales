"""Verificacion en dos pasos (TOTP, RFC 6238) y codigos de recuperacion.

Compatible con Google Authenticator, Microsoft Authenticator, Authy y 1Password.
Sin dependencias pesadas: HMAC-SHA1, base32 y, para el QR, la libreria segno.

- El secreto se guarda cifrado (Fernet, clave derivada de SECRET_KEY).
- Un codigo TOTP solo vale una vez: se recuerda el ultimo paso usado.
- Los codigos de recuperacion (para quien pierde el telefono o la contrasena)
  se guardan como SHA-256; cada uno vale una sola vez.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

PASO = 30
DIGITOS = 6
VENTANA = 1  # tolera 30 s de desfase del reloj del telefono hacia cada lado
EMISOR = "Permisos Ambientales"
ALFABETO_RECUPERACION = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # sin 0, 1, I, L, O


def nuevo_secreto():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _clave(secreto):
    return base64.b32decode(secreto + "=" * (-len(secreto) % 8), casefold=True)


def codigo_en(secreto, paso, digitos=DIGITOS):
    mac = hmac.new(_clave(secreto), struct.pack(">Q", paso), hashlib.sha1).digest()
    desplazamiento = mac[-1] & 0x0F
    numero = (struct.unpack(">I", mac[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF) % (10 ** digitos)
    return f"{numero:0{digitos}d}"


def paso_actual(ahora=None):
    return int((time.time() if ahora is None else ahora) // PASO)


def verificar(secreto, entrada, ultimo_paso=0, ahora=None):
    """Devuelve el paso al que corresponde el codigo, o None si no es valido o ya se uso."""
    entrada = "".join(ch for ch in str(entrada or "") if ch.isdigit())
    if len(entrada) != DIGITOS:
        return None
    actual = paso_actual(ahora)
    for paso in range(actual - VENTANA, actual + VENTANA + 1):
        if paso > ultimo_paso and hmac.compare_digest(codigo_en(secreto, paso), entrada):
            return paso
    return None


def uri(secreto, cuenta):
    etiqueta = quote(f"{EMISOR}:{cuenta}", safe="")
    return (f"otpauth://totp/{etiqueta}?secret={secreto}&issuer={quote(EMISOR)}"
            f"&algorithm=SHA1&digits={DIGITOS}&period={PASO}")


def qr_svg(contenido):
    import segno
    return segno.make(contenido, error="m").svg_inline(scale=5, border=2, dark="#161c24", light="#ffffff")


# ---------- Cifrado del secreto ----------

def _fernet(clave_app):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(f"totp|{clave_app}".encode()).digest()))


def cifrar(secreto, clave_app):
    return _fernet(clave_app).encrypt(secreto.encode()).decode()


def descifrar(cifrado, clave_app):
    try:
        return _fernet(clave_app).decrypt(cifrado.encode()).decode()
    except (InvalidToken, AttributeError):
        return None


# ---------- Codigos de recuperacion ----------

def nuevo_codigo_recuperacion():
    texto = "".join(secrets.choice(ALFABETO_RECUPERACION) for _ in range(10))
    return f"{texto[:5]}-{texto[5:]}"


def normalizar_codigo(codigo):
    return "".join(ch for ch in str(codigo or "").upper() if ch.isalnum())


def hash_codigo(codigo):
    return hashlib.sha256(normalizar_codigo(codigo).encode()).hexdigest()


def parece_codigo_recuperacion(entrada):
    n = normalizar_codigo(entrada)
    return len(n) == 10 and all(ch in ALFABETO_RECUPERACION for ch in n)
