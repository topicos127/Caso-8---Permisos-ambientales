"""Datos de demostracion de Apto: dos consultoras ficticias, con todo cargado, para presentar la plataforma.

Uso (en la Console de Railway, o en local con las variables de la base):

    DEMO_PASSWORD='SuClaveDeDemo1' python scripts/demo_produccion.py     # crea (o rehace) las dos empresas
    python scripts/demo_produccion.py --borrar                            # elimina todo lo demo

- Las dos empresas, sus cuentas, expedientes y documentos son ficticios. Las cuentas usan la contrasena
  que usted indica en DEMO_PASSWORD (no esta escrita en el repositorio) y terminan en @istmo.demo y
  @pacifico.demo.
- Los datos se crean con la propia aplicacion (la misma validacion, historial, trazabilidad y almacenamiento
  que un uso real) y despues se ajustan las fechas para que haya siempre un plazo vencido, uno por vencer y
  varios en plazo. Volver a correrlo refresca las fechas.
- Solo toca las empresas marcadas como demostracion (RUC "DEMO-..."). Nunca toca datos reales.
"""
import argparse
import hashlib
import io
import math
import os
import struct
import sys
import zipfile
import zlib
from datetime import datetime, time, timedelta
from urllib.parse import quote

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

MARCA_DEMO = "DEMO-"           # prefijo del RUC: asi se reconoce lo que es demostracion
CABECERA = {"X-Requested-With": "fetch"}

# ---------------------------------------------------------------------------------------------- empresas
# nombre, color, razon social, ruc, direccion, telefono, dominio de los correos
EMPRESAS = [
    {
        "clave": "istmo", "nombre": "Consultora Ambiental Istmo", "color": "#17805a", "ruc": "DEMO-0001",
        "razon": "Consultora Ambiental Istmo, S.A. (ficticia)", "direccion": "Calle 50, Ciudad de Panamá",
        "telefono": "+507 000-0001", "dominio": "istmo.demo", "logo": False,
        "directores": [("Carolina Mendieta", "direccion"), ("Rodrigo Arosemena", "director2")],
        "consultores": [("Andrés Vallarino", "consultor1"), ("Mariana Cedeño", "consultor2"),
                        ("Tomás Barrios", "consultor3")],
        "clientes": [("Fernando Alvarado", "cliente1", "Inmobiliaria Costa Verde S.A."),
                     ("Lucía Pinzón", "cliente2", "Hidroeléctrica Río Chico S.A."),
                     ("Esteban Ruiz", "cliente3", "Agroindustrias del Valle S.A.")],
    },
    {
        "clave": "pacifico", "nombre": "EcoGestión del Pacífico", "color": "#2563a8", "ruc": "DEMO-0002",
        "razon": "EcoGestión del Pacífico, S.A. (ficticia)", "direccion": "Vía España, Ciudad de Panamá",
        "telefono": "+507 000-0002", "dominio": "pacifico.demo", "logo": True,
        "directores": [("Gabriela Ortega", "direccion"), ("Ricardo Montenegro", "director2")],
        "consultores": [("Valeria Espino", "consultor1"), ("Javier Castrellón", "consultor2"),
                        ("Natalia Samaniego", "consultor3")],
        "clientes": [("Daniel Sucre", "cliente1", "Desarrollos Playa Blanca S.A."),
                     ("Paola Herrera", "cliente2", "Energía Solar Coclé S.A.")],
    },
]

