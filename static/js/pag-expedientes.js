// Expedientes: el mismo conjunto de datos en cinco vistas (lista, tablero, tabla, cronograma y calendario),
// con filtros, agrupación y vistas guardadas.
const jefe = esJefe();
const interno = esJefe() || esConsultor();  // HU-15: el IPE y los comentarios son para la consultora

// ---------- Datos y estado ----------
let todos = [];
let totalServidor = 0;
let vistaActiva = null;     // id de la vista guardada aplicada (si hay)
let vistas = [];
let mesCal = null;          // { a, m } del calendario
const VISTAS = [
  ['lista', 'Lista', '<path d="M8 6h12M8 12h12M8 18h12"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>'],
  ['tablero', 'Tablero', '<rect x="3.5" y="4" width="5" height="16" rx="1.5"/><rect x="10.5" y="4" width="5" height="10" rx="1.5"/><rect x="17.5" y="4" width="3" height="13" rx="1.5"/>'],
  ['tabla', 'Tabla', '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 10h17M9.5 10v9.5"/>'],
  ['cronograma', 'Cronograma', '<path d="M4 6h9M8 12h12M6 18h8"/>'],
  ['calendario', 'Calendario', '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'],
];
const ESTADOS = [['pendiente', '#e09a1a'], ['aprobado_interno', '#7c5ac8'], ['evaluacion', '#3b6bea'], ['aprobado', '#1f9d67'], ['rechazado', '#e04b3f']];
const ETQ_ESTADO = { pendiente: 'Pendiente de subsanación', aprobado_interno: 'Aprobado internamente', evaluacion: 'En evaluación', aprobado: 'Aprobado', rechazado: 'Rechazado' };
const SEM = { en_plazo: ['#2fa66b', 'En plazo'], por_vencer: ['#f08a1c', 'Por vencer'], vencido: ['#ef4444', 'Vencido'], resuelto: ['#8a929b', 'Resuelto'] };
const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const COLUMNAS = [  // clave, titulo, disponible, visible por defecto
  ['codigo', 'Código', true, true], ['proyecto', 'Proyecto', true, true], ['cliente', 'Cliente', true, true],
  ['cat', 'Cat.', true, true], ['resp', 'Responsable', true, jefe], ['estado', 'Estado', true, true],
  ['plazo', 'Plazo', true, true], ['limite', 'Fecha límite', true, true], ['ipe', 'IPE', interno, true],
  ['docs', 'Documentos', interno, true], ['ingreso', 'Ingreso', true, false],
];

function guardado(clave, defecto) {
  try { const v = localStorage.getItem(clave); return v === null ? defecto : v; } catch (e) { return defecto; }
}
function guardar(clave, valor) { try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ } }

let vista = guardado('vista_exp', 'lista');
const hash = window.location.hash.replace('#', '');
if (VISTAS.some(v => v[0] === hash)) vista = hash;
let columnasOcultas = new Set(JSON.parse(guardado('cols_exp', 'null') || 'null')
  || COLUMNAS.filter(c => c[2] && !c[3]).map(c => c[0]));

// ---------- Utilidades ----------
const estadoVisible = (e) => (!interno && e.estado === 'aprobado_interno') ? 'pendiente' : e.estado;
const colorEstado = (k) => (ESTADOS.find(x => x[0] === k) || [0, '#8a929b'])[1];
const textoEstadoVisible = (k) => ETQ_ESTADO[k] || k;
const semDe = (e) => SEM[(e.plazo && e.plazo.estado_semaforo)] || ['#8a929b', '—'];
function fechaDe(txt) { if (!txt) return null; const [a, m, d] = String(txt).slice(0, 10).split('-').map(Number); return new Date(a, m - 1, d); }
function hoySinHora() { const h = new Date(); return new Date(h.getFullYear(), h.getMonth(), h.getDate()); }
function fechaCorta(d) { return d ? `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}` : '—'; }
function diasTxt(p) {
  if (!p || p.dias_restantes_legales == null) return '';
  const n = p.dias_restantes_legales;
  return n < 0 ? `hace ${-n} d` : n === 0 ? 'vence hoy' : `${n} d`;
}
function avatarMini(nombre) {
  return `<span class="avatar-mini" style="background:${colorDe(nombre || '?')};" title="${esc(nombre || 'Sin responsable')}">${esc(iniciales(nombre || '?'))}</span>`;
}
function limiteHtml(e) {
  const d = fechaDe(e.plazo && e.plazo.fecha_limite);
  if (!d) return '<span class="panel-note" style="margin:0;">—</span>';
  const vencido = e.plazo.estado_semaforo === 'vencido';
  return `<span class="${vencido ? 'fecha-vencida' : ''}">${fechaCorta(d)}</span>`;
}
function tierCorto(c) { return `<span class="tier" title="Categoría ${esc(c)}"><b>${esc(c)}</b></span>`; }
function urlDe(e) { return 'expediente-detalle.html?codigo=' + encodeURIComponent(e.codigo); }

