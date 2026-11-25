const usuario = requireAuth();
if (usuario) {
  pintarTopbar();

  let expActual = null;

  async function buscar() {
    const codigo = document.getElementById('inputCodigo').value.trim();
    if (!codigo) return;
    document.getElementById('panelResultado').style.display = 'none';
    document.getElementById('panelNoEncontrado').style.display = 'none';
    document.getElementById('panelSinAcceso').style.display = 'none';
    try {
      const r = await fetch('/consulta/' + encodeURIComponent(codigo), { credentials: 'same-origin' });
      // HU-09: sin acceso público el servidor responde 403 y no entrega datos.
      if (r.status === 403) {
        document.getElementById('panelSinAcceso').style.display = 'block';
        return;
      }
      const d = await r.json();
      if (!r.ok || !d.expediente) {
        document.getElementById('panelNoEncontrado').style.display = 'block';
        return;
      }
      expActual = d.expediente;
      document.getElementById('rCodigo').textContent = expActual.codigo;
      document.getElementById('rProyecto').textContent = expActual.proyecto;
      document.getElementById('rPromotor').textContent = expActual.promotor;
      document.getElementById('rConsultor').textContent = expActual.consultor || '—';
      document.getElementById('rCategoria').innerHTML = fichaTier(expActual.categoria);
      document.getElementById('rEstado').innerHTML = `<span class="${claseEstado(expActual.estado)}">${esc(expActual.estado_publico)}</span>`;
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
    ];
    let y = 34;
    lineas.forEach(l => { doc.text(l, 20, y); y += 8; });
    doc.save(expActual.codigo + "-resumen.pdf");
  });
}
