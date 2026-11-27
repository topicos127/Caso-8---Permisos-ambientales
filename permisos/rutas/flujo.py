"""Flujo del expediente: aprobacion interna (HU-10), sometimiento (HU-08),
resolucion de MiAmbiente y devolucion con observaciones (Sprint 10); PDF de
resumen."""
import io
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file
from fpdf import FPDF

from ..almacenamiento import almacen
from ..bd import _esquema, cargar_expediente, cursor, registrar_historial
from ..config import ACCION_APROBAR, ACCION_DEVOLVER, ACCION_RECHAZO, ACCION_RESOLUCION, ACCION_SOMETER
from ..errores import ApiError
from ..reglas import ahora, calcular_verificacion, como_fecha, hoy
from ..seguridad import exigir_gestion, exigir_jefe_de, exigir_lectura, requiere_login
from ..utiles import texto

bp = Blueprint("flujo", __name__)


@bp.route("/expedientes/<codigo>/aprobar", methods=["POST"])
@requiere_login
def aprobar_expediente(codigo):
    data = request.get_json(silent=True) or {}
    motivo = texto(data, "motivo", 2000, obligatorio=False)
    if not motivo:
        return jsonify({"ok": False, "mensaje": "Motivo obligatorio."}), 400

    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_jefe_de(g.usuario, exp)  # solo el jefe de la empresa aprueba internamente
        if exp["estado"] != "pendiente":
            raise ApiError(400, "Estado invalido.")
        cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s", (exp["id"],))
        verif = calcular_verificacion(exp["categoria"], cur.fetchall())
        if not verif["puede_someter"]:
            raise ApiError(400, f"Faltan: {', '.join(verif['faltantes'])}")
        cur.execute("INSERT INTO aprobaciones (expediente_id, motivo, aprobado_por) VALUES (%s, %s, %s)",
                    (exp["id"], motivo, g.usuario["id"]))
        # Condicional: si dos pestanas aprueban a la vez, solo una cambia el estado.
        cambiadas = cur.execute("UPDATE expedientes SET estado='aprobado_interno' WHERE id=%s AND estado='pendiente'",
                                (exp["id"],))
        if cambiadas != 1:
            raise ApiError(400, "Estado invalido.")
        registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_APROBAR)
    return jsonify({"ok": True, "mensaje": "Aprobado internamente."}), 200


def cambiar_estado(codigo, desde, hacia, mensaje_error, accion, extra_sql="", extra_params=()):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        if exp["estado"] != desde:
            raise ApiError(400, mensaje_error)
        cambiadas = cur.execute(f"UPDATE expedientes SET estado=%s{extra_sql} WHERE id=%s AND estado=%s",
                                (hacia, *extra_params, exp["id"], desde))
        if cambiadas != 1:
            raise ApiError(400, mensaje_error)
        registrar_historial(cur, exp["id"], g.usuario["id"], accion)  # Sprint 9


@bp.route("/expedientes/<codigo>/someter", methods=["POST"])
@requiere_login
def someter_expediente(codigo):
    # HU-08 (Sprint 10): desde hoy corre el plazo de MiAmbiente, en dias habiles.
    extra = (", fecha_sometimiento=%s", (hoy().isoformat(),)) if _esquema["sometimiento"] else ("", ())
    cambiar_estado(codigo, "aprobado_interno", "evaluacion", "Debe aprobarse internamente primero.",
                   ACCION_SOMETER, *extra)
    return jsonify({"ok": True, "mensaje": "Sometido a MiAmbiente.",
                    "fecha_sometimiento": hoy().isoformat()}), 200


@bp.route("/expedientes/<codigo>/aprobar-miambiente", methods=["POST"])
@requiere_login
def aprobar_miambiente(codigo):
    """Atajo del Sprint 9 (aprobacion sin numero ni fecha). Se conserva para las
    suites anteriores; la pantalla usa /resolucion."""
    cambiar_estado(codigo, "evaluacion", "aprobado", "Debe estar en evaluacion.", ACCION_RESOLUCION)
    return jsonify({"ok": True, "mensaje": "Aprobado por MiAmbiente."}), 200