// ---------- Filtros ----------
function filtrosActuales() {
  const f = {
    q: document.getElementById('buscador').value.trim(),
    estado: document.getElementById('filtro-estado').value,
    categoria: document.getElementById('filtro-categoria').value,
    responsable: document.getElementById('filtro-responsable').value,
    orden: document.getElementById('orden').value,
    grupo: document.getElementById('grupo').value,
    vista,
  };
  Object.keys(f).forEach(k => { if (!f[k]) delete f[k]; });
  return f;
}

function filtrados() {
  const f = filtrosActuales();
  const q = (f.q || '').toLowerCase();
  const lista = todos.filter(e => {
    if (q && !(`${e.codigo} ${e.proyecto} ${e.promotor} ${e.consultor || ''}`.toLowerCase().includes(q))) return false;
    if (f.estado && estadoVisible(e) !== f.estado) return false;
    if (f.categoria && e.categoria !== f.categoria) return false;
    if (f.responsable && (e.consultor || '') !== f.responsable) return false;
    return true;
  });
  if (f.orden === 'plazo') {
    lista.sort((a, b) => {
      const ra = a.plazo && a.plazo.dias_restantes_legales, rb = b.plazo && b.plazo.dias_restantes_legales;
      return (ra == null) - (rb == null) || (ra - rb) || a.codigo.localeCompare(b.codigo);
    });
  }
  return lista;
}

function grupos(lista, modo) {
  const mapa = new Map();
  const clave = (e) => modo === 'responsable' ? (e.consultor || 'Sin responsable')
    : modo === 'categoria' ? `Categoría ${e.categoria}` : modo === 'ninguno' ? 'Expedientes' : estadoVisible(e);
  lista.forEach(e => { const k = clave(e); if (!mapa.has(k)) mapa.set(k, []); mapa.get(k).push(e); });
  let claves = [...mapa.keys()];
  if (modo === 'estado') claves = ESTADOS.map(x => x[0]).filter(k => mapa.has(k));
  else claves.sort((a, b) => a.localeCompare(b));
  return claves.map(k => ({
    clave: k,
    etiqueta: modo === 'estado' ? textoEstadoVisible(k) : k,
    color: modo === 'estado' ? colorEstado(k) : modo === 'ninguno' ? '#3e4650' : colorDe(k),
    filas: mapa.get(k),
  }));
}

// ---------- Vista: lista ----------
function filaLista(e) {
  const [colorSem, etiquetaSem] = semDe(e);
  return `<a class="lista-fila" href="${urlDe(e)}">
    <span class="fila-titulo"><i class="punto-estado" style="background:${colorEstado(estadoVisible(e))};"></i>
      <span style="min-width:0;"><b>${esc(e.proyecto)}</b><small>${esc(e.codigo)}</small></span></span>
    <span class="movil-no fila-celda">${esc(e.promotor)}</span>
    <span class="movil-no fila-celda">${avatarMini(e.consultor)} <span>${esc(e.consultor || '—')}</span></span>
    <span class="movil-no fila-celda">${tierCorto(e.categoria)}</span>
    <span class="fila-celda"><span class="etiqueta-color" style="background:${colorSem}1f; color:${colorSem};">${etiquetaSem}</span>
      <small class="plazo-dias">${esc(diasTxt(e.plazo))}</small></span>
    <span class="movil-no fila-celda">${limiteHtml(e)}</span>
    <span class="movil-no fila-celda">${interno ? celdaIpe(e.ipe) : ''}</span>
  </a>`;
}

function vistaLista(lista) {
  const modo = document.getElementById('grupo').value || 'estado';
  return grupos(lista, modo).map(g => `
    <section class="grupo" data-grupo="${esc(g.clave)}">
      <header class="grupo-cab" tabindex="0" role="button" aria-expanded="true">
        <svg class="flecha" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
        <span class="grupo-etiqueta" style="background:${g.color};">${esc(g.etiqueta)}</span>
        <span class="grupo-cuenta">${g.filas.length}</span>
      </header>
      <div class="filas">
        <div class="lista-cols movil-no"><span>Proyecto</span><span>Cliente</span><span>Responsable</span><span>Cat.</span><span>Plazo</span><span>Vence</span><span>${interno ? 'Preparación' : ''}</span></div>
        ${g.filas.map(filaLista).join('')}
      </div>
    </section>`).join('');
}

