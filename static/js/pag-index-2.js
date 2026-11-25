function claseEstado(estado) {
  if (estado === 'aprobado') return 'status status-ok';
  if (estado === 'evaluacion') return 'status status-info';
  if (estado === 'rechazado') return 'status status-bad';
  return 'status status-warn';
}
function fichaTier(cat) {
  const t = { 'I': 'Bajo impacto', 'II': 'Impacto moderado', 'III': 'Alto impacto' };
  return `<span class="tier"><b>${cat}</b> ${t[cat] || ''}</span>`;
}

let expActual = null;

async function buscar() {
  const codigo = document.getElementById('inputCodigo').value.trim();
  if (!codigo) return;

  document.getElementById('panelResultado').style.display = 'none';
  document.getElementById('panelNoEncontrado').style.display = 'none';
  document.getElementById('panelSinAcceso').style.display = 'none';

  try {
    const r = await fetch('/consulta/' + encodeURIComponent(codigo));
    // HU-09: si la consultora no habilitó el acceso público, el servidor
    // responde 403 y no entrega ningún dato (ni resumen ni PDF).
    if (r.status === 403) {
      document.getElementById('panelSinAcceso').style.display = 'block';
      return;
    }
    if (!r.ok) {
      document.getElementById('panelNoEncontrado').style.display = 'block';
      return;
    }
    const d = await r.json();
    expActual = d.expediente;
    window.expActual = expActual;

    document.getElementById('rCodigo').textContent = expActual.codigo;
    document.getElementById('rProyecto').textContent = expActual.proyecto;
    document.getElementById('rPromotor').textContent = expActual.promotor;
    document.getElementById('rConsultor').textContent = expActual.consultor || '—';
    document.getElementById('rCategoria').innerHTML = fichaTier(expActual.categoria);
    const estado = document.createElement('span');
    estado.className = claseEstado(expActual.estado);
    estado.textContent = expActual.estado_publico;
    document.getElementById('rEstado').replaceChildren(estado);

    document.getElementById('panelResultado').style.display = 'block';
  } catch (e) {
    document.getElementById('panelNoEncontrado').style.display = 'block';
  }
}

document.getElementById('btnBuscar').addEventListener('click', buscar);
document.getElementById('inputCodigo').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') buscar();
});

document.getElementById('btnPdf').addEventListener('click', () => {
  if (!expActual) return;
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  doc.setFont("helvetica", "bold"); doc.setFontSize(16);
  doc.text("Resumen Ejecutivo del Expediente", 20, 20);
  doc.setFont("helvetica", "normal"); doc.setFontSize(11);
  const lineas = [
    "Código: " + expActual.codigo,
    "Proyecto: " + expActual.proyecto,
    "Promotor: " + expActual.promotor,
    "Consultor responsable: " + (expActual.consultor || "—"),
    "Categoría: " + expActual.categoria,
    "Estado: " + expActual.estado_publico,
    "",
    "Documento generado desde el portal público de consulta.",
    "No contiene información personal de los solicitantes."
  ];
  let y = 34;
  lineas.forEach(l => { doc.text(l, 20, y); y += 8; });
  doc.save(expActual.codigo + "-resumen.pdf");
});