# ---------------------------------------------------------------------------------------------- expedientes
# proyecto, cliente (1..n), categoria, estado, dias desde el ingreso, consultor (1..3), documentos subidos,
# dias desde el sometimiento (o None), (resultado, dias desde la resolucion) o None, acceso publico, extras
EXPEDIENTES = {
    "istmo": [
        ("Urbanización Brisas del Golfo", 1, "II", "pendiente", 33, 1, 3, None, None, True, {"nueva_version": True}),
        ("Hotel Boutique Playa Serena", 1, "III", "aprobado_interno", 46, 2, 5, None, None, True, {}),
        ("Centro Comercial Plaza Boquete", 1, "II", "evaluacion", 62, 3, 4, 20, None, True,
         {"responsable": 2, "vence_en": 9}),
        ("Residencial Altos de Gorgona", 1, "I", "aprobado", 80, 1, 3, 60, ("aprobado", 35), True, {}),
        ("Marina y Muelle Isla Grande", 1, "III", "pendiente", 12, 2, 2, None, None, True, {}),
        ("Central Hidroeléctrica Río Chico II", 2, "III", "evaluacion", 120, 1, 5, 90, None, True,
         {"vencido_hace": 6}),
        ("Línea de Transmisión Chiriquí-Veraguas", 2, "III", "rechazado", 150, 2, 5, 110, ("rechazado", 70), False, {}),
        ("Mini Hidro Quebrada Honda", 2, "II", "evaluacion", 75, 3, 4, 49, None, True, {}),
        ("Planta Procesadora de Arroz", 3, "II", "pendiente", 8, 3, 1, None, None, True, {}),
        ("Granja Porcina Los Llanos", 3, "I", "evaluacion", 45, 1, 3, 33, None, True, {}),
        ("Sistema de Riego Azuero", 3, "II", "aprobado_interno", 28, 2, 4, None, None, True, {}),
        ("Planta de Tratamiento Villa Esperanza", 3, "I", "pendiente", 24, 3, 3, None, None, True, {"devuelto": True}),
    ],
    "pacifico": [
        ("Complejo Turístico Playa Blanca", 1, "III", "evaluacion", 100, 1, 5, 70, None, True, {"vence_en": 12}),
        ("Residencial Mar y Sol", 1, "II", "pendiente", 14, 2, 2, None, None, True, {}),
        ("Parque Solar Coclé 50 MW", 2, "III", "aprobado", 140, 1, 5, 100, ("aprobado", 60), True, {}),
        ("Subestación Eléctrica Penonomé", 2, "II", "aprobado_interno", 30, 3, 4, None, None, True, {}),
        ("Estación de Servicio La Ribera", 1, "I", "rechazado", 60, 2, 3, 45, ("rechazado", 20), False, {}),
        ("Almacén Logístico Colón", 2, "II", "evaluacion", 55, 3, 4, 20, None, True, {}),
        ("Granja Solar Los Santos", 2, "II", "pendiente", 38, 1, 3, None, None, True, {}),
        ("Hostal Ecológico Boca Chica", 1, "I", "pendiente", 25, 2, 1, None, None, True, {}),
    ],
}

# comentarios internos: (expediente 1..n, autor, texto, dias atras). autor: "director", "director2", "consultorN"
COMENTARIOS = {
    "istmo": [
        (3, "consultor3", "Pendiente de MiAmbiente: ya respondimos la solicitud de aclaraciones del 3 de este mes.", 6),
        (3, "direccion", "Gracias. Si no hay respuesta esta semana, llamamos a la oficina regional.", 5),
        (6, "direccion", "Este expediente ya está en el último tramo del plazo. Prioridad esta semana.", 4),
        (6, "consultor1", "Actualicé la cartografía y subí la versión corregida del plan de manejo.", 3),
        (12, "direccion", "Falta el paz y salvo del promotor; se lo pedimos y lo adjuntamos al anexo legal.", 2),
        (10, "consultor1", "El promotor confirmó que la fecha de la consulta ciudadana se mantiene.", 7),
    ],
    "pacifico": [
        (1, "direccion", "Faltan 18 días para el límite del plazo: revisar con el cliente la respuesta a MiAmbiente.", 3),
        (1, "consultor1", "Quedó cargada la evidencia del foro público con las firmas escaneadas.", 8),
        (7, "consultor1", "Cartografía pendiente: el topógrafo entrega el shapefile el viernes.", 2),
    ],
}

OBSERVACION = ("El anexo legal no incluye el paz y salvo vigente del promotor ni la copia del aviso de consulta. "
               "Corregir y volver a presentar para aprobación interna.")

