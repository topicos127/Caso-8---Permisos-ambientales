"""
Sistema de Permisos Ambientales - Seed completo

Uso:
    python seed_usuarios.py          usuarios y 3 expedientes (CI y pruebas de Robot)
    python seed_usuarios.py --demo   ademas, 7 expedientes de demostracion con fechas
                                     relativas a hoy, para ver el UI/UX con datos
                                     (tambien con SEED_DEMO_RICO=true)
"""
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone

import pymysql
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "permisos123"),
    "database": os.environ.get("DB_NAME", "permisos_ambientales"),
}

USUARIOS = [
    ("Carlos Herrera", "consultor1@ejemplo.com", "Clave123", "consultor"),
    ("Luis Batista", "promotor1@ejemplo.com", "Clave456", "promotor"),
    # Sprint 8: segundo consultor, para probar que cada consultor ve solo lo
    # suyo y el jefe ve todo. El jefe lo crea la app al arrancar (app.py).
    ("Ana Ríos", "consultor2@ejemplo.com", "Clave2026", "consultor"),
]

# codigo, proyecto, promotor, promotor_email, categoria, estado, fecha, email_consultor
EXPEDIENTES = [
    ("SP-A8-2026-001", "Planta Solar Azuero",  "Energía Verde S.A.",     "promotor1@ejemplo.com", "II",  "pendiente",        "2026-09-10", "consultor1@ejemplo.com"),
    ("SP-A8-2026-002", "Hotel Costero Bocas",  "Inversiones del Caribe", "promotor1@ejemplo.com", "III", "pendiente",        "2026-09-05", "consultor1@ejemplo.com"),
    ("SP-A8-2026-003", "Reforestación Darién", "ONG Ambiental",          None,                    "I",   "aprobado",         "2026-08-28", "consultor1@ejemplo.com"),
]

DOCS_POR_CAT = {
    "I":   ["Línea Base", "Plan de Manejo", "Anexos Legales"],
    "II":  ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía"],
    "III": ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía", "Evidencia Foro Público"],
}

ALERTAS = [
    ("SP-A8-2026-001", "Paz y salvo del Municipio vence en 12 días", 12),
    ("SP-A8-2026-001", "Certificado de registro vence en 28 días", 28),
]


# Expedientes de demostracion (--demo). Las fechas son relativas a hoy (hora de
# Panama, UTC-5), asi siempre hay un plazo vencido, uno por vencer y varios en plazo.
# codigo, proyecto, promotor, correo, categoria, estado, dias desde el ingreso,
# consultor, documentos recibidos, dias desde que se subieron, acceso publico
DEMO_EXPEDIENTES = [
    ("SP-A8-2026-101", "Parque Eólico Coclé", "Energía del Pacífico S.A.", "promotor1@ejemplo.com", "III", "pendiente", 75, "consultor1@ejemplo.com", 4, 10, True),
    ("SP-A8-2026-102", "Urbanización Costa del Este", "Grupo Inmobiliario Istmo", None, "II", "pendiente", 5, "consultor2@ejemplo.com", 2, 3, True),
    ("SP-A8-2026-103", "Planta de Tratamiento Chiriquí", "Aguas del Occidente", None, "I", "aprobado_interno", 12, "consultor2@ejemplo.com", 3, 8, True),
    ("SP-A8-2026-104", "Puerto Seco Colón", "Logística Atlántica S.A.", "promotor1@ejemplo.com", "III", "evaluacion", 30, "consultor1@ejemplo.com", 5, 25, True),
    ("SP-A8-2026-105", "Reforestación Azuero", "Fundación Verde Azuero", None, "I", "aprobado", 50, "consultor2@ejemplo.com", 3, 45, True),
    ("SP-A8-2026-106", "Hidroeléctrica Bocas", "Hidro Bocas S.A.", None, "II", "pendiente", 38, "consultor1@ejemplo.com", 3, 340, True),
    ("SP-A8-2026-107", "Eco-Lodge Boquete", "Turismo Sostenible Panamá", None, "II", "pendiente", 52, "consultor2@ejemplo.com", 1, 20, False),
]
JEFE_EMAIL = os.environ.get("JEFE_EMAIL", "jefe1@ejemplo.com").strip().lower()

