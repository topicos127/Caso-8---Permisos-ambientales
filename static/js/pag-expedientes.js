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
    // HU-07: el cliente ve "aprobado_interno" como "Pendiente de subsanación".
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

  // HU-13: el director de proyectos ve todos los expedientes de la consultora y de quién es cada uno.
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

  // ---------- Vistas guardadas: filtros que se repiten, a un clic ----------
  let vistas = [];
  let vistaActiva = null;

  function filtrosActuales() {
    const f = {
      q: document.getElementById('buscador').value.trim(),
      estado: document.getElementById('filtro-estado').value,
      orden: document.getElementById('orden').value,
    };
    Object.keys(f).forEach(k => { if (!f[k]) delete f[k]; });
    return f;
  }

  function pintarVistas() {
    const caja = document.getElementById('vistas');
    caja.hidden = !vistas.length;
    caja.innerHTML = vistas.map(v => `
      <span class="chip-vista${v.id === vistaActiva ? ' activa' : ''}" data-vista="${v.id}" role="button" tabindex="0">
        ${esc(v.nombre)}<button type="button" data-borrar-vista="${v.id}" aria-label="Eliminar la vista ${esc(v.nombre)}">×</button>
      </span>`).join('');
  }

  async function cargarVistas() {
    const d = await apiFetch('/vistas');
    vistas = d.vistas || [];
    pintarVistas();
  }

  async function aplicarVista(v) {
    vistaActiva = v.id;
    document.getElementById('buscador').value = v.filtros.q || '';
    document.getElementById('filtro-estado').value = v.filtros.estado || '';
    document.getElementById('orden').value = v.filtros.orden || '';
    pintarVistas();
    await cargarLista();
  }

  document.getElementById('vistas').addEventListener('click', async (e) => {
    const borrar = e.target.closest('[data-borrar-vista]');
    if (borrar) {
      e.stopPropagation();
      const r = await apiFetch(`/vistas/${borrar.dataset.borrarVista}`, { method: 'DELETE' });
      mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
      if (vistaActiva === Number(borrar.dataset.borrarVista)) vistaActiva = null;
      await cargarVistas();
      return;
    }
    const chip = e.target.closest('[data-vista]');
    if (chip) aplicarVista(vistas.find(v => v.id === Number(chip.dataset.vista)));
  });
  document.getElementById('vistas').addEventListener('keydown', (e) => {
    const chip = e.target.closest('[data-vista]');
    if (chip && (e.key === 'Enter' || e.key === ' ') && e.target === chip) { e.preventDefault(); chip.click(); }
  });

  document.getElementById('btn-guardar-vista').addEventListener('click', () => {
    const filtros = filtrosActuales();
    if (!Object.keys(filtros).length) { mostrarToast('Aplique algún filtro antes de guardar la vista.', 'error'); return; }
    abrirModal({
      titulo: 'Guardar vista',
      html: '<div class="doc-field"><label for="m-nombre-vista">Nombre de la vista</label><input type="text" id="m-nombre-vista" maxlength="60" placeholder="Ej. Pendientes por vencer"></div><div class="doc-msg" id="m-error" role="alert"></div>',
      acciones: [
        { texto: 'Cancelar', clase: 'btn btn-ghost' },
        {
          texto: 'Guardar', clase: 'btn btn-brass',
          alHacerClic: async ({ el }) => {
            const nombre = el.querySelector('#m-nombre-vista').value.trim();
            const m = el.querySelector('#m-error');
            if (!nombre) { m.className = 'doc-msg show error'; m.textContent = 'Escriba un nombre.'; return false; }
            const r = await apiFetch('/vistas', { method: 'POST', body: JSON.stringify({ nombre, filtros }) });
            if (!r.ok) { m.className = 'doc-msg show error'; m.textContent = r.mensaje || 'No se pudo guardar.'; return false; }
            mostrarToast('Vista guardada.', 'exito');
            vistaActiva = r.id;
            await cargarVistas();
          },
        },
      ],
    });
  });

  // Si el usuario cambia un filtro a mano, ya no está en una vista guardada.
  ['buscador', 'filtro-estado', 'orden'].forEach(id => document.getElementById(id).addEventListener('input', () => {
    if (vistaActiva !== null) { vistaActiva = null; pintarVistas(); }
  }));

  // Con un código en la URL (?q=) la lista llega ya filtrada (por ejemplo, desde el panel).
  const q0 = new URLSearchParams(window.location.search).get('q');
  if (q0) document.getElementById('buscador').value = q0;

  cargarVistas().catch(console.error);
  cargarLista();
}
