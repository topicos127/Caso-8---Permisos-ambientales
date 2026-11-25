"""Listado, creacion y detalle de expedientes; aprobaciones y plazos (HU-07);
acceso publico (HU-09) y cuenta del promotor (Sprint 9)."""
import secrets
from datetime import datetime, timezone

import pymysql
from flask import Blueprint, Response, g, jsonify, request
from werkzeug.security import generate_password_hash

from ..bd import (SQL_ULTIMA_VERSION, _esquema, cargar_expediente, col_org, col_sometimiento, col_vencimiento,
                  cursor, documentos_de, registrar_historial)
from ..config import (ACCION_ACCESO, ACCION_CREAR, ACCION_CUENTA_PROMOTOR, CATEGORIAS_DOCS, EMAIL_RE,
                      ROLES_INTERNOS)
from ..calendario import generar_ics
from ..errores import ApiError
from ..reglas import (calcular_ipe, calcular_semaforo, calcular_verificacion, hoy, problema_de_password,
                      vencimiento_documento)
from ..seguridad import exigir_gestion, exigir_jefe_de, exigir_lectura, filtro_de, requiere_login
from ..utiles import entero, formatear_fechas, paginacion, texto

bp = Blueprint("expedientes", __name__)


@bp.route("/expedientes", methods=["GET"])
@requiere_login
def listar_expedientes():
    q = request.args.get("q", "").strip()[:100]
    page = entero("page", 1, 1, 100000)
    per_page = entero("per_page", 50, 1, 100)
    orden = request.args.get("orden", "").strip()
    if orden not in ("", "fecha", "ipe"):
        raise ApiError(400, "'orden' debe ser fecha o ipe.")
    interno = g.usuario["rol"] in ROLES_INTERNOS
    # HU-15: el IPE es para la consultora; el promotor no lo ve ni ordena por el.
    por_ipe = orden == "ipe" and interno
    offset = (page - 1) * per_page

    filtro, params = filtro_de(g.usuario)
    where = f"WHERE {filtro}"
    params = list(params)
    if q:
        patron = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where += " AND (e.codigo LIKE %s OR e.proyecto LIKE %s OR e.promotor LIKE %s)"
        params.extend([patron, patron, patron])

    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM expedientes e {where}", params)
        total = cur.fetchone()["total"]
        # Por IPE se ordena en Python (es un valor calculado), asi que se traen
        # todos los que coinciden y se pagina despues.
        limite = "" if por_ipe else "LIMIT %s OFFSET %s"
        cur.execute(f"""SELECT e.id, e.codigo, e.proyecto, e.promotor, e.categoria, e.estado, e.fecha_ingreso,
                               {col_sometimiento()}, u.nombre AS consultor
                        FROM expedientes e LEFT JOIN usuarios u ON u.id = e.usuario_id
                        {where} ORDER BY e.fecha_ingreso DESC, e.id DESC {limite}""",
                    params if por_ipe else params + [per_page, offset])
        filas = cur.fetchall()
        docs = documentos_de(cur, [f["id"] for f in filas]) if interno else {}

    for f in filas:
        # HU-13: el jefe ve los plazos de cada expediente en la lista.
        sem = calcular_semaforo(f)
        f["plazo"] = {"estado_semaforo": sem["estado_semaforo"],
                      "dias_restantes_legales": sem["dias_restantes_legales"],
                      "limite_dias": sem["limite_dias"]}
        if interno:
            r = calcular_ipe(f, docs[f["id"]])
            f["ipe"] = {"valor": r["ipe"], "banda": r["banda"], "banda_texto": r["banda_texto"]}
    if por_ipe:
        # Menor a mayor: primero lo que mas necesita al equipo. Los resueltos al final.
        filas.sort(key=lambda f: (f["estado"] in ("aprobado", "rechazado"), f["ipe"]["valor"], f["codigo"]))
        filas = filas[offset:offset + per_page]
    for f in filas:
        del f["id"]
    formatear_fechas(filas, "fecha_ingreso", "%Y-%m-%d")
    formatear_fechas(filas, "fecha_sometimiento", "%Y-%m-%d")

    return jsonify({"expedientes": filas, "paginacion": paginacion(total, page, per_page)})


def siguiente_codigo(cur, prefijo):
    # El codigo sale del mayor numero usado (no de COUNT(*), que se repetia
    # si se borraba un expediente).
    cur.execute(
        "SELECT MAX(CAST(SUBSTRING(codigo, %s) AS UNSIGNED)) AS n FROM expedientes WHERE codigo LIKE %s",
        (len(prefijo) + 1, prefijo + "%"),
    )
    return f"{prefijo}{(cur.fetchone()['n'] or 0) + 1:03d}"


