"""Flujo del expediente: aprobacion interna (HU-10), sometimiento y
aprobacion de MiAmbiente (simulada); PDF de resumen."""
import io

from flask import Blueprint, g, jsonify, request, send_file
from fpdf import FPDF

from ..bd import cargar_expediente, cursor, registrar_historial
from ..config import ACCION_APROBAR
from ..errores import ApiError
from ..reglas import calcular_verificacion
from ..seguridad import exigir_gestion, exigir_jefe, exigir_lectura, requiere_login
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
        exigir_jefe(g.usuario)  # HU-13: solo el jefe aprueba internamente
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


def cambiar_estado(codigo, desde, hacia, mensaje_error):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_gestion(g.usuario, exp)
        if exp["estado"] != desde:
            raise ApiError(400, mensaje_error)
        cambiadas = cur.execute("UPDATE expedientes SET estado=%s WHERE id=%s AND estado=%s",
                                (hacia, exp["id"], desde))
        if cambiadas != 1:
            raise ApiError(400, mensaje_error)


@bp.route("/expedientes/<codigo>/someter", methods=["POST"])
@requiere_login
def someter_expediente(codigo):
    cambiar_estado(codigo, "aprobado_interno", "evaluacion", "Debe aprobarse internamente primero.")
    return jsonify({"ok": True, "mensaje": "Sometido a MiAmbiente."}), 200


@bp.route("/expedientes/<codigo>/aprobar-miambiente", methods=["POST"])
@requiere_login
def aprobar_miambiente(codigo):
    cambiar_estado(codigo, "evaluacion", "aprobado", "Debe estar en evaluacion.")
    return jsonify({"ok": True, "mensaje": "Aprobado por MiAmbiente."}), 200


# ---------- PDF ----------

def latin1(valor):
    # Las fuentes base de FPDF solo traen latin-1; un emoji tumbaba el PDF.
    return str(valor).encode("latin-1", "replace").decode("latin-1")


@bp.route("/expedientes/<codigo>/pdf", methods=["GET"])
@requiere_login
def generar_pdf_expediente(codigo):
    with cursor() as cur:
        exp = cargar_expediente(cur, codigo)
        exigir_lectura(g.usuario, exp)
        cur.execute("SELECT carpeta, estado FROM documentos WHERE expediente_id=%s ORDER BY id", (exp["id"],))
        docs = cur.fetchall()

    pdf = FPDF()
    pdf.add_page()
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

    return send_file(io.BytesIO(bytes(pdf.output())), mimetype='application/pdf', as_attachment=True,
                     download_name=f"{exp['codigo']}-resumen.pdf")
