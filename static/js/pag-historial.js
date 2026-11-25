// HU-14: solo lectura. No hay botones de editar ni borrar, y el servidor
// responde 405 a cualquier intento de cambiar el historial.
const ACCION_CLASE = {
  'creó': 'status status-info',
  'subió documento': 'status status-warn',
  'aprobó': 'status status-ok',
  'eliminó documento': 'status status-bad',
  'subió nueva versión': 'status status-warn',
  'sometió': 'status status-info',
  'registró aprobación de MiAmbiente': 'status status-ok',
  'cambió acceso público': 'status status-warn',
  'creó cuenta del promotor': 'status status-info',
  'reasignó': 'status status-bad',
};

let pagina = 1;
let codigoFiltro = '';

function renderHistorial(d) {
  const tbody = document.getElementById('tabla-historial');
  const filas = d.historial || [];
  if (!filas.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="sin-etiqueta" data-label="" style="padding:24px; color:var(--ink-faint); text-align:center;">Todavía no hay acciones registradas.</td></tr>';
  } else {
    tbody.innerHTML = filas.map(h => `
      <tr>
        <td data-label="Fecha" style="padding-left:24px; white-space:nowrap; font-family:var(--mono); font-size:12.5px;">${esc(h.fecha)}</td>
        <td data-label="Expediente" style="white-space:nowrap;"><a href="expediente-detalle.html?codigo=${encodeURIComponent(h.codigo)}"><span class="case-tag">${esc(h.codigo)}</span></a></td>
        <td data-label="Proyecto">${esc(h.proyecto)}</td>
        <td data-label="Acción" style="white-space:nowrap;"><span class="${ACCION_CLASE[h.accion] || 'status status-info'}">${esc(h.accion)}</span></td>
        <td data-label="Usuario">${esc(h.usuario)}</td>
        <td data-label="Rol" style="white-space:nowrap;">${esc(ROL_TEXTO[h.usuario_rol] || h.usuario_rol)}</td>
      </tr>`).join('');
  }
  const p = d.paginacion || { page: 1, pages: 0, total: 0 };
  document.getElementById('info-pagina').textContent =
    `${p.total} acciones · página ${p.pages ? p.page : 0} de ${p.pages}`;
  document.getElementById('btnAnterior').disabled = p.page <= 1;
  document.getElementById('btnSiguiente').disabled = p.page >= p.pages;
}

async function cargar() {
  const tbody = document.getElementById('tabla-historial');
  const params = new URLSearchParams({ page: pagina, per_page: 25 });
  if (codigoFiltro) params.set('codigo', codigoFiltro);
  const d = await apiFetch('/historial?' + params.toString());
  if (d.error) {
    tbody.innerHTML = `<tr><td colspan="6" class="sin-etiqueta" data-label="" style="padding:24px; color:var(--status-bad); text-align:center;">${esc(d.error)}</td></tr>`;
    document.getElementById('info-pagina').textContent = '';
    return;
  }
  renderHistorial(d);
}

const usuario = requireAuth();
if (usuario) {
  pintarTopbar();
  if (esPromotor()) {
    // El promotor no ve el historial (el servidor también responde 403).
    window.location.href = 'expedientes.html';
  }
  if (esJefe()) {
    document.getElementById('lede-historial').textContent =
      'Quién hizo cada acción en todos los expedientes de la consultora y cuándo. El historial es de solo lectura.';
  }

  const inicial = new URLSearchParams(window.location.search).get('codigo');
  if (inicial) {
    codigoFiltro = inicial;
    document.getElementById('filtro-codigo').value = inicial;
  }

  document.getElementById('btnFiltrar').addEventListener('click', () => {
    codigoFiltro = document.getElementById('filtro-codigo').value.trim();
    pagina = 1;
    cargar();
  });
  document.getElementById('filtro-codigo').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.getElementById('btnFiltrar').click();
  });
  document.getElementById('btnTodos').addEventListener('click', () => {
    codigoFiltro = '';
    document.getElementById('filtro-codigo').value = '';
    pagina = 1;
    cargar();
  });
  document.getElementById('btnAnterior').addEventListener('click', () => { pagina--; cargar(); });
  document.getElementById('btnSiguiente').addEventListener('click', () => { pagina++; cargar(); });

  cargar().catch(console.error);
}