@bp.route("/expedientes", methods=["POST"])
@requiere_login
def crear_expediente():
    u = g.usuario
    if u["rol"] not in ROLES_INTERNOS:
        raise ApiError(403, "Solo un consultor o el director de proyectos pueden crear expedientes.")

    data = request.get_json(silent=True) or {}
    proyecto = texto(data, "proyecto", 150, obligatorio=False)
    promotor = texto(data, "promotor", 150, obligatorio=False)
    promotor_email = texto(data, "promotor_email", 255, obligatorio=False).lower() or None
    categoria = data.get("categoria", "II")
    acceso_publico = data.get("acceso_publico", True)

    if not isinstance(acceso_publico, bool):
        return jsonify({"ok": False, "mensaje": "acceso_publico debe ser true o false."}), 400
    if not proyecto or not promotor:
        return jsonify({"ok": False, "mensaje": "Proyecto y promotor son obligatorios."}), 400
    if categoria not in CATEGORIAS_DOCS:
        return jsonify({"ok": False, "mensaje": "Categoria invalida. Use I, II o III."}), 400
    if promotor_email and not EMAIL_RE.match(promotor_email):
        return jsonify({"ok": False, "mensaje": "El correo del promotor no es valido."}), 400

    if _esquema["org"] and u.get("organizacion_id") is None:
        raise ApiError(403, "Su cuenta no pertenece a ninguna empresa.")
    col_empresa, marca_empresa, valor_empresa = ((", organizacion_id", ", %s", (u["organizacion_id"],))
                                                 if _esquema["org"] else ("", "", ()))
    dia = hoy()
    prefijo = f"SP-A8-{dia.year}-"
    with cursor() as cur:
        # Si dos personas crean a la vez, el UNIQUE de codigo rechaza a la
        # segunda y se reintenta.
        for _ in range(5):
            codigo = siguiente_codigo(cur, prefijo)
            try:
                cur.execute(
                    f"""INSERT INTO expedientes (codigo, proyecto, promotor, promotor_email, categoria,
                                                estado, fecha_ingreso, usuario_id, acceso_publico{col_empresa})
                       VALUES (%s, %s, %s, %s, %s, 'pendiente', %s, %s, %s{marca_empresa})""",
                    (codigo, proyecto, promotor, promotor_email, categoria, dia.isoformat(), u["id"],
                     acceso_publico, *valor_empresa),
                )
                break
            except pymysql.err.IntegrityError:
                continue
        else:
            raise ApiError(409, "No se pudo asignar un codigo. Intente de nuevo.")

        exp_id = cur.lastrowid
        for carpeta in CATEGORIAS_DOCS[categoria]:
            cur.execute("INSERT INTO documentos (expediente_id, carpeta, estado) VALUES (%s, %s, 'pendiente')",
                        (exp_id, carpeta))
        registrar_historial(cur, exp_id, u["id"], ACCION_CREAR)

    return jsonify({"ok": True, "codigo": codigo, "mensaje": "Expediente creado."}), 201