# Empresas de prueba. La primera recibe a todos los usuarios y expedientes de arriba; la segunda
# existe para comprobar que una consultora no ve lo de otra.
EMPRESA_A = os.environ.get("ORG_POR_DEFECTO", "Consultora Demo")
EMPRESA_B = "Ambiental del Pacífico"
USUARIOS_B = [
    ("Rosa Ibarra", "jefe2@ejemplo.com", "Jefe2026*", "jefe"),
    ("Mateo Quiroz", "consultor3@ejemplo.com", "Clave2026", "consultor"),
]
# codigo, proyecto, promotor, categoria, estado, dias desde el ingreso, correo del consultor
EXPEDIENTES_B = [
    ("SP-A8-2026-201", "Parque Solar Chiriquí", "Energía del Pacífico", "II", "pendiente", 10, "consultor3@ejemplo.com"),
]


def sembrar_empresas(cur):
    """Crea las dos empresas de prueba y devuelve {nombre: id}; {} si la base es anterior a las empresas."""
    try:
        for nombre, color in ((EMPRESA_A, "#17805a"), (EMPRESA_B, "#2563a8")):
            cur.execute("INSERT IGNORE INTO organizaciones (nombre, color) VALUES (%s, %s)", (nombre, color))
        cur.execute("SELECT nombre, id FROM organizaciones")
    except pymysql.MySQLError:
        return {}
    return {nombre: id_ for nombre, id_ in cur.fetchall()}


def sembrar_segunda_empresa(cur, empresas, ahora):
    org = empresas[EMPRESA_B]
    for nombre, email, password, rol in USUARIOS_B:
        cur.execute(
            """INSERT INTO usuarios (nombre, email, password_hash, rol, organizacion_id)
               VALUES (%s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), nombre=VALUES(nombre),
                                       organizacion_id=VALUES(organizacion_id)""",
            (nombre, email, generate_password_hash(password), rol, org))
    for codigo, proyecto, promotor, categoria, estado, dias, email_consultor in EXPEDIENTES_B:
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email_consultor,))
        consultor = cur.fetchone()[0]
        ingreso = (ahora - timedelta(days=dias)).date()
        cur.execute(
            """INSERT INTO expedientes (codigo, proyecto, promotor, categoria, estado, fecha_ingreso, usuario_id,
                                        organizacion_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE proyecto=VALUES(proyecto), promotor=VALUES(promotor),
                 categoria=VALUES(categoria), estado=VALUES(estado), fecha_ingreso=VALUES(fecha_ingreso),
                 usuario_id=VALUES(usuario_id), organizacion_id=VALUES(organizacion_id)""",
            (codigo, proyecto, promotor, categoria, estado, ingreso, consultor, org))
        cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
        exp_id = cur.fetchone()[0]
        borrar_documentos_de_prueba(cur, exp_id)
        for carpeta in DOCS_POR_CAT[categoria]:
            cur.execute("INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, 'pendiente')",
                        (exp_id, carpeta))


def borrar_documentos_de_prueba(cur, exp_id):
    """Reinicio de datos de prueba: el seed rehace los documentos de sus propios
    expedientes. La app nunca borra versiones (HU-01); solo este script lo hace,
    y solo para los expedientes que siembra."""
    try:
        cur.execute("DELETE v FROM documento_versiones v JOIN documentos d ON d.id = v.documento_id "
                    "WHERE d.expediente_id=%s", (exp_id,))
    except pymysql.MySQLError:
        pass  # base anterior al Sprint 9: la tabla de versiones aun no existe
    cur.execute("DELETE FROM documentos WHERE expediente_id=%s", (exp_id,))