// ---------- Vista: tablero ----------
function tarjetaTablero(e) {
  const [colorSem, etiquetaSem] = semDe(e);
  const d = e.documentos;
  return `<a class="tarjeta-exp" href="${urlDe(e)}">
    <div class="tarjeta-banda" style="background:${colorSem};">${etiquetaSem}</div>
    <div class="tarjeta-cuerpo">
      <h4>${esc(e.proyecto)}</h4>
      <p>${esc(e.promotor)}</p>
      <div class="tarjeta-meta">${avatarMini(e.consultor)}${fichaTier(e.categoria)}<span style="margin-left:auto;">${interno ? anilloIpe(e.ipe.valor, e.ipe.banda, 30) : ''}</span></div>
    </div>
    <div class="tarjeta-pie">
      <span title="Código"><code>${esc(e.codigo.replace('SP-A8-', ''))}</code></span>
      ${d ? `<span title="Documentos recibidos"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>${d.recibidos}/${d.total}</span>` : ''}
      ${e.comentarios ? `<span title="Comentarios internos"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12z"/></svg>${e.comentarios}</span>` : ''}
      <span class="fecha ${e.plazo && e.plazo.estado_semaforo === 'vencido' ? 'fecha-vencida' : ''}">${esc(diasTxt(e.plazo) || '')}</span>
    </div>
  </a>`;
}

function vistaTablero(lista) {
  const porEstado = grupos(lista, 'estado');
  const visibles = ESTADOS.map(x => x[0]).filter(k => interno || k !== 'aprobado_interno');
  return `<div class="tablero">${visibles.map(k => {
    const g = porEstado.find(x => x.clave === k) || { filas: [] };
    return `<section class="tablero-col"><header class="tablero-cab"><i class="barra" style="background:${colorEstado(k)};"></i>
      <b>${esc(textoEstadoVisible(k))}</b><span class="n">${g.filas.length}</span></header>
      ${g.filas.map(tarjetaTablero).join('') || '<p class="tablero-vacio">Sin expedientes</p>'}</section>`;
  }).join('')}</div>`;
}

// ---------- Vista: tabla ----------
function vistaTabla(lista) {
  const cols = COLUMNAS.filter(c => c[2] && !columnasOcultas.has(c[0]));
  const celda = {
    codigo: (e) => `<span class="case-tag">${esc(e.codigo)}</span>`,
    proyecto: (e) => `<b style="font-weight:600;">${esc(e.proyecto)}</b>`,
    cliente: (e) => esc(e.promotor),
    cat: (e) => tierCorto(e.categoria),
    resp: (e) => `<span class="nowrap">${avatarMini(e.consultor)} ${esc(e.consultor || '—')}</span>`,
    estado: (e) => `<span class="${claseEstado(e.estado)}">${textoEstado(e.estado)}</span>`,
    plazo: (e) => etiquetaPlazo(e.plazo),
    limite: (e) => limiteHtml(e),
    ipe: (e) => celdaIpe(e.ipe),
    docs: (e) => e.documentos ? `${e.documentos.recibidos}/${e.documentos.total}` : '',
    ingreso: (e) => esc(e.fecha_ingreso),
  };
  return `<div class="panel" style="padding:0; overflow-x:auto;"><table class="ledger compacta tarjetas" style="margin:0; width:100%; table-layout:auto;">
    <thead><tr>${cols.map((c, i) => `<th${i === 0 ? ' style="padding-left:22px;"' : ''}>${esc(c[1])}</th>`).join('')}<th></th></tr></thead>
    <tbody>${lista.map(e => `<tr>${cols.map((c, i) => `<td data-label="${esc(c[1])}"${i === 0 ? ' style="padding-left:22px; white-space:nowrap;"' : ''}>${celda[c[0]](e)}</td>`).join('')}
      <td data-label="" style="text-align:right; padding-right:18px;"><a class="btn btn-ghost" style="min-height:32px; padding:0 12px; font-size:13px;" href="${urlDe(e)}">Abrir</a></td></tr>`).join('')}</tbody></table></div>`;
}

// ---------- Vista: cronograma ----------
function vistaCronograma(lista) {
  const conPlazo = lista.filter(e => e.plazo && e.plazo.fecha_inicio && e.plazo.fecha_limite);
  const sinPlazo = lista.length - conPlazo.length;
  if (!conPlazo.length) return '<div class="panel"><p class="panel-note" style="margin:0;">No hay plazos en curso para mostrar con estos filtros.</p></div>';
  const hoy = hoySinHora();
  let inicio = new Date(hoy.getTime() - 21 * 86400000);
  let fin = new Date(hoy.getTime() + 35 * 86400000);
  conPlazo.forEach(e => {
    const a = fechaDe(e.plazo.fecha_inicio), b = fechaDe(e.plazo.fecha_limite);
    if (a < inicio) inicio = a;
    if (b > fin) fin = b;
  });
  inicio = new Date(inicio.getFullYear(), inicio.getMonth(), 1);
  fin = new Date(fin.getFullYear(), fin.getMonth() + 1, 0);
  const total = fin - inicio + 86400000;
  const pct = (d) => ((d - inicio) / total * 100);
  const meses = [];
  for (let d = new Date(inicio); d <= fin; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) meses.push(new Date(d));
  const lineas = meses.map(m => `<i class="crono-linea" style="left:${pct(m).toFixed(2)}%;"></i>`).join('');
  const hoyHtml = `<i class="crono-hoy" style="left:${pct(hoy).toFixed(2)}%;"></i>`;
  const modo = document.getElementById('grupo').value || (jefe ? 'responsable' : 'estado');
  const fila = (e) => {
    const [color] = semDe(e);
    const a = fechaDe(e.plazo.fecha_inicio), b = fechaDe(e.plazo.fecha_limite);
    const ancho = Math.max(pct(new Date(b.getTime() + 86400000)) - pct(a), 1.4);
    return `<div class="crono-fila"><a class="crono-etiqueta" href="${urlDe(e)}">${avatarMini(e.consultor)}<span><b>${esc(e.proyecto)}</b><small>${esc(e.codigo)}</small></span></a>
      <div class="crono-pista">${lineas}${hoyHtml}
        <a class="crono-barra" href="${urlDe(e)}" style="left:${pct(a).toFixed(2)}%; width:${ancho.toFixed(2)}%; background:${color};"
           title="${esc(e.proyecto)} · vence el ${fechaCorta(b)}">${esc(diasTxt(e.plazo))}</a></div></div>`;
  };
  const cuerpo = grupos(conPlazo, modo === 'ninguno' ? 'ninguno' : modo).map(g => `
    <div class="crono-grupo"><span style="background:${g.color};"></span>${esc(g.etiqueta)} <small>${g.filas.length}</small></div>${g.filas.map(fila).join('')}`).join('');
  return `<div class="crono"><div class="crono-grid">
    <div class="crono-cab"><div class="crono-cab-izq">Expediente</div>
      <div class="crono-meses">${meses.map((m, i) => {
        const siguiente = meses[i + 1] || new Date(fin.getTime() + 86400000);
        return `<span class="crono-mes" style="left:${pct(m).toFixed(2)}%; width:${(pct(siguiente) - pct(m)).toFixed(2)}%;">${MESES[m.getMonth()]} ${m.getFullYear()}</span>`;
      }).join('')}</div></div>${cuerpo}</div></div>
    ${sinPlazo ? `<p class="panel-note" style="margin-top:10px;">${sinPlazo} expediente(s) ya resueltos no tienen un plazo en curso.</p>` : ''}`;
}

// ---------- Vista: calendario ----------
function vistaCalendario(lista) {
  if (!mesCal) { const h = new Date(); mesCal = { a: h.getFullYear(), m: h.getMonth() }; }
  const primero = new Date(mesCal.a, mesCal.m, 1);
  const inicioGrid = new Date(primero.getFullYear(), primero.getMonth(), 1 - ((primero.getDay() + 6) % 7));  // lunes
  const hoy = hoySinHora();
  const porDia = {};
  lista.forEach(e => {
    const d = fechaDe(e.plazo && e.plazo.fecha_limite);
    if (!d) return;
    const k = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    (porDia[k] = porDia[k] || []).push(e);
  });
  const celdas = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(inicioGrid.getFullYear(), inicioGrid.getMonth(), inicioGrid.getDate() + i);
    const eventos = porDia[`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`] || [];
    celdas.push(`<div class="cal-dia${d.getMonth() !== mesCal.m ? ' fuera' : ''}${d.getTime() === hoy.getTime() ? ' hoy' : ''}">
      <span class="num">${d.getDate()}</span>
      ${eventos.slice(0, 3).map(e => `<a class="cal-evento" href="${urlDe(e)}" style="background:${semDe(e)[0]};" title="${esc(e.proyecto)}">${esc(e.proyecto)}</a>`).join('')}
      ${eventos.length > 3 ? `<span class="cal-mas">+${eventos.length - 3} más</span>` : ''}</div>`);
  }
  return `<div class="cal"><div class="cal-cab"><h3>${MESES[mesCal.m]} ${mesCal.a}</h3>
      <div class="cal-nav"><button type="button" class="btn btn-ghost" data-cal="prev" aria-label="Mes anterior">‹</button>
        <button type="button" class="btn btn-ghost" data-cal="hoy">Hoy</button>
        <button type="button" class="btn btn-ghost" data-cal="sig" aria-label="Mes siguiente">›</button></div>
      <span class="cal-leyenda">${Object.values(SEM).slice(0, 3).map(([c, t]) => `<span><i style="background:${c};"></i>${t}</span>`).join('')}</span></div>
    <div class="cal-semana">${['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'].map(d => `<span>${d}</span>`).join('')}</div>
    <div class="cal-dias">${celdas.join('')}</div></div>`;
}

// ---------- Pintar ----------
function pintar() {
  const lista = filtrados();
  const area = document.getElementById('area-vista');
  document.querySelectorAll('#tabs-vistas button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.vista === vista)));
  document.getElementById('control-agrupar').hidden = !['lista', 'cronograma'].includes(vista);
  document.getElementById('menu-columnas').hidden = vista !== 'tabla';
  if (!lista.length) {
    area.innerHTML = '<div class="panel"><p class="panel-note" style="margin:0; text-align:center; padding:18px 0;">No se encontraron expedientes con esos filtros.</p></div>';
  } else {
    area.innerHTML = { lista: vistaLista, tablero: vistaTablero, tabla: vistaTabla, cronograma: vistaCronograma, calendario: vistaCalendario }[vista](lista);
  }
  const mostrando = `${lista.length} de ${todos.length} expediente(s)`;
  document.getElementById('pie-lista').textContent = totalServidor > todos.length
    ? `${mostrando}. Hay ${totalServidor} en total: se cargan los ${todos.length} más recientes; use los filtros para acotar.` : mostrando;
}

function cambiarVista(nueva) {
  vista = nueva;
  guardar('vista_exp', nueva);
  history.replaceState(null, '', window.location.pathname + window.location.search + '#' + nueva);
  if (vistaActiva !== null) { vistaActiva = null; pintarVistas(); }
  pintar();
}

// ---------- Vistas guardadas ----------
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
  const f = v.filtros || {};
  document.getElementById('buscador').value = f.q || '';
  document.getElementById('filtro-estado').value = f.estado || '';
  document.getElementById('filtro-categoria').value = f.categoria || '';
  document.getElementById('filtro-responsable').value = f.responsable || '';
  document.getElementById('orden').value = f.orden || '';
  document.getElementById('grupo').value = f.grupo || '';
  if (VISTAS.some(x => x[0] === f.vista)) { vista = f.vista; guardar('vista_exp', vista); }
  pintarVistas();
  if (document.getElementById('orden').value === 'ipe') await cargarLista(); else pintar();
}

// ---------- Carga ----------
async function cargarLista() {
  const orden = document.getElementById('orden').value;
  const d = await apiFetch('/expedientes?per_page=100' + (orden === 'ipe' ? '&orden=ipe' : ''));
  todos = d.expedientes || [];
  totalServidor = (d.paginacion && d.paginacion.total) || todos.length;
  // Responsables para el filtro (solo el jefe ve a varios).
  if (jefe) {
    const sel = document.getElementById('filtro-responsable');
    const actual = sel.value;
    const nombres = [...new Set(todos.map(e => e.consultor).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    sel.innerHTML = '<option value="">Responsable: todos</option>' + nombres.map(n => `<option>${esc(n)}</option>`).join('');
    sel.value = actual;
  }
  pintar();
}

// ---------- Arranque ----------
const usuario = requireAuth();
if (usuario) {
  pintarTopbar();

  if (esPromotor()) {
    document.getElementById('btnNuevo').style.display = 'none';
    document.getElementById('opt-aprobado-interno').remove();
    document.getElementById('btnExportar').style.display = 'none';
  }
  if (jefe) {
    document.getElementById('titulo-lista').textContent = 'Expedientes de la consultora';
    document.getElementById('lede-lista').textContent = 'Toda la cartera, en la vista que mejor le sirva.';
    document.getElementById('filtro-responsable').hidden = false;
  } else {
    document.getElementById('lede-lista').textContent = esPromotor()
      ? 'Sus proyectos y el estado de cada trámite.' : 'Los expedientes que gestiona, en la vista que mejor le sirva.';
  }
  if (!interno) {
    document.querySelectorAll('.solo-interno').forEach(el => el.remove());
  }

  // Pestañas de vistas
  document.getElementById('tabs-vistas').innerHTML = VISTAS.map(([k, nombre, icono]) =>
    `<button type="button" role="tab" data-vista="${k}" aria-selected="${k === vista}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">${icono}</svg>${nombre}</button>`).join('');
  document.getElementById('tabs-vistas').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-vista]');
    if (b) cambiarVista(b.dataset.vista);
  });

  // Columnas de la tabla
  const lista = document.getElementById('lista-columnas');
  lista.innerHTML = COLUMNAS.filter(c => c[2]).map(c =>
    `<label><input type="checkbox" data-col="${c[0]}" ${columnasOcultas.has(c[0]) ? '' : 'checked'}> ${esc(c[1])}</label>`).join('');
  lista.addEventListener('change', (e) => {
    const c = e.target.dataset.col;
    if (!c) return;
    if (e.target.checked) columnasOcultas.delete(c); else columnasOcultas.add(c);
    guardar('cols_exp', JSON.stringify([...columnasOcultas]));
    pintar();
  });

  // Filtros
  ['buscador', 'filtro-estado', 'filtro-categoria', 'filtro-responsable', 'grupo'].forEach(id =>
    document.getElementById(id).addEventListener('input', () => { if (vistaActiva !== null) { vistaActiva = null; pintarVistas(); } pintar(); }));
  document.getElementById('orden').addEventListener('change', () => { if (vistaActiva !== null) { vistaActiva = null; pintarVistas(); } cargarLista(); });

  // Grupos plegables, calendario y vistas guardadas
  document.getElementById('area-vista').addEventListener('click', (e) => {
    const cab = e.target.closest('.grupo-cab');
    if (cab) {
      const g = cab.closest('.grupo');
      g.classList.toggle('cerrado');
      cab.setAttribute('aria-expanded', String(!g.classList.contains('cerrado')));
      return;
    }
    const nav = e.target.closest('[data-cal]');
    if (nav) {
      const h = new Date();
      if (nav.dataset.cal === 'hoy') mesCal = { a: h.getFullYear(), m: h.getMonth() };
      else { const d = new Date(mesCal.a, mesCal.m + (nav.dataset.cal === 'sig' ? 1 : -1), 1); mesCal = { a: d.getFullYear(), m: d.getMonth() }; }
      pintar();
    }
  });
  document.getElementById('area-vista').addEventListener('keydown', (e) => {
    const cab = e.target.closest('.grupo-cab');
    if (cab && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); cab.click(); }
  });

  document.getElementById('vistas').addEventListener('click', async (e) => {
    const borrar = e.target.closest('[data-borrar-vista]');
    if (borrar) {
      e.stopPropagation();
      const r = await apiFetch(`/vistas/${borrar.dataset.borrarVista}`, { method: 'DELETE' });
      mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
      if (vistaActiva === Number(borrar.dataset.borrarVista)) vistaActiva = null;
      await cargarVistas();
      pintarRail();
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
    abrirModal({
      titulo: 'Guardar vista',
      html: '<p>Guarda la vista actual (pestaña, filtros y agrupación) para abrirla con un clic desde el menú.</p><div class="doc-field"><label for="m-nombre-vista">Nombre de la vista</label><input type="text" id="m-nombre-vista" maxlength="60" placeholder="Ej. Por vencer esta semana"></div><div class="doc-msg" id="m-error" role="alert"></div>',
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
            pintarRail();
          },
        },
      ],
    });
  });

  // Todo cargado: primero los datos, luego la vista pedida en la URL (?vista=ID)
  (async () => {
    await cargarVistas().catch(console.error);
    const id = Number(new URLSearchParams(window.location.search).get('vista'));
    const pedida = id && vistas.find(v => v.id === id);
    if (pedida) await aplicarVista(pedida); else await cargarLista();
  })();
}