@bp.route("/expedientes/<codigo>", methods=["GET"])
@requiere_login
def detalle_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT d.id, d.carpeta, d.estado, d.archivo_nombre, d.archivo_tamano, d.fecha_subida, "
                    f"{col_vencimiento()}, {SQL_ULTIMA_VERSION} FROM documentos d WHERE d.expediente_id=%s "
                    "ORDER BY d.id", (exp["id"],))
        docs = cur.fetchall()
        cur.execute("SELECT motivo, fecha FROM aprobaciones WHERE expediente_id=%s ORDER BY fecha DESC LIMIT 1",
                    (exp["id"],))
        aprob = cur.fetchone()
        # Sprint 10: resolucion de MiAmbiente (la ve quien puede ver el expediente)
        # y observaciones del jefe (solo la consultora).
        cur.execute("SELECT r.resultado, r.numero, r.fecha_resolucion, u.nombre AS registrado_por "
                    "FROM resoluciones r LEFT JOIN usuarios u ON u.id = r.registrado_por "
                    "WHERE r.expediente_id=%s ORDER BY r.id DESC LIMIT 1", (exp["id"],))
        resolucion = cur.fetchone()
        observaciones = []
        if g.usuario["rol"] in ROLES_INTERNOS:
            cur.execute("SELECT o.texto, o.fecha, u.nombre AS autor FROM observaciones o "
                        "LEFT JOIN usuarios u ON u.id = o.autor_id WHERE o.expediente_id=%s "
                        "ORDER BY o.fecha DESC, o.id DESC", (exp["id"],))
            observaciones = cur.fetchall()
        responsable = None
        if g.usuario["rol"] in ROLES_INTERNOS:
            cur.execute("SELECT id, nombre FROM usuarios WHERE id=%s", (exp["usuario_id"],))
            responsable = cur.fetchone()

    verificacion = calcular_verificacion(exp["categoria"], docs)
    ipe = calcular_ipe(exp, docs) if g.usuario["rol"] in ROLES_INTERNOS else None  # HU-15
    for d in docs:
        vence = vencimiento_documento(d)  # HU-05: fecha real o un ano despues de subido
        d["vence"] = vence.strftime("%d/%m/%Y") if vence else None
        d["vencimiento_real"] = bool(d.get("fecha_vencimiento"))
        d["dias_para_vencer"] = (vence - hoy()).days if vence else None
        d.pop("fecha_vencimiento", None)
    del exp["id"], exp["usuario_id"]
    exp["acceso_publico"] = bool(exp["acceso_publico"])
    if g.usuario["rol"] not in ROLES_INTERNOS:
        del exp["promotor_email"]  # el correo del promotor solo lo ve la consultora
    formatear_fechas([exp], "fecha_ingreso", "%d/%m/%Y")
    formatear_fechas([exp], "fecha_sometimiento", "%d/%m/%Y")
    formatear_fechas(docs, "fecha_subida", "%d/%m/%Y %H:%M")
    formatear_fechas([aprob], "fecha", "%d/%m/%Y %H:%M")
    formatear_fechas([resolucion], "fecha_resolucion", "%d/%m/%Y")
    formatear_fechas(observaciones, "fecha", "%d/%m/%Y %H:%M")

    return jsonify({"expediente": exp, "documentos": docs, "aprobacion": aprob, "verificacion": verificacion,
                    "ipe": ipe, "resolucion": resolucion, "observaciones": observaciones,
                    "responsable": responsable})


@bp.route("/expedientes/<codigo>/aprobaciones", methods=["GET"])
@requiere_login
def listar_aprobaciones(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("""SELECT a.id, a.motivo, a.fecha, u.nombre AS aprobado_por_nombre FROM aprobaciones a
                       LEFT JOIN usuarios u ON u.id = a.aprobado_por
                       WHERE a.expediente_id = %s ORDER BY a.fecha DESC""", (exp["id"],))
        aprobaciones = cur.fetchall()

    formatear_fechas(aprobaciones, "fecha", "%d/%m/%Y %H:%M")
    return jsonify({"expediente_codigo": exp["codigo"], "estado": exp["estado"], "aprobaciones": aprobaciones})


@bp.route("/expedientes/<codigo>/acceso-publico", methods=["POST"])
@requiere_login
def cambiar_acceso_publico(codigo):
    """HU-09: solo el jefe publica o retira un proyecto de la consulta publica."""
    data = request.get_json(silent=True) or {}
    valor = data.get("acceso_publico")
    if not isinstance(valor, bool):
        raise ApiError(400, "acceso_publico debe ser true o false.")
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_jefe_de(g.usuario, exp, "Solo el director de proyectos cambia el acceso público.")
        cur.execute("UPDATE expedientes SET acceso_publico=%s WHERE id=%s", (valor, exp["id"]))
        if bool(exp["acceso_publico"]) != valor:
            registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_ACCESO)
    return jsonify({"ok": True, "acceso_publico": valor}), 200


def contrasena_temporal():
    """Aleatoria y conforme a la politica: largo, numero y mayuscula."""
    while True:
        clave = secrets.token_urlsafe(9) + secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") + str(secrets.randbelow(10))
        if problema_de_password(clave) is None:
            return clave