def sembrar_demo(cur):
    ahora = datetime.now(timezone(timedelta(hours=-5))).replace(tzinfo=None, microsecond=0)

    def id_usuario(email):
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        fila = cur.fetchone()
        return fila[0] if fila else None

    # La jefa la crea la app al arrancar, pero el seed puede correr antes: se
    # crea aqui si falta (la app no la duplica: busca por correo).
    if not id_usuario(JEFE_EMAIL):
        cur.execute("INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, 'jefe')",
                    (os.environ.get("JEFE_NOMBRE", "Mariela Quintero"), JEFE_EMAIL,
                     generate_password_hash(os.environ.get("JEFE_PASSWORD", "Jefe2026*"))))
    jefe = id_usuario(JEFE_EMAIL)
    try:
        cur.execute("SELECT 1 FROM historial_expediente LIMIT 1")
        hay_historial = True
    except pymysql.MySQLError:
        hay_historial = False  # la app lo crea al arrancar

    for (codigo, proyecto, promotor, prom_email, categoria, estado, dias, email_consultor,
         recibidos, subidos_hace, publico) in DEMO_EXPEDIENTES:
        ingreso = ahora - timedelta(days=dias)
        consultor = id_usuario(email_consultor)
        cur.execute(
            """INSERT INTO expedientes
               (codigo, proyecto, promotor, promotor_email, categoria, estado, fecha_ingreso, usuario_id, acceso_publico)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                 proyecto=VALUES(proyecto), promotor=VALUES(promotor), promotor_email=VALUES(promotor_email),
                 categoria=VALUES(categoria), estado=VALUES(estado), fecha_ingreso=VALUES(fecha_ingreso),
                 usuario_id=VALUES(usuario_id), acceso_publico=VALUES(acceso_publico)""",
            (codigo, proyecto, promotor, prom_email, categoria, estado, ingreso.date(), consultor, publico),
        )
        cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
        exp_id = cur.fetchone()[0]
        # Sprint 10 (HU-08): los ya sometidos guardan su fecha de sometimiento
        # (la misma del evento "sometió" del historial de abajo).
        sometido = (ingreso + timedelta(days=min(dias, 6))).date() if estado in ("evaluacion", "aprobado") else None
        try:
            cur.execute("UPDATE expedientes SET fecha_sometimiento=%s WHERE id=%s", (sometido, exp_id))
        except pymysql.MySQLError:
            pass  # base anterior al Sprint 10: la app agrega la columna al arrancar

        borrar_documentos_de_prueba(cur, exp_id)
        subidas = []
        for i, carpeta in enumerate(DOCS_POR_CAT[categoria]):
            if i < recibidos:
                # En el 106 el primer documento es el que esta por vencer; los demas son recientes.
                hace = subidos_hace if i == 0 else min(subidos_hace, 30)
                fecha = ahora - timedelta(days=hace)
                subidas.append(fecha)
                cur.execute(
                    """INSERT INTO documentos (expediente_id, carpeta, estado, archivo_nombre, archivo_tamano, fecha_subida)
                       VALUES (%s, %s, 'recibido', %s, %s, %s)""",
                    (exp_id, carpeta, f"{carpeta.replace(' ', '_')}.pdf", 184320, fecha))
                # HU-01: version 1 con su codigo de trazabilidad (sin archivo real en disco).
                doc_id = cur.lastrowid
                sha = hashlib.sha256(f"{codigo}/{carpeta}/demo".encode("utf-8")).hexdigest()
                try:
                    cur.execute("""INSERT INTO documento_versiones (documento_id, version, codigo_trazabilidad,
                                   archivo_nombre, archivo_tamano, sha256, subido_por, fecha_subida)
                                   VALUES (%s, 1, %s, %s, %s, %s, %s, %s)""",
                                (doc_id, f"{codigo}-D{doc_id}-V1-{sha[:8].upper()}",
                                 f"{carpeta.replace(' ', '_')}.pdf", 184320, sha, consultor, fecha))
                except pymysql.MySQLError:
                    pass  # base anterior al Sprint 9
            else:
                cur.execute("INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, 'pendiente')",
                            (exp_id, carpeta))

        # Aprobaciones e historial: solo datos de demostracion, se reescriben en cada corrida.
        cur.execute("DELETE FROM aprobaciones WHERE expediente_id=%s", (exp_id,))
        if jefe and estado != "pendiente":
            cur.execute("INSERT INTO aprobaciones (expediente_id, motivo, aprobado_por, fecha) VALUES (%s, %s, %s, %s)",
                        (exp_id, "Documentación verificada y completa (datos de demostración).", jefe,
                         ingreso + timedelta(days=min(dias, 5))))
        if hay_historial and consultor:
            cur.execute("DELETE FROM historial_expediente WHERE expediente_id=%s", (exp_id,))
            eventos = [(ingreso, consultor, "creó")]
            eventos += [(f, consultor, "subió documento") for f in sorted(subidas)]
            if jefe and estado != "pendiente":
                eventos.append((ingreso + timedelta(days=min(dias, 5)), jefe, "aprobó"))
            if estado in ("evaluacion", "aprobado"):
                eventos.append((ingreso + timedelta(days=min(dias, 6)), consultor, "sometió"))
            if estado == "aprobado":
                eventos.append((ingreso + timedelta(days=min(dias, 20)), consultor, "registró aprobación de MiAmbiente"))
            for fecha, usuario, accion in eventos:
                cur.execute("INSERT INTO historial_expediente (expediente_id, usuario_id, accion, fecha) "
                            "VALUES (%s, %s, %s, %s)", (exp_id, usuario, accion, max(fecha, ingreso)))


