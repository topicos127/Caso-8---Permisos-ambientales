let todosLosExpedientes = [];
const jefe = esJefe();
const interno = esJefe() || esConsultor();  // HU-15: el IPE es para la consultora

function renderTabla(expedientes) {
  const tbody = document.getElementById('tabla-expedientes');
  tbody.innerHTML = '';

  if (expedientes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="sin-etiqueta" data-label="" style="padding:24px; color:var(--ink-faint); text-align:center;">No se encontraron expedientes con esos filtros.</td></tr>';
    return;
  }

  expedientes.forEach(e => {
    tbody.innerHTML += `
      <tr>
        <td data-label="Código" style="padding-left:24px; white-space:nowrap;"><span class="case-tag">${esc(e.codigo)}</span></td>
        <td data-label="Proyecto"><div style="display:flex; flex-direction:column; gap:2px;"><b style="font-weight:600;">${esc(e.proyecto)}</b><span style="font-size:12.5px; color:var(--ink-faint);">${esc(e.promotor)}</span></div></td>
        <td data-label="Categoría"><span class="tier" title="Categoría ${esc(e.categoria)}"><b>${esc(e.categoria)}</b></span></td>
        ${jefe ? `<td data-label="Consultor">${esc(e.consultor || '—')}</td>` : ''}
        <td data-label="Estado" style="white-space:nowrap;"><span class="${claseEstado(e.estado)}">${textoEstado(e.estado)}</span></td>
        <td data-label="Plazo" style="white-space:nowrap;">${etiquetaPlazo(e.plazo)}</td>
        ${interno ? `<td data-label="IPE" style="white-space:nowrap;">${celdaIpe(e.ipe)}</td>` : ''}
        <td data-label="Fecha" style="white-space:nowrap; font-family:var(--mono); font-size:12.5px;">${esc(e.fecha_ingreso)}</td>
        <td data-label="" style="white-space:nowrap; text-align:right; padding-right:20px;"><a class="btn btn-ghost" style="min-height:34px; padding:0 12px; font-size:13px;" href="expediente-detalle.html?codigo=${encodeURIComponent(e.codigo)}">Abrir</a></td>
      </tr>
    `;
  });
}

function aplicarFiltros() {
  const texto = document.getElementById('buscador').value.toLowerCase();
  const estado = document.getElementById('filtro-estado').value;

  const filtrados = todosLosExpedientes.filter(e => {
    const coincideTexto = e.codigo.toLowerCase().includes(texto) || e.proyecto.toLowerCase().includes(texto);
    // HU-07: el promotor ve "aprobado_interno" como "Pendiente de subsanación".
    const coincideEstado = estado === '' || e.estado === estado
      || (!interno && estado === 'pendiente' && e.estado === 'aprobado_interno');
    return coincideTexto && coincideEstado;
  });

  renderTabla(filtrados);
}

const usuario = requireAuth();
if (usuario) {
  pintarTopbar();

  if (esPromotor()) {
    const btn = document.getElementById('btnNuevo');
    if (btn) btn.style.display = 'none';
    document.getElementById('opt-aprobado-interno').remove();
  }

  // HU-13: el jefe ve todos los expedientes de la consultora y de quién es cada uno.
  if (jefe) {
    document.getElementById('titulo-lista').textContent = 'Expedientes de la consultora';
    document.getElementById('lede-lista').textContent =
      'Todos los expedientes de la consultora, con su consultor, estado y plazo legal.';
    document.querySelectorAll('.col-consultor').forEach(th => th.style.display = '');
  }

  if (interno) {
    document.querySelectorAll('.col-ipe').forEach(th => th.style.display = '');
    document.getElementById('orden').style.display = '';
  }

  function cargarLista() {
    const orden = document.getElementById('orden').value;
    return apiFetch('/expedientes' + (orden ? '?orden=' + encodeURIComponent(orden) : '')).then(d => {
      todosLosExpedientes = d.expedientes || [];
      aplicarFiltros();
    }).catch(console.error);
  }

  document.getElementById('buscador').addEventListener('input', aplicarFiltros);
  document.getElementById('filtro-estado').addEventListener('change', aplicarFiltros);
  document.getElementById('orden').addEventListener('change', cargarLista);

  cargarLista();
}