@bp.route("/expedientes/<codigo>/promotor/cuenta", methods=["POST"])
@requiere_login
def crear_cuenta_promotor(codigo):
    """Sprint 9: el promotor ya no se registra solo. Su consultor (o el jefe)
    crea la cuenta con el correo del expediente y recibe una contrasena
    temporal que entrega al promotor; el promotor la cambia en «Mi cuenta»."""
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        email = exp["promotor_email"]
        if not email:
            raise ApiError(400, "El expediente no tiene correo de promotor.")
        cur.execute(f"SELECT rol, {col_org('')} FROM usuarios WHERE email=%s", (email,))
        existente = cur.fetchone()
        if existente:
            if existente["rol"] == "promotor" and existente["organizacion_id"] == exp.get("organizacion_id"):
                raise ApiError(409, "El promotor ya tiene cuenta.")
            if existente["rol"] == "promotor":
                raise ApiError(409, "Ese correo ya tiene una cuenta de promotor en otra empresa: cada cuenta "
                                    "pertenece a una sola empresa.")
            raise ApiError(409, "Ese correo ya pertenece a otra cuenta.")
        temporal = contrasena_temporal()
        try:
            # Contrasena temporal: el promotor debe cambiarla al entrar. La cuenta es de la empresa del expediente.
            columna, marca = (", debe_cambiar_clave", ", TRUE") if _esquema["cambio_clave"] else ("", "")
            if _esquema["org"]:
                columna, marca = columna + ", organizacion_id", marca + ", %s"
            cur.execute(f"INSERT INTO usuarios (nombre, email, password_hash, rol{columna}) "
                        f"VALUES (%s, %s, %s, 'promotor'{marca})",
                        (exp["promotor"], email, generate_password_hash(temporal),
                         *((exp["organizacion_id"],) if _esquema["org"] else ())))
        except pymysql.err.IntegrityError:
            raise ApiError(409, "El promotor ya tiene cuenta.")
        registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_CUENTA_PROMOTOR)
    return jsonify({
        "ok": True,
        "email": email,
        "password_temporal": temporal,
        "mensaje": "Entregue esta contraseña al promotor por un canal seguro. Se muestra una sola vez y el sistema le exigirá cambiarla en su primer ingreso.",
    }), 201


@bp.route("/expedientes/<codigo>/promotor/clave", methods=["POST"])
@requiere_login
def restablecer_clave_promotor(codigo):
    """El consultor duenio o el jefe genera una contrasena temporal nueva para el promotor
    del expediente (olvido su clave). Se muestra una sola vez y cierra sus sesiones."""
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        email = exp["promotor_email"]
        if not email:
            raise ApiError(400, "El expediente no tiene correo de promotor.")
        cur.execute(f"SELECT id, {col_org('')} FROM usuarios WHERE email=%s AND rol='promotor'", (email,))
        cuenta = cur.fetchone()
        if not cuenta or cuenta["organizacion_id"] != exp.get("organizacion_id"):
            raise ApiError(404, "El promotor todavía no tiene cuenta: créela primero.")
        temporal = contrasena_temporal()
        sets = "password_hash=%s" + (", debe_cambiar_clave=TRUE" if _esquema["cambio_clave"] else "") \
            + (", sesion_version = sesion_version + 1" if _esquema["sesion"] else "") \
            + (", totp_activo=FALSE, totp_secreto=NULL, totp_ultimo_paso=0" if _esquema["totp"] else "")
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id=%s", (generate_password_hash(temporal), cuenta["id"]))
    return jsonify({"ok": True, "email": email, "password_temporal": temporal,
                    "mensaje": "Entregue esta contraseña al promotor por un canal seguro. Se muestra una sola vez y "
                               "deberá cambiarla en su próximo ingreso."}), 200


@bp.route("/expedientes/<codigo>/alertas", methods=["GET"])
@requiere_login
def obtener_alertas(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
    return jsonify(calcular_semaforo(exp)), 200


@bp.route("/expedientes/<codigo>/plazos.ics", methods=["GET"])
@requiere_login
def calendario_de_plazos(codigo):
    """Innovacion del Sprint 10: el limite legal y los vencimientos de los
    documentos en un archivo .ics para Google Calendar u Outlook. Solo con
    sesion y permiso de lectura sobre el expediente (consultor, jefe o su
    promotor)."""
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute(f"SELECT carpeta, estado, fecha_subida, {col_vencimiento('')} FROM documentos "
                    "WHERE expediente_id=%s ORDER BY id", (exp["id"],))
        docs = cur.fetchall()
    dia = hoy()
    ics = generar_ics(exp, calcular_semaforo(exp, dia), docs, dia, datetime.now(timezone.utc))
    return Response(ics, mimetype="text/calendar",
                    headers={"Content-Type": "text/calendar; charset=utf-8",
                             "Content-Disposition": f'attachment; filename="{exp["codigo"]}_plazos.ics"'})