def main(demo=False):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # Usuarios
            for nombre, email, password, rol in USUARIOS:
                cur.execute(
                    """INSERT INTO usuarios (nombre, email, password_hash, rol)
                       VALUES (%s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), nombre=VALUES(nombre)""",
                    (nombre, email, generate_password_hash(password), rol),
                )
            # El jefe que crea la app al arrancar traia un nombre de cargo; si nadie
            # lo cambio, pasa a un nombre de persona (la bienvenida lo usa).
            cur.execute("UPDATE usuarios SET nombre=%s WHERE email=%s AND nombre='Jefa de la Consultora'",
                        (os.environ.get("JEFE_NOMBRE", "Mariela Quintero"), JEFE_EMAIL))

            # Expedientes + documentos
            for codigo, proyecto, promotor, prom_email, categoria, estado, fecha, email_consultor in EXPEDIENTES:
                cur.execute("SELECT id FROM usuarios WHERE email=%s", (email_consultor,))
                row = cur.fetchone()
                uid = row[0] if row else None

                cur.execute(
                    """INSERT INTO expedientes
                       (codigo, proyecto, promotor, promotor_email, categoria, estado, fecha_ingreso, usuario_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                         proyecto=VALUES(proyecto), promotor=VALUES(promotor),
                         promotor_email=VALUES(promotor_email),
                         categoria=VALUES(categoria), estado=VALUES(estado),
                         fecha_ingreso=VALUES(fecha_ingreso), usuario_id=VALUES(usuario_id)""",
                    (codigo, proyecto, promotor, prom_email, categoria, estado, fecha, uid),
                )

                cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
                exp_id = cur.fetchone()[0]

                borrar_documentos_de_prueba(cur, exp_id)
                docs = DOCS_POR_CAT[categoria]
                for i, carpeta in enumerate(docs):
                    # Solo los expedientes pendientes dejan el ultimo documento
                    # sin subir; uno aprobado o en evaluacion ya los tiene todos.
                    estado_doc = "pendiente" if (i == len(docs) - 1 and estado == "pendiente") else "recibido"
                    cur.execute(
                        "INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, %s)",
                        (exp_id, carpeta, estado_doc),
                    )

            # Alertas
            cur.execute("DELETE FROM alertas")
            for codigo, descripcion, dias in ALERTAS:
                cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "INSERT INTO alertas (expediente_id, descripcion, dias_restantes) VALUES (%s, %s, %s)",
                        (row[0], descripcion, dias),
                    )

            if demo:
                sembrar_demo(cur)

            # Empresas: lo sembrado arriba (sin empresa) pasa a la primera; la segunda trae lo suyo.
            empresas = sembrar_empresas(cur)
            if empresas:
                ahora = datetime.now(timezone(timedelta(hours=-5))).replace(tzinfo=None, microsecond=0)
                cur.execute("UPDATE usuarios SET organizacion_id=%s WHERE organizacion_id IS NULL AND rol <> 'admin'",
                            (empresas[EMPRESA_A],))
                cur.execute("UPDATE expedientes SET organizacion_id=%s WHERE organizacion_id IS NULL",
                            (empresas[EMPRESA_A],))
                sembrar_segunda_empresa(cur, empresas, ahora)

        conn.commit()
        print("Seed completo: empresas, usuarios, expedientes, documentos y alertas"
              + (" y expedientes de demostracion." if demo else "."))
    finally:
        conn.close()


if __name__ == "__main__":
    main(demo="--demo" in sys.argv or os.environ.get("SEED_DEMO_RICO", "").lower() == "true")