"""Listado, creacion y detalle de expedientes; aprobaciones y plazos (HU-07)."""
import pymysql
from flask import Blueprint, g, jsonify, request

from ..bd import cargar_expediente, cursor, registrar_historial
from ..config import ACCION_CREAR, CATEGORIAS_DOCS, EMAIL_RE, ROLES_INTERNOS
from ..errores import ApiError
from ..reglas import calcular_semaforo, calcular_verificacion, hoy
from ..seguridad import exigir_lectura, filtro_de, requiere_login
from ..utiles import entero, formatear_fechas, paginacion, texto

bp = Blueprint("expedientes", __name__)


@bp.route("/expedientes", methods=["GET"])
@requiere_login
def listar_expedientes():
    q = request.args.get("q", "").strip()[:100]
    page = entero("page", 1, 1, 100000)
    per_page = entero("per_page", 50, 1, 100)
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
        cur.execute(f"""SELECT e.codigo, e.proyecto, e.promotor, e.categoria, e.estado, e.fecha_ingreso,
                               u.nombre AS consultor
                        FROM expedientes e LEFT JOIN usuarios u ON u.id = e.usuario_id
                        {where} ORDER BY e.fecha_ingreso DESC, e.id DESC LIMIT %s OFFSET %s""",
                    params + [per_page, offset])
        filas = cur.fetchall()

    for f in filas:
        # HU-13: el jefe ve los plazos de cada expediente en la lista.
        sem = calcular_semaforo(f)
        f["plazo"] = {"estado_semaforo": sem["estado_semaforo"],
                      "dias_restantes_legales": sem["dias_restantes_legales"],
                      "limite_dias": sem["limite_dias"]}
    formatear_fechas(filas, "fecha_ingreso", "%Y-%m-%d")

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
        raise ApiError(403, "Solo un consultor o el jefe pueden crear expedientes.")

    data = request.get_json(silent=True) or {}
    proyecto = texto(data, "proyecto", 150, obligatorio=False)
    promotor = texto(data, "promotor", 150, obligatorio=False)
    promotor_email = texto(data, "promotor_email", 255, obligatorio=False).lower() or None
    categoria = data.get("categoria", "II")

    if not proyecto or not promotor:
        return jsonify({"ok": False, "mensaje": "Proyecto y promotor son obligatorios."}), 400
    if categoria not in CATEGORIAS_DOCS:
        return jsonify({"ok": False, "mensaje": "Categoria invalida. Use I, II o III."}), 400
    if promotor_email and not EMAIL_RE.match(promotor_email):
        return jsonify({"ok": False, "mensaje": "El correo del promotor no es valido."}), 400

    dia = hoy()
    prefijo = f"SP-A8-{dia.year}-"
    with cursor() as cur:
        # Si dos personas crean a la vez, el UNIQUE de codigo rechaza a la
        # segunda y se reintenta.
        for _ in range(5):
            codigo = siguiente_codigo(cur, prefijo)
            try:
                cur.execute(
                    """INSERT INTO expedientes (codigo, proyecto, promotor, promotor_email, categoria,
                                                estado, fecha_ingreso, usuario_id)
                       VALUES (%s, %s, %s, %s, %s, 'pendiente', %s, %s)""",
                    (codigo, proyecto, promotor, promotor_email, categoria, dia.isoformat(), u["id"]),
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
        cur.execute("SELECT id, carpeta, estado, archivo_nombre, archivo_tamano, fecha_subida "
                    "FROM documentos WHERE expediente_id=%s ORDER BY id", (exp["id"],))
        docs = cur.fetchall()
        cur.execute("SELECT motivo, fecha FROM aprobaciones WHERE expediente_id=%s ORDER BY fecha DESC LIMIT 1",
                    (exp["id"],))
        aprob = cur.fetchone()

    verificacion = calcular_verificacion(exp["categoria"], docs)
    for campo in ("id", "usuario_id", "promotor_email", "acceso_publico"):
        del exp[campo]
    formatear_fechas([exp], "fecha_ingreso", "%d/%m/%Y")
    formatear_fechas(docs, "fecha_subida", "%d/%m/%Y %H:%M")
    formatear_fechas([aprob], "fecha", "%d/%m/%Y %H:%M")

    return jsonify({"expediente": exp, "documentos": docs, "aprobacion": aprob, "verificacion": verificacion})


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


@bp.route("/expedientes/<codigo>/alertas", methods=["GET"])
@requiere_login
def obtener_alertas(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
    return jsonify(calcular_semaforo(exp)), 200