# ---------------------------------------------------------------------------------------------- archivos de demostracion


def latin1(texto):
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def pdf_demo(empresa, proyecto, codigo, carpeta, version):
    """PDF pequeno con texto real (distinto en cada documento y version, asi cada huella es unica)."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 17)
    pdf.multi_cell(0, 10, latin1(carpeta), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.ln(3)
    for linea in (f"Proyecto: {proyecto}", f"Expediente: {codigo}", f"Consultora: {empresa}", f"Versión: {version}"):
        pdf.multi_cell(0, 8, latin1(linea), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 11)
    pdf.multi_cell(0, 7, latin1(
        "DOCUMENTO DE DEMOSTRACIÓN. Este archivo es ficticio y se generó automáticamente para mostrar "
        "cómo Apto guarda, versiona y entrega los documentos de un estudio de impacto ambiental. "
        "No contiene información real."), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def zip_cartografia(proyecto):
    """ZIP con un shapefile minimo (.shp, .shx y .dbf), suficiente para la validacion de la carpeta Cartografia."""
    base = hashlib.sha1(proyecto.encode("utf-8")).hexdigest()[:8]
    cabecera = b"\x00\x00\x27\x0a" + b"\x00" * 20 + struct.pack(">i", 50) + struct.pack("<ii", 1000, 1) + b"\x00" * 64
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"mapa_{base}/area.shp", cabecera)
        z.writestr(f"mapa_{base}/area.shx", cabecera[:100])
        z.writestr(f"mapa_{base}/area.dbf", b"\x03\x7e\x0b\x1c" + b"\x00" * 60)
        z.writestr(f"mapa_{base}/LEEME.txt", f"Cartografía de demostración de {proyecto}.\n".encode("utf-8"))
    return salida.getvalue()


def png_logo(color_hex, lado=128):
    """Logo sencillo (cuadrado redondeado con un anillo) en PNG, sin dependencias externas."""
    rojo, verde, azul = (int(color_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    radio, centro = 26.0, lado / 2
    filas = bytearray()
    for y in range(lado):
        filas.append(0)
        for x in range(lado):
            px, py = x + 0.5, y + 0.5
            dx = max(abs(px - centro) - (centro - radio), 0)
            dy = max(abs(py - centro) - (centro - radio), 0)
            if math.hypot(dx, dy) > radio:
                filas += bytes((0, 0, 0, 0))
                continue
            d = math.hypot(px - centro, py - centro)
            if 20 <= d <= 34:
                filas += bytes((255, 255, 255, 255))
            elif d < 11:
                filas += bytes((255, 255, 255, 255))
            else:
                filas += bytes((rojo, verde, azul, 255))

    def trozo(tipo, datos):
        c = tipo + datos
        return struct.pack(">I", len(datos)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(bytes(filas), 9)) + trozo(b"IEND", b""))


def archivo_de(carpeta, empresa, proyecto, codigo, version):
    """(nombre, contenido) del archivo que corresponde a cada carpeta."""
    base = "".join(c if c.isalnum() else "_" for c in latin1(carpeta).replace(" ", "_"))
    if carpeta == "Cartografía":
        return f"{base}_{codigo[-3:]}.zip", zip_cartografia(f"{proyecto}-{version}")
    return f"{base}_{codigo[-3:]}_v{version}.pdf", pdf_demo(empresa, proyecto, codigo, carpeta, version)


# ---------------------------------------------------------------------------------------------- linea de tiempo


def momento(dia, hora, minuto=0):
    return datetime.combine(dia, time(hora, minuto))


def linea_de_tiempo(spec, eventos, hoy_, ahora_):
    """Hora de cada evento del historial, en el orden en que ocurrieron. Siempre creciente y nunca en el futuro."""
    dias, somet, resol = spec["dias"], spec["somet"], spec["resol"]
    ingreso = hoy_ - timedelta(days=dias)
    tramo = max(1, min(dias - 1, 10))                    # los documentos se suben en los primeros dias
    n_docs = max(1, sum(1 for e in eventos if e[0] == "doc"))
    fecha_somet = hoy_ - timedelta(days=somet) if somet is not None else None
    fecha_resol = hoy_ - timedelta(days=resol[1]) if resol else None
    fecha_aprob = min(ingreso + timedelta(days=tramo + 1), (fecha_somet - timedelta(days=1)) if fecha_somet else hoy_ - timedelta(days=1))
    fecha_aprob = max(fecha_aprob, ingreso)
    tiempos, i_doc, previo = [], 0, None
    for ev in eventos:
        tipo = ev[0]
        if tipo == "crear":
            t = momento(ingreso, 9, 15)
        elif tipo == "doc":
            t = momento(ingreso + timedelta(days=1 + (i_doc * tramo) // n_docs), 10 + i_doc % 6, 5 * i_doc % 55)
            i_doc += 1
        elif tipo == "aprobar":
            t = momento(fecha_aprob, 15, 20)
        elif tipo == "devolver":
            t = momento(fecha_aprob, 16, 5)
        elif tipo == "someter":
            t = momento(fecha_somet, 11, 0)
        elif tipo == "resolver":
            t = momento(fecha_resol, 16, 40)
        else:  # responsable y otros cambios: poco despues de lo anterior
            t = (previo or momento(ingreso, 9, 15)) + timedelta(hours=3)
        if previo is not None and t <= previo:
            t = previo + timedelta(minutes=1)
        t = min(t, ahora_ - timedelta(minutes=5))
        tiempos.append(t)
        previo = t
    return tiempos


# ---------------------------------------------------------------------------------------------- borrado


def _en(ids):
    return ",".join(["%s"] * len(ids))


def borrar_demo():
    """Elimina las empresas de demostracion y todo lo suyo (y sus archivos). Devuelve cuantas empresas borro."""
    from permisos import bd
    from permisos.almacenamiento import almacen
    with bd.cursor() as cur:
        cur.execute("SELECT id, logo_ruta FROM organizaciones WHERE ruc LIKE %s", (MARCA_DEMO + "%",))
        orgs = cur.fetchall()
        if not orgs:
            return 0
        ids = [o["id"] for o in orgs]
        m = _en(ids)
        rutas = {o["logo_ruta"] for o in orgs if o["logo_ruta"]}
        for sql in (
            f"SELECT v.archivo_ruta AS r FROM documento_versiones v JOIN documentos d ON d.id=v.documento_id "
            f"JOIN expedientes e ON e.id=d.expediente_id WHERE e.organizacion_id IN ({m})",
            f"SELECT d.archivo_ruta AS r FROM documentos d JOIN expedientes e ON e.id=d.expediente_id "
            f"WHERE e.organizacion_id IN ({m})",
        ):
            cur.execute(sql, ids)
            rutas |= {f["r"] for f in cur.fetchall() if f["r"]}
        hijos = (
            "documento_versiones v JOIN documentos d ON d.id=v.documento_id JOIN expedientes e ON e.id=d.expediente_id",
            "documentos d JOIN expedientes e ON e.id=d.expediente_id",
            "aprobaciones d JOIN expedientes e ON e.id=d.expediente_id",
            "alertas d JOIN expedientes e ON e.id=d.expediente_id",
            "historial_expediente d JOIN expedientes e ON e.id=d.expediente_id",
            "resoluciones d JOIN expedientes e ON e.id=d.expediente_id",
            "observaciones d JOIN expedientes e ON e.id=d.expediente_id",
            "comentarios d JOIN expedientes e ON e.id=d.expediente_id",
        )
        for tabla in hijos:
            alias = tabla.split()[1]
            cur.execute(f"DELETE {alias} FROM {tabla} WHERE e.organizacion_id IN ({m})", ids)
        cur.execute(f"DELETE FROM expedientes WHERE organizacion_id IN ({m})", ids)
        cur.execute(f"SELECT id FROM usuarios WHERE organizacion_id IN ({m})", ids)
        usuarios = [u["id"] for u in cur.fetchall()]
        if usuarios:
            mu = _en(usuarios)
            for tabla in ("vistas_guardadas", "codigos_recuperacion"):
                cur.execute(f"DELETE FROM {tabla} WHERE usuario_id IN ({mu})", usuarios)
        cur.execute(f"DELETE FROM invitaciones WHERE organizacion_id IN ({m})", ids)
        cur.execute(f"DELETE FROM eventos_cuenta WHERE organizacion_id IN ({m})", ids)
        cur.execute(f"UPDATE organizaciones SET titular_id=NULL WHERE id IN ({m})", ids)
        cur.execute(f"DELETE FROM usuarios WHERE organizacion_id IN ({m})", ids)
        cur.execute(f"DELETE FROM organizaciones WHERE id IN ({m})", ids)
    for ruta in rutas:
        try:
            almacen().borrar(ruta)
        except Exception as e:  # noqa: BLE001 - un archivo que ya no esta no debe detener el borrado
            print(f"  aviso: no se pudo borrar el archivo {ruta}: {e!r}")
    return len(ids)


# ---------------------------------------------------------------------------------------------- creacion


class Sesion:
    """Una persona usando la aplicacion (por dentro, sin red): inicia sesion y llama a la API."""

    def __init__(self, app, email, clave):
        self.cliente = app.test_client()
        r = self.cliente.post("/login", json={"email": email, "password": clave}, headers=CABECERA)
        datos = r.get_json() or {}
        if r.status_code != 200 or not datos.get("acceso"):
            raise SystemExit(f"No se pudo iniciar sesión como {email}: {datos.get('mensaje')}")

    def post(self, ruta, **kw):
        return self.cliente.post(ruta, headers=CABECERA, **kw)


def _ok(r, contexto):
    if r.status_code not in (200, 201):
        raise SystemExit(f"Falló {contexto}: {r.status_code} {r.get_data(as_text=True)[:300]}")
    return r.get_json()


def crear_empresas_y_cuentas(clave):
    from werkzeug.security import generate_password_hash
    from permisos import bd
    from permisos.almacenamiento import almacen
    ahora_ = datetime.now()
    hash_ = generate_password_hash(clave)
    columnas_extra = ""
    valores_extra = []
    if bd._esquema["terminos"]:
        columnas_extra += ", terminos_aceptados_en"
        valores_extra.append(ahora_)
    if bd._esquema["tour"]:
        columnas_extra += ", tour_visto_en"
        valores_extra.append(ahora_)
    marca = "".join(", %s" for _ in valores_extra)
    cuentas = {}
    with bd.cursor() as cur:
        for e in EMPRESAS:
            cur.execute("SELECT id, ruc FROM organizaciones WHERE nombre=%s", (e["nombre"],))
            previa = cur.fetchone()
            if previa:
                raise SystemExit(f"Ya existe una empresa llamada «{e['nombre']}» que no es de demostración. No se toca.")
            cur.execute("INSERT INTO organizaciones (nombre, color, razon_social, ruc, direccion, telefono, "
                        "email_contacto, pie_documento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (e["nombre"], e["color"], e["razon"], e["ruc"], e["direccion"], e["telefono"],
                         f"contacto@{e['dominio']}", f"{e['nombre']} · datos de demostración"))
            org = cur.lastrowid
            e["org_id"] = org
            lista = {}

            def nueva(nombre, usuario, rol):
                correo = f"{usuario}@{e['dominio']}"
                cur.execute(f"INSERT INTO usuarios (nombre, email, password_hash, rol, organizacion_id{columnas_extra}) "
                            f"VALUES (%s, %s, %s, %s, %s{marca})", (nombre, correo, hash_, rol, org, *valores_extra))
                return {"id": cur.lastrowid, "nombre": nombre, "email": correo, "rol": rol}
            lista["directores"] = [nueva(n, u, "jefe") for n, u in e["directores"]]
            lista["consultores"] = [nueva(n, u, "consultor") for n, u in e["consultores"]]
            lista["clientes"] = [dict(nueva(n, u, "promotor"), empresa=emp) for n, u, emp in e["clientes"]]
            cur.execute("UPDATE organizaciones SET titular_id=%s WHERE id=%s", (lista["directores"][0]["id"], org))
            cuentas[e["clave"]] = lista
            if e["logo"]:
                datos = png_logo(e["color"])
                ruta = f"organizaciones/{org}/logo-demo.png"
                almacen().guardar(ruta, datos)
                cur.execute("UPDATE organizaciones SET logo_ruta=%s WHERE id=%s", (ruta, org))
    return cuentas


def crear_expedientes(app, empresa, cuentas, clave):
    from permisos import bd
    from permisos.config import CATEGORIAS_DOCS
    from permisos.reglas import ahora, hoy
    hoy_, ahora_ = hoy(), ahora()
    sesiones = {}

    def sesion(persona):
        if persona["email"] not in sesiones:
            sesiones[persona["email"]] = Sesion(app, persona["email"], clave)
        return sesiones[persona["email"]]

    directores, consultores, clientes = cuentas["directores"], cuentas["consultores"], cuentas["clientes"]
    por_clave = {"direccion": directores[0], "director2": directores[1]}
    for i, c in enumerate(consultores, 1):
        por_clave[f"consultor{i}"] = c
    codigos = []

    for n, fila in enumerate(EXPEDIENTES[empresa["clave"]], 1):
        proyecto, idx_cliente, cat, estado, dias, idx_cons, n_docs, somet, resol, publico, extras = fila
        cliente, consultor = clientes[idx_cliente - 1], consultores[idx_cons - 1]
        spec = {"dias": dias, "somet": somet, "resol": resol}
        s_cons, s_dir = sesion(consultor), sesion(directores[0])
        r = _ok(s_cons.post("/expedientes", json={"proyecto": proyecto, "promotor": cliente["empresa"],
                                                  "promotor_email": cliente["email"], "categoria": cat,
                                                  "acceso_publico": publico}), f"crear {proyecto}")
        codigo = r["codigo"]
        eventos = [("crear",)]
        carpetas = CATEGORIAS_DOCS[cat][:n_docs]
        for k, carpeta in enumerate(carpetas):
            nombre, contenido = archivo_de(carpeta, empresa["nombre"], proyecto, codigo, 1)
            datos = {"archivo": (io.BytesIO(contenido), nombre)}
            if extras.get("vence_en") and k == 0:
                datos["fecha_vencimiento"] = (hoy_ + timedelta(days=extras["vence_en"])).isoformat()
            r = s_cons.post(f"/expedientes/{codigo}/documentos/{quote(carpeta)}/subir", data=datos,
                            content_type="multipart/form-data")
            _ok(r, f"subir {carpeta} de {proyecto}")
            eventos.append(("doc", carpeta, 1))
        if extras.get("nueva_version"):
            carpeta = carpetas[0]
            nombre, contenido = archivo_de(carpeta, empresa["nombre"], proyecto, codigo, 2)
            _ok(s_cons.post(f"/expedientes/{codigo}/documentos/{quote(carpeta)}/subir",
                            data={"archivo": (io.BytesIO(contenido), nombre)}, content_type="multipart/form-data"),
                f"nueva versión de {proyecto}")
            eventos.append(("doc", carpeta, 2))
        if estado in ("aprobado_interno", "evaluacion", "aprobado", "rechazado") or extras.get("devuelto"):
            _ok(s_dir.post(f"/expedientes/{codigo}/aprobar", json={
                "motivo": "Documentación verificada y completa."}), f"aprobar {proyecto}")
            eventos.append(("aprobar",))
        if extras.get("devuelto"):
            _ok(s_dir.post(f"/expedientes/{codigo}/devolver", json={"observaciones": OBSERVACION}), f"devolver {proyecto}")
            eventos.append(("devolver",))
        if estado in ("evaluacion", "aprobado", "rechazado"):
            _ok(s_cons.post(f"/expedientes/{codigo}/someter", json={}), f"someter {proyecto}")
            eventos.append(("someter",))
        if resol:
            numero = f"DEMO-IA-{n + (100 if empresa['clave'] == 'pacifico' else 0):03d}-{hoy_.year}"
            _ok(s_cons.post(f"/expedientes/{codigo}/resolucion", json={
                "resultado": resol[0], "numero": numero, "fecha": hoy_.isoformat()}), f"resolución de {proyecto}")
            eventos.append(("resolver",))
        if extras.get("responsable"):
            nuevo = consultores[extras["responsable"] - 1]
            _ok(s_dir.post(f"/expedientes/{codigo}/responsable", json={"usuario_id": nuevo["id"]}), f"responsable de {proyecto}")
            eventos.append(("responsable",))
        codigos.append((n, codigo, spec, eventos, extras))

    # comentarios internos (se publican con la API y luego se les pone fecha)
    comentarios = []
    for n, autor, texto, hace in COMENTARIOS[empresa["clave"]]:
        _, codigo, _, _, extras = codigos[n - 1]
        persona = por_clave[autor]
        # un consultor solo comenta en lo suyo: si el expediente pasó a otro responsable, sigue la conversación el nuevo
        if persona["rol"] == "consultor" and extras.get("responsable"):
            persona = consultores[extras["responsable"] - 1]
        _ok(sesion(persona).post(f"/expedientes/{codigo}/comentarios", json={"texto": texto}), f"comentario en {codigo}")
        comentarios.append((codigo, texto, hace))

    # ----- fechas: se llevan al pasado, con todo en orden cronologico -----
    with bd.cursor() as cur:
        for n, codigo, spec, eventos, extras in codigos:
            cur.execute("SELECT id FROM expedientes WHERE codigo=%s", (codigo,))
            exp_id = cur.fetchone()["id"]
            tiempos = linea_de_tiempo(spec, eventos, hoy_, ahora_)
            ingreso = hoy_ - timedelta(days=spec["dias"])
            cur.execute("UPDATE expedientes SET fecha_ingreso=%s WHERE id=%s", (ingreso, exp_id))
            if spec["somet"] is not None:
                cur.execute("UPDATE expedientes SET fecha_sometimiento=%s WHERE id=%s",
                            (hoy_ - timedelta(days=spec["somet"]), exp_id))
            cur.execute("SELECT id FROM historial_expediente WHERE expediente_id=%s ORDER BY id", (exp_id,))
            filas = [f["id"] for f in cur.fetchall()]
            if len(filas) != len(tiempos):
                print(f"  aviso: {codigo} tiene {len(filas)} eventos y se esperaban {len(tiempos)}; no se ajusta su historial")
            else:
                for fid, t in zip(filas, tiempos):
                    cur.execute("UPDATE historial_expediente SET fecha=%s WHERE id=%s", (t, fid))
            ultimo = {}
            for ev, t in zip(eventos, tiempos):
                if ev[0] == "doc":
                    cur.execute("SELECT d.id FROM documentos d WHERE d.expediente_id=%s AND d.carpeta=%s", (exp_id, ev[1]))
                    doc_id = cur.fetchone()["id"]
                    cur.execute("UPDATE documento_versiones SET fecha_subida=%s WHERE documento_id=%s AND version=%s",
                                (t, doc_id, ev[2]))
                    ultimo[doc_id] = t
                elif ev[0] == "aprobar":
                    cur.execute("UPDATE aprobaciones SET fecha=%s WHERE expediente_id=%s ORDER BY id DESC LIMIT 1", (t, exp_id))
                elif ev[0] == "devolver":
                    cur.execute("UPDATE observaciones SET fecha=%s WHERE expediente_id=%s ORDER BY id DESC LIMIT 1", (t, exp_id))
                elif ev[0] == "resolver":
                    cur.execute("UPDATE resoluciones SET fecha_resolucion=%s, fecha_registro=%s WHERE expediente_id=%s",
                                (t.date(), t, exp_id))
            for doc_id, t in ultimo.items():
                cur.execute("UPDATE documentos SET fecha_subida=%s WHERE id=%s", (t, doc_id))
            if extras.get("vencido_hace"):  # un documento ya vencido, para ver la alerta roja
                cur.execute("UPDATE documentos SET fecha_vencimiento=%s WHERE expediente_id=%s AND estado='recibido' "
                            "ORDER BY id LIMIT 1", (hoy_ - timedelta(days=extras["vencido_hace"]), exp_id))
        for codigo, texto, hace in comentarios:
            cur.execute("UPDATE comentarios c JOIN expedientes e ON e.id=c.expediente_id SET c.fecha=%s "
                        "WHERE e.codigo=%s AND c.texto=%s", (ahora_ - timedelta(days=hace, hours=2), codigo, texto))
    return [c[1] for c in codigos]


def sembrar_accesos(empresa, cuentas):
    """Un rastro de inicios de sesion de los ultimos 14 dias para «Mi consultora → Accesos» (IP de documentacion)."""
    from permisos import bd
    from permisos.reglas import ahora
    ahora_ = ahora()
    personas = cuentas["directores"] + cuentas["consultores"]
    with bd.cursor() as cur:
        for i in range(24):
            p = personas[i % len(personas)]
            cuando = ahora_ - timedelta(days=(i * 13) // 24 + 1, hours=(i * 5) % 9 + 1, minutes=(i * 17) % 60)
            cur.execute("INSERT INTO eventos_cuenta (organizacion_id, usuario_id, email, tipo, detalle, ip, fecha) "
                        "VALUES (%s, %s, %s, 'acceso', '', %s, %s)",
                        (empresa["org_id"], p["id"], p["email"], f"203.0.113.{10 + i % 40}", cuando))


def crear_demo(clave):
    from permisos import bd, create_app
    from permisos.reglas import problema_de_password
    problema = problema_de_password(clave or "")
    if problema:
        raise SystemExit(f"DEMO_PASSWORD no sirve: {problema}")
    app = create_app()
    app.config["SESSION_COOKIE_SECURE"] = False   # las llamadas son internas, sin HTTPS de por medio
    if not bd._estado_bd["lista"]:
        bd.asegurar_bd()
    if not bd._estado_bd["lista"]:
        raise SystemExit("La base de datos no está lista. Corra antes scripts/init_db.py.")
    previas = borrar_demo()
    if previas:
        print(f"Se rehacen los datos de demostración existentes ({previas} empresas).")
    cuentas = crear_empresas_y_cuentas(clave)
    for e in EMPRESAS:
        print(f"Creando expedientes de {e['nombre']}...")
        codigos = crear_expedientes(app, e, cuentas[e["clave"]], clave)
        sembrar_accesos(e, cuentas[e["clave"]])
        print(f"  {len(codigos)} expedientes con documentos, historial y comentarios.")
    resumen(cuentas)


def resumen(cuentas):
    print("\n=== Cuentas de demostración (la contraseña es la que indicó en DEMO_PASSWORD) ===")
    for e in EMPRESAS:
        c = cuentas[e["clave"]]
        print(f"\n{e['nombre']}")
        for rol, lista in (("Director de proyectos", c["directores"]), ("Consultor ambiental", c["consultores"]),
                           ("Cliente", c["clientes"])):
            for p in lista:
                extra = f"  ({p['empresa']})" if "empresa" in p else ""
                print(f"  {rol:<22} {p['email']:<28} {p['nombre']}{extra}")
    print("\nEntre por /login con cualquiera de esas cuentas. Para quitar todo: python scripts/demo_produccion.py --borrar")


def main():
    ap = argparse.ArgumentParser(description="Datos de demostración de Apto (dos consultoras ficticias).")
    ap.add_argument("--borrar", action="store_true", help="elimina las empresas de demostración y todo lo suyo")
    args = ap.parse_args()
    if args.borrar:
        from permisos import create_app
        create_app()
        n = borrar_demo()
        print(f"Se eliminaron {n} empresas de demostración." if n else "No hay datos de demostración.")
        return
    crear_demo(os.environ.get("DEMO_PASSWORD"))


if __name__ == "__main__":
    main()