@bp.route("/expedientes/<codigo>/resolucion", methods=["POST"])
@requiere_login
def registrar_resolucion(codigo):
    """Sprint 10: la consultora registra la resolucion que emitio MiAmbiente:
    aprobado o rechazado, con su numero y su fecha."""
    data = request.get_json(silent=True) or {}
    resultado = data.get("resultado")
    if resultado not in ("aprobado", "rechazado"):
        raise ApiError(400, "El resultado debe ser aprobado o rechazado.")
    numero = texto(data, "numero", 60)
    valor_fecha = texto(data, "fecha", 10)
    try:
        fecha = datetime.strptime(valor_fecha, "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(400, "La fecha debe tener el formato AAAA-MM-DD.")
    if fecha > hoy():
        raise ApiError(400, "La fecha de la resolución no puede ser futura.")

    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        if exp["estado"] != "evaluacion":
            raise ApiError(400, "Solo se registra la resolución de un expediente en evaluación.")
        sometido = como_fecha(exp.get("fecha_sometimiento"))
        if sometido and fecha < sometido:
            raise ApiError(400, "La resolución no puede ser anterior al sometimiento.")
        cambiadas = cur.execute("UPDATE expedientes SET estado=%s WHERE id=%s AND estado='evaluacion'",
                                (resultado, exp["id"]))
        if cambiadas != 1:
            raise ApiError(400, "Solo se registra la resolución de un expediente en evaluación.")
        cur.execute("INSERT INTO resoluciones (expediente_id, resultado, numero, fecha_resolucion, "
                    "registrado_por, fecha_registro) VALUES (%s, %s, %s, %s, %s, %s)",
                    (exp["id"], resultado, numero, fecha.isoformat(), g.usuario["id"], ahora()))
        registrar_historial(cur, exp["id"], g.usuario["id"],
                            ACCION_RESOLUCION if resultado == "aprobado" else ACCION_RECHAZO)
    texto_resultado = "Aprobado" if resultado == "aprobado" else "Rechazado"
    return jsonify({"ok": True, "estado": resultado,
                    "mensaje": f"Resolución {numero} registrada: {texto_resultado}."}), 200


@bp.route("/expedientes/<codigo>/devolver", methods=["POST"])
@requiere_login
def devolver_con_observaciones(codigo):
    """Sprint 10: el jefe devuelve el expediente al consultor con lo que debe
    corregir. Si ya estaba aprobado internamente, vuelve a pendiente."""
    data = request.get_json(silent=True) or {}
    observaciones = texto(data, "observaciones", 2000)
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_jefe_de(g.usuario, exp, "Solo el director de proyectos devuelve expedientes.")
        if exp["estado"] not in ("pendiente", "aprobado_interno"):
            raise ApiError(400, "Solo se devuelve un expediente que aún no se ha sometido.")
        cambiadas = cur.execute("UPDATE expedientes SET estado='pendiente' WHERE id=%s AND estado=%s",
                                (exp["id"], exp["estado"]))
        if cambiadas != 1:
            raise ApiError(400, "El expediente cambió de estado. Recargue e intente de nuevo.")
        cur.execute("INSERT INTO observaciones (expediente_id, texto, autor_id, fecha) VALUES (%s, %s, %s, %s)",
                    (exp["id"], observaciones, g.usuario["id"], ahora()))
        registrar_historial(cur, exp["id"], g.usuario["id"], ACCION_DEVOLVER)
    return jsonify({"ok": True, "estado": "pendiente",
                    "mensaje": "Expediente devuelto al consultor con observaciones."}), 200


# ---------- PDF ----------

def latin1(valor):
    # Las fuentes base de FPDF solo traen latin-1; un emoji tumbaba el PDF.
    return str(valor).encode("latin-1", "replace").decode("latin-1")


def _encabezado_de_marca(pdf, marca):
    """Nombre y logo de la consultora arriba del resumen (si la empresa los configuro)."""
    if not marca:
        return
    color = marca["color"].lstrip("#")
    rojo, verde, azul = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    if marca["logo_ruta"]:
        try:
            datos = almacen().leer(marca["logo_ruta"])
            if datos:
                pdf.image(io.BytesIO(datos), x=10, y=8, h=14)
        except Exception:  # un logo ilegible no debe impedir el PDF
            pass
    pdf.set_font("Helvetica", 'B', 11)
    pdf.set_text_color(rojo, verde, azul)
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, latin1(marca["nombre"]), align='R')
    # Datos de la empresa (si el director los cargo en "Mi consultora")
    pdf.set_text_color(90, 96, 104)
    pdf.set_font("Helvetica", '', 8.5)
    lineas = [marca.get("razon_social"), f"RUC {marca['ruc']}" if marca.get("ruc") else None,
              marca.get("direccion"), " · ".join(x for x in (marca.get("telefono"), marca.get("email_contacto")) if x)]
    y = 20
    for linea in (x for x in lineas if x):
        pdf.set_xy(80, y)
        pdf.cell(120, 4, latin1(linea), align='R')
        y += 4
    pdf.set_draw_color(rojo, verde, azul)
    pdf.set_line_width(0.6)
    pdf.line(10, max(25, y + 3), 200, max(25, y + 3))
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(10, max(25, y + 3) + 7)


@bp.route("/expedientes/<codigo>/pdf", methods=["GET"])
@requiere_login
def generar_pdf_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s ORDER BY id", (exp["id"],))
        docs = cur.fetchall()
        marca = None
        if _esquema["org"] and exp.get("organizacion_id") is not None:
            extra = ", razon_social, ruc, direccion, telefono, email_contacto, pie_documento" if _esquema["org_perfil"] else ""
            cur.execute(f"SELECT nombre, color, logo_ruta{extra} FROM organizaciones WHERE id=%s", (exp["organizacion_id"],))
            marca = cur.fetchone()

    pdf = FPDF()
    pdf.add_page()
    _encabezado_de_marca(pdf, marca)
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "Resumen Ejecutivo del Expediente", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(10)

    pdf.set_font("Helvetica", '', 12)
    for etiqueta, valor in (("Codigo", exp["codigo"]), ("Proyecto", exp["proyecto"]),
                            ("Promotor", exp["promotor"]), ("Categoria", exp["categoria"]),
                            ("Estado", exp["estado"]), ("Fecha de Ingreso", exp["fecha_ingreso"])):
        pdf.cell(0, 10, latin1(f"{etiqueta}: {valor}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Documentos del expediente:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", '', 12)
    for d in docs:
        estado_doc = "Recibido" if d['estado'] == 'recibido' else "Pendiente"
        pdf.cell(0, 10, latin1(f"- {d['carpeta']}: {estado_doc}"), new_x="LMARGIN", new_y="NEXT")

    if marca and marca.get("pie_documento"):
        pdf.set_y(-24)
        pdf.set_font("Helvetica", 'I', 8)
        pdf.set_text_color(110, 116, 124)
        pdf.multi_cell(0, 4, latin1(marca["pie_documento"]), align='C')
    return send_file(io.BytesIO(bytes(pdf.output())), mimetype='application/pdf', as_attachment=True,
                     download_name=f"{exp['codigo']}-resumen.pdf")
