// Helpers de API compartidos por las pantallas internas.
//
// Sprint 7: la sesion la lleva una cookie del servidor. sessionStorage solo
// guarda el nombre y el rol para pintar la barra; el servidor no lo usa.

// Escapa texto antes de meterlo en innerHTML (evita XSS con nombres de
// proyecto, promotores, motivos, etc.).
function esc(valor) {
  return String(valor ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Cabeceras para cualquier fetch propio: el servidor rechaza los POST sin
// X-Requested-With (proteccion contra CSRF).
function cabecerasApi(extra) {
  return Object.assign({ 'X-Requested-With': 'fetch' }, extra || {});
}

function getUsuario() {
  try { return JSON.parse(sessionStorage.getItem('usuario') || 'null'); }
  catch { return null; }
}

function requireAuth() {
  const u = getUsuario();
  if (!u || !u.email) { window.location.href = paginaDeAcceso(); return null; }
  // Sprint 9: con una contraseña temporal, solo "Mi cuenta" está disponible.
  if (u.debe_cambiar_clave && !window.location.pathname.endsWith('cuenta.html')) {
    window.location.href = 'cuenta.html?obligatorio=1';
    return null;
  }
  if (u.rol === 'admin' && !PAGINAS_DEL_ADMIN.some(p => window.location.pathname.endsWith(p))) {
    window.location.href = '/admin/panel';
    return null;
  }
  return u;
}

function esPromotor() {
  const u = getUsuario();
  return u && u.rol === 'promotor';
}

function esConsultor() {
  const u = getUsuario();
  return u && u.rol === 'consultor';
}

// HU-13: el director de proyectos ve todo y es quien aprueba internamente.
function esJefe() {
  const u = getUsuario();
  return u && u.rol === 'jefe';
}

const ROL_TEXTO = { promotor: 'Cliente', consultor: 'Consultor ambiental', jefe: 'Director de proyectos', admin: 'Administración de la plataforma' };

// Administrador de la plataforma: crea empresas, ve el estado y los respaldos. No ve expedientes.
function esAdmin() {
  const u = getUsuario();
  return u && u.rol === 'admin';
}

// Paginas que el administrador puede abrir; cualquier otra lo lleva a la plataforma.
const PAGINAS_DEL_ADMIN = ['/admin/panel', 'cuenta.html', 'ayuda.html', 'estado.html'];

// A donde se manda a quien no tiene sesion: la administracion tiene su propia entrada (/admin).
function paginaDeAcceso(rol) {
  return (rol === 'admin' || window.location.pathname.startsWith('/admin')) ? '/admin' : 'login.html';
}

// HU-07/HU-13: etiqueta corta del plazo para las listas.
const PLAZO_ETIQUETA = {
  en_plazo:   ['status status-ok',   'En plazo'],
  por_vencer: ['status status-warn', 'Por vencer'],
  vencido:    ['status status-bad',  'Vencido'],
  resuelto:   ['status status-neutral', 'Resuelto'],
};

function etiquetaPlazo(plazo) {
  if (!plazo) return '—';
  const [clase, texto] = PLAZO_ETIQUETA[plazo.estado_semaforo] || ['status status-info', '—'];
  const n = plazo.dias_restantes_legales;
  let dias = '';
  if (plazo.estado_semaforo !== 'resuelto' && n != null) {
    dias = n < 0 ? ` · hace ${esc(-n)} d` : n === 0 ? ' · vence hoy' : ` · ${esc(n)} d`;
  }
  return `<span class="${clase}">${texto}${dias}</span>`;
}

// HU-15: etiqueta del Indice de Preparacion (0 a 100) con su banda.
const IPE_CLASE = { listo: 'status status-ok', en_preparacion: 'status status-warn', en_riesgo: 'status status-bad' };

function etiquetaIpe(ipe) {
  if (!ipe) return '—';
  return `<span class="${IPE_CLASE[ipe.banda] || 'status status-info'}">${esc(ipe.valor)} · ${esc(ipe.banda_texto)}</span>`;
}

// Nuevo UI/UX: color de cada banda del IPE (listo, en preparacion, en riesgo).
const IPE_COLOR = { listo: '#1f9d67', en_preparacion: '#e09a1a', en_riesgo: '#e04b3f' };

// Anillo pequeño con el valor del IPE, para tablas y listas.
function anilloIpe(valor, banda, tam = 34) {
  const v = Math.max(0, Math.min(100, Number(valor) || 0));
  const color = IPE_COLOR[banda] || '#8a929b';
  const largo = (87.96 * v / 100).toFixed(1);
  return `<svg width="${tam}" height="${tam}" viewBox="0 0 34 34" role="img" aria-label="IPE ${v} de 100">`
    + '<circle cx="17" cy="17" r="14" fill="none" stroke="#f1f3f2" stroke-width="4.5"/>'
    + `<circle cx="17" cy="17" r="14" fill="none" stroke="${color}" stroke-width="4.5" stroke-linecap="round" stroke-dasharray="${largo} 88" transform="rotate(-90 17 17)"/>`
    + '</svg>';
}

// Celda de IPE: anillo + numero + banda.
function celdaIpe(ipe) {
  if (!ipe) return '—';
  return `<span class="ipe-celda">${anilloIpe(ipe.valor, ipe.banda)}`
    + `<span class="val"><b>${esc(ipe.valor)}</b><span class="banda-${esc(ipe.banda)}">${esc(ipe.banda_texto)}</span></span></span>`;
}

// Medidor de media luna (0 a 100) con el tramo de cada banda tintado al fondo.
function medidorIpe(valor, banda, textoBanda) {
  const v = Math.max(0, Math.min(100, Number(valor) || 0));
  const color = IPE_COLOR[banda] || '#8a929b';
  const ang = Math.PI * (1 - v / 100);
  const x = (120 + 100 * Math.cos(ang)).toFixed(1);
  const y = (112 - 100 * Math.sin(ang)).toFixed(1);
  const arco = 'M20 112 A100 100 0 0 1 220 112';
  const clase = IPE_CLASE[banda] || 'status status-info';
  return `<div class="medidor"><svg viewBox="0 0 240 132" role="img" aria-label="Índice ${v} de 100">`
    + `<path d="${arco}" fill="none" stroke="#fbe3e0" stroke-width="14" stroke-dasharray="155 400"/>`
    + `<path d="${arco}" fill="none" stroke="#fbebd0" stroke-width="14" stroke-dasharray="0 159 92 400"/>`
    + `<path d="${arco}" fill="none" stroke="#dcf0e5" stroke-width="14" stroke-dasharray="0 253 62 400"/>`
    + (v > 0 ? `<path d="${arco}" fill="none" stroke="${color}" stroke-width="14" stroke-linecap="round" stroke-dasharray="${(314.16 * v / 100).toFixed(1)} 400"/>` : '')
    + `<circle cx="${x}" cy="${y}" r="9" fill="#fff" stroke="${color}" stroke-width="4"/></svg>`
    + `<div class="cifra"><b>${v}<small>/100</small></b>`
    + (textoBanda ? `<span class="${clase}">${esc(textoBanda)}</span>` : '') + '</div></div>';
}

async function apiFetch(url, opciones = {}) {
  const esFormulario = opciones.body instanceof FormData;
  const headers = cabecerasApi(Object.assign(
    esFormulario ? {} : { 'Content-Type': 'application/json' },
    opciones.headers || {}
  ));
  const r = await fetch(url, Object.assign({}, opciones, { headers, credentials: 'same-origin' }));
  if (r.status === 401) {
    const previo = getUsuario();
    sessionStorage.removeItem('usuario');
    window.location.href = paginaDeAcceso(previo && previo.rol);
    throw new Error('No autenticado');
  }
  const cuerpo = await r.json();
  if (r.status === 403 && cuerpo.cambio_clave_obligatorio) {
    const u = getUsuario();
    if (u) { u.debe_cambiar_clave = true; sessionStorage.setItem('usuario', JSON.stringify(u)); }
    window.location.href = 'cuenta.html?obligatorio=1';
    throw new Error('Cambio de contraseña obligatorio');
  }
  return cuerpo;
}

async function cerrarSesion(ev) {
  if (ev) ev.preventDefault();
  const previo = getUsuario();
  try {
    await fetch('/logout', { method: 'POST', headers: cabecerasApi(), credentials: 'same-origin' });
  } catch (e) { /* aunque falle la red, se limpia la sesion local */ }
  sessionStorage.removeItem('usuario');
  window.location.href = paginaDeAcceso(previo && previo.rol);
}

function claseEstado(estado) {
  if (estado === 'aprobado') return 'status status-ok';
  if (estado === 'evaluacion') return 'status status-info';
  if (estado === 'aprobado_interno') return 'status status-violet';
  if (estado === 'pendiente') return 'status status-warn';
  if (estado === 'rechazado') return 'status status-bad';
  return 'status status-info';
}

// HU-07: el cliente y el publico ven solo tres estados (Aprobado, En
// evaluacion, Pendiente de subsanacion). La consultora ve ademas el paso
// interno "Aprobado internamente".
const ESTADO_PUBLICO = {
  pendiente: 'Pendiente de subsanación',
  aprobado_interno: 'Pendiente de subsanación',
  evaluacion: 'En evaluación',
  aprobado: 'Aprobado',
  rechazado: 'Rechazado',
};

function textoEstado(estado) {
  const u = getUsuario();
  const interno = u && (u.rol === 'consultor' || u.rol === 'jefe');
  if (interno && estado === 'aprobado_interno') return 'Aprobado internamente';
  return ESTADO_PUBLICO[estado] || esc(estado);
}

function fichaTier(cat) {
  const t = { 'I': 'Bajo impacto', 'II': 'Impacto moderado', 'III': 'Alto impacto' };
  return `<span class="tier"><b>${esc(cat)}</b> ${t[cat] || ''}</span>`;
}

// Iniciales para el avatar: "Mariela Quintero" -> "MQ".
function iniciales(nombre) {
  const partes = String(nombre || '').trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  const primera = partes[0][0] || '';
  const ultima = partes.length > 1 ? partes[partes.length - 1][0] : (partes[0][1] || '');
  return (primera + ultima).toUpperCase();
}

function pintarTopbar() {
  const u = getUsuario();
  const who = document.querySelector('.who');
  if (u && who) {
    // Menu de usuario: avatar con iniciales, nombre y rol; abre "Mi perfil" y "Salir".
    const rolTexto = ROL_TEXTO[u.rol] || u.rol;
    who.innerHTML = `
      <div class="menu-usuario">
        <button type="button" class="menu-usuario-boton" aria-haspopup="menu" aria-expanded="false" aria-controls="menu-usuario-lista">
          <span class="avatar">${esc(iniciales(u.nombre || u.email))}</span>
          <span class="menu-usuario-texto"><b>${esc(u.nombre || u.email)}</b><span>${esc(rolTexto)}</span></span>
          <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
        </button>
        <div class="menu-usuario-lista" id="menu-usuario-lista" role="menu" hidden>
          <div class="menu-usuario-cabecera"><b>${esc(u.nombre || '')}</b><span>${esc(u.email)}</span></div>
          <a href="cuenta.html" role="menuitem">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>
            Mi perfil</a>
          <a href="login.html" id="link-salir" role="menuitem">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3"/><path d="M14 17l5-5-5-5M19 12H9"/></svg>
            Salir</a>
        </div>
      </div>`;
    const boton = who.querySelector('.menu-usuario-boton');
    const lista = who.querySelector('.menu-usuario-lista');
    const abrir = (si) => {
      lista.hidden = !si;
      boton.setAttribute('aria-expanded', si ? 'true' : 'false');
      if (si) lista.querySelector('a').focus();
    };
    boton.addEventListener('click', () => abrir(lista.hidden));
    document.addEventListener('click', (e) => { if (!who.contains(e.target)) abrir(false); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !lista.hidden) { abrir(false); boton.focus(); } });
    who.querySelector('#link-salir').addEventListener('click', cerrarSesion);
  }
  pintarRail();
  if (u && u.rol !== 'admin') {
    agregarBotonBuscar();
    iniciarPaleta();
  }
  revisarTerminos();
}

// ============== NOTIFICACIONES TOAST ==============
function mostrarToast(mensaje, tipo = 'exito') {
  let container = document.getElementById('toast-container');
  
  // Si no existe el contenedor, lo creamos
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${tipo}`;
  
  const icono = tipo === 'exito'
    ? '<path d="M5 12l5 5 9-10"/>'
    : '<path d="M12 7v6M12 17h.01"/>';
  toast.setAttribute('role', 'status');
  toast.innerHTML = '<span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" '
    + `stroke-linecap="round">${icono}</svg></span> <span>${esc(mensaje)}</span>`;
  
  container.appendChild(toast);

  // Desaparece después de 3 segundos
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ============== HU-12: menu lateral en el celular ==============
// En pantallas de 820 px o menos el menu se oculta y se abre con el boton
// "Menu" de la barra de arriba. Se cierra con el fondo, con Escape o al
// elegir una opcion.
function iniciarMenuMovil() {
  const rail = document.querySelector('.rail');
  const topbar = document.querySelector('.topbar');
  if (!rail || !topbar || document.querySelector('.btn-menu')) return;
  rail.id = rail.id || 'menu-lateral';

  const boton = document.createElement('button');
  boton.type = 'button';
  boton.className = 'btn-menu';
  boton.setAttribute('aria-controls', rail.id);
  boton.setAttribute('aria-expanded', 'false');
  boton.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
    + '<path d="M4 7h16M4 12h16M4 17h16"/></svg> Menú';
  topbar.insertBefore(boton, topbar.firstChild);

  const fondo = document.createElement('div');
  fondo.className = 'menu-fondo';
  document.body.appendChild(fondo);

  const abrir = (si) => {
    document.body.classList.toggle('menu-abierto', si);
    boton.setAttribute('aria-expanded', si ? 'true' : 'false');
  };
  boton.addEventListener('click', () => abrir(!document.body.classList.contains('menu-abierto')));
  fondo.addEventListener('click', () => abrir(false));
  rail.querySelectorAll('a').forEach(a => a.addEventListener('click', () => abrir(false)));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') abrir(false); });
  window.addEventListener('resize', () => { if (window.innerWidth > 820) abrir(false); });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciarMenuMovil);
} else {
  iniciarMenuMovil();
}

// ============== MENU LATERAL, MARCA DE LA EMPRESA ==============
// El menu se arma segun el rol (asi todas las pantallas comparten el mismo y no se
// desfasan) y muestra el nombre y el logo de la consultora a la que pertenece el usuario.
const ICONOS = {
  panel: '<rect x="3.5" y="3.5" width="7" height="7"/><rect x="13.5" y="3.5" width="7" height="7"/><rect x="3.5" y="13.5" width="7" height="7"/><rect x="13.5" y="13.5" width="7" height="7"/>',
  carpeta: '<path d="M4 6.5a1.5 1.5 0 0 1 1.5-1.5H10l2 2.5h6.5A1.5 1.5 0 0 1 20 9v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18z"/>',
  nuevo: '<path d="M6 3.5h9l4 4V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path d="M12 11v6M9 14h6"/>',
  historial: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  equipo: '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><circle cx="17" cy="9.5" r="2.4"/><path d="M15.8 14.2c2.3.2 4 1.8 4.6 4.8"/>',
  empresa: '<path d="M4 20V6.5L12 3l8 3.5V20"/><path d="M9 20v-5h6v5M8 9.5h.01M12 9.5h.01M16 9.5h.01"/>',
  buscar: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M19.5 19.5 15 15"/>',
  ayuda: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.2c-.8.5-1.2 1-1.2 1.9M12 16.8h.01"/>',
  plataforma: '<rect x="3.5" y="4" width="17" height="6" rx="1.5"/><rect x="3.5" y="14" width="17" height="6" rx="1.5"/><path d="M7 7h.01M7 17h.01"/>',
  estado: '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
  persona: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
};

function itemsDeMenu(rol) {
  const panel = { href: 'dashboard.html', icono: 'panel', texto: 'Panel' };
  const ayuda = { href: 'ayuda.html', icono: 'ayuda', texto: 'Ayuda' };
  if (rol === 'admin') {
    return [{ href: '/admin/panel', icono: 'plataforma', texto: 'Plataforma' },
            { href: 'estado.html', icono: 'estado', texto: 'Estado del servicio' }, ayuda];
  }
  if (rol === 'promotor') {
    return [panel, { href: 'expedientes.html', icono: 'carpeta', texto: 'Mis expedientes' },
            { href: 'consulta-publica.html', icono: 'buscar', texto: 'Consulta pública' }, ayuda];
  }
  const items = [panel,
    { href: 'expedientes.html', icono: 'carpeta', texto: rol === 'jefe' ? 'Expedientes' : 'Mis expedientes' },
    { href: 'expediente-nuevo.html', icono: 'nuevo', texto: 'Nuevo expediente' },
    { href: 'historial.html', icono: 'historial', texto: 'Historial' }];
  if (rol === 'jefe') {
    items.push({ href: 'equipo.html', icono: 'equipo', texto: 'Equipo' },
               { href: 'empresa.html', icono: 'empresa', texto: 'Mi consultora' });
  }
  items.push({ href: 'consulta-publica.html', icono: 'buscar', texto: 'Consulta pública' }, ayuda);
  return items;
}

// Las pantallas de detalle pertenecen a "Expedientes".
const PAGINA_PADRE = { 'expediente-detalle.html': 'expedientes.html', 'panel': '/admin/panel' };

function pintarRail() {
  const rail = document.querySelector('.rail');
  const u = getUsuario();
  if (!rail || !u) return;
  const nav = rail.querySelector('nav');
  const pagina = window.location.pathname.split('/').pop() || 'index.html';
  const activa = PAGINA_PADRE[pagina] || pagina;
  if (nav) {
    nav.innerHTML = itemsDeMenu(u.rol).map(i =>
      `<a href="${i.href}"${i.href === activa ? ' class="active" aria-current="page"' : ''}>`
      + `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">${ICONOS[i.icono]}</svg>${esc(i.texto)}</a>`).join('');
  }
  const e = u.empresa;
  const marca = rail.querySelector('.rail-brand');
  if (e && marca) {
    document.documentElement.style.setProperty('--empresa', e.color || '#17805a');
    const sello = e.logo
      ? `<div class="seal seal-logo"><img src="${esc(e.logo)}" alt=""></div>`
      : `<div class="seal seal-iniciales" aria-hidden="true">${esc(iniciales(e.nombre))}</div>`;
    marca.innerHTML = `${sello}<div><b>${esc(e.nombre)}</b><span>Permisos Ambientales</span></div>`;
    marca.classList.add('con-empresa');
  } else if (u.rol === 'admin' && marca) {
    marca.innerHTML = marca.innerHTML.replace('Expedientes ambientales', 'Administración');
  }
  pintarEspacios(rail, u);
}

// Colores de las letras de los "espacios" (vistas guardadas): el mismo nombre, siempre el mismo color.
const COLORES_ESPACIO = ['#7c5ac8', '#2563a8', '#17805a', '#c2410c', '#0e7c86', '#b4261c', '#9a5b00', '#3e4650'];
function colorDe(texto) {
  let h = 0;
  for (const ch of String(texto)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return COLORES_ESPACIO[h % COLORES_ESPACIO.length];
}

// Las vistas guardadas de la persona, como atajos en el menu (abren Expedientes con esa vista).
async function pintarEspacios(rail, u) {
  if (!u || u.rol === 'admin' || !rail.querySelector('nav')) return;
  try {
    const d = await apiFetch('/vistas');
    const vistas = d.vistas || [];
    let cont = rail.querySelector('.rail-espacios');
    if (!vistas.length) { if (cont) cont.remove(); return; }
    if (!cont) {
      cont = document.createElement('div');
      cont.className = 'rail-espacios';
      rail.querySelector('nav').after(cont);
    }
    const actual = new URLSearchParams(window.location.search).get('vista');
    cont.innerHTML = '<h4>Vistas guardadas</h4>' + vistas.map(v =>
      `<a href="expedientes.html?vista=${esc(v.id)}"${String(v.id) === actual ? ' class="activa"' : ''}>`
      + `<span class="espacio-ico" style="background:${colorDe(v.nombre)};">${esc((v.nombre || '?')[0].toUpperCase())}</span>`
      + `<span class="espacio-nombre">${esc(v.nombre)}</span></a>`).join('');
  } catch (e) { /* sin vistas: el menu queda como esta */ }
}

// ============== VENTANAS (confirmaciones, avisos que se muestran una vez) ==============
// abrirModal({ titulo, html, acciones: [{ texto, clase, alHacerClic }], cerrable })
// Devuelve { cerrar, el }. Escape cierra si es cerrable; el foco queda dentro mientras esta abierta.
// Si alHacerClic devuelve false, la ventana no se cierra.
function abrirModal({ titulo, html, acciones = [], cerrable = true }) {
  const previo = document.activeElement;
  const fondo = document.createElement('div');
  fondo.className = 'modal-fondo';
  fondo.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-titulo">
      <h3 id="modal-titulo">${esc(titulo)}</h3><div class="modal-cuerpo">${html || ''}</div>
      <div class="modal-acciones"></div></div>`;
  const caja = fondo.querySelector('.modal');
  const barra = fondo.querySelector('.modal-acciones');
  const cerrar = () => {
    document.removeEventListener('keydown', teclas, true);
    fondo.remove();
    if (previo && previo.focus) previo.focus();
  };
  acciones.forEach(a => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = a.clase || 'btn btn-ghost';
    b.textContent = a.texto;
    b.addEventListener('click', async () => {
      if (a.alHacerClic) {
        const resultado = await a.alHacerClic({ cerrar, el: caja });
        if (resultado === false) return;
      }
      cerrar();
    });
    barra.appendChild(b);
  });
  function teclas(ev) {
    if (ev.key === 'Escape' && cerrable) { ev.stopPropagation(); cerrar(); return; }
    if (ev.key !== 'Tab') return;
    const foco = caja.querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (!foco.length) return;
    const primero = foco[0], ultimo = foco[foco.length - 1];
    if (ev.shiftKey && document.activeElement === primero) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
  }
  document.addEventListener('keydown', teclas, true);
  if (cerrable) fondo.addEventListener('mousedown', (ev) => { if (ev.target === fondo) cerrar(); });
  document.body.appendChild(fondo);
  (caja.querySelector('input, select, textarea') || barra.querySelector('button') || caja).focus();
  return { cerrar, el: caja };
}

// Confirmacion propia (en lugar de confirm()): devuelve una promesa con true o false.
function confirmar(titulo, mensaje, textoBoton = 'Confirmar', peligro = false) {
  return new Promise(resolver => {
    abrirModal({
      titulo, html: `<p>${esc(mensaje)}</p>`,
      acciones: [
        { texto: 'Cancelar', clase: 'btn btn-ghost', alHacerClic: () => resolver(false) },
        { texto: textoBoton, clase: peligro ? 'btn btn-peligro' : 'btn btn-brass', alHacerClic: () => resolver(true) },
      ],
    });
  });
}

// Copia texto al portapapeles y lo avisa.
async function copiarTexto(texto, aviso = 'Copiado.') {
  try { await navigator.clipboard.writeText(texto); mostrarToast(aviso, 'exito'); }
  catch (e) { mostrarToast('No se pudo copiar; selecciónelo y copie a mano.', 'error'); }
}

// ============== TERMINOS Y POLITICA DE PRIVACIDAD ==============
// Quien aun no los acepto (cuentas anteriores) los ve una vez al entrar.
async function revisarTerminos() {
  const u = getUsuario();
  if (!u || u.debe_cambiar_clave || sessionStorage.getItem('terminos_ok') === '1') return;
  try {
    const s = await apiFetch('/sesion');
    if (!s.terminos_pendientes) { sessionStorage.setItem('terminos_ok', '1'); return; }
    abrirModal({
      titulo: 'Términos y privacidad',
      html: '<p>Para seguir usando la plataforma, confirme que leyó y acepta los '
        + '<a href="terminos.html" target="_blank" rel="noopener">términos de uso</a> y la '
        + '<a href="privacidad.html" target="_blank" rel="noopener">política de privacidad</a>.</p>',
      cerrable: false,
      acciones: [{
        texto: 'Acepto', clase: 'btn btn-brass',
        alHacerClic: async () => {
          const r = await apiFetch('/cuenta/terminos', { method: 'POST', body: '{}' });
          if (!r.ok) { mostrarToast(r.mensaje || 'No se pudo registrar.', 'error'); return false; }
          sessionStorage.setItem('terminos_ok', '1');
        },
      }],
    });
  } catch (e) { /* sin red: se vuelve a intentar en la proxima pantalla */ }
}

// ============== BUSQUEDA GLOBAL (Ctrl+K) ==============
function agregarBotonBuscar() {
  const topbar = document.querySelector('.topbar');
  if (!topbar || topbar.querySelector('.btn-buscar')) return;
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn-buscar';
  b.setAttribute('aria-label', 'Buscar en la plataforma (Control K)');
  b.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
    + `${ICONOS.buscar}</svg><span>Buscar</span><kbd>Ctrl K</kbd>`;
  b.addEventListener('click', abrirPaleta);
  const who = topbar.querySelector('.who');
  topbar.insertBefore(b, who || null);
}

let paletaIniciada = false;
function iniciarPaleta() {
  if (paletaIniciada) return;
  paletaIniciada = true;
  document.addEventListener('keydown', (ev) => {
    const escribiendo = /^(INPUT|TEXTAREA|SELECT)$/.test((ev.target.tagName || '')) || ev.target.isContentEditable;
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); abrirPaleta(); }
    else if (ev.key === '/' && !escribiendo && !document.querySelector('.paleta-fondo')) { ev.preventDefault(); abrirPaleta(); }
  });
}

function abrirPaleta() {
  if (document.querySelector('.paleta-fondo')) return;
  const u = getUsuario();
  if (!u) return;
  const previo = document.activeElement;
  const paginas = itemsDeMenu(u.rol).map(i => ({ grupo: 'Ir a', texto: i.texto, href: i.href, icono: i.icono }));
  const acciones = [];
  if (u.rol !== 'promotor') {
    acciones.push({ grupo: 'Acciones', texto: 'Crear un expediente', href: 'expediente-nuevo.html', icono: 'nuevo' });
  }
  acciones.push({ grupo: 'Acciones', texto: 'Descargar la cartera en Excel', href: '/exportar/cartera.xlsx', icono: 'carpeta' });
  acciones.push({ grupo: 'Acciones', texto: 'Mi perfil y seguridad', href: 'cuenta.html', icono: 'persona' });
  const comandos = [...acciones, ...paginas];

  const fondo = document.createElement('div');
  fondo.className = 'paleta-fondo';
  fondo.innerHTML = `<div class="paleta" role="dialog" aria-modal="true" aria-label="Buscar en la plataforma">
      <div class="paleta-campo">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">${ICONOS.buscar}</svg>
        <input type="text" id="paleta-q" role="combobox" aria-expanded="true" aria-controls="paleta-lista" aria-autocomplete="list"
               placeholder="Código, proyecto, cliente o una acción…" autocomplete="off" maxlength="80">
        <kbd>Esc</kbd>
      </div>
      <ul id="paleta-lista" role="listbox"></ul>
      <div class="paleta-pie"><span><kbd>↑</kbd><kbd>↓</kbd> moverse</span><span><kbd>Enter</kbd> abrir</span></div>
    </div>`;
  document.body.appendChild(fondo);
  const campo = fondo.querySelector('#paleta-q');
  const lista = fondo.querySelector('#paleta-lista');
  let filas = [];
  let sel = 0;
  let temporizador = null;
  let consulta = 0;

  const cerrar = () => { document.removeEventListener('keydown', teclas, true); fondo.remove(); if (previo && previo.focus) previo.focus(); };
  const ir = (f) => { if (!f) return; cerrar(); window.location.href = f.href; };

  function pintar() {
    let grupo = '';
    lista.innerHTML = filas.length ? filas.map((f, i) => {
      const cab = f.grupo !== grupo ? `<li class="paleta-grupo" role="presentation">${esc(f.grupo)}</li>` : '';
      grupo = f.grupo;
      return `${cab}<li role="option" id="paleta-op-${i}" data-i="${i}" aria-selected="${i === sel}" class="${i === sel ? 'sel' : ''}">`
        + `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">${ICONOS[f.icono] || ICONOS.carpeta}</svg>`
        + `<span class="paleta-texto"><b>${esc(f.texto)}</b>${f.detalle ? `<small>${esc(f.detalle)}</small>` : ''}</span></li>`;
    }).join('') : '<li class="paleta-vacio" role="presentation">Sin resultados.</li>';
    campo.setAttribute('aria-activedescendant', filas.length ? `paleta-op-${sel}` : '');
    const activo = lista.querySelector('li.sel');
    if (activo) activo.scrollIntoView({ block: 'nearest' });
  }

  function filtrarComandos(q) {
    const n = q.toLowerCase();
    return comandos.filter(c => !n || c.texto.toLowerCase().includes(n));
  }

  async function buscar() {
    const q = campo.value.trim();
    const mio = ++consulta;
    let encontrados = [];
    if (q.length >= 2) {
      try {
        const d = await apiFetch('/buscar?q=' + encodeURIComponent(q));
        if (mio !== consulta) return;  // llego una busqueda mas nueva
        encontrados = (d.expedientes || []).map(e => ({
          grupo: 'Expedientes', texto: `${e.codigo} · ${e.proyecto}`, detalle: `${e.promotor} — ${e.estado}`,
          href: 'expediente-detalle.html?codigo=' + encodeURIComponent(e.codigo), icono: 'carpeta' }));
        encontrados.push(...(d.personas || []).map(p => ({
          grupo: 'Equipo', texto: p.nombre, detalle: p.email, href: 'equipo.html', icono: 'equipo' })));
      } catch (e) { /* sin red: quedan los comandos */ }
    }
    filas = [...encontrados, ...filtrarComandos(q)];
    sel = 0;
    pintar();
  }

  function teclas(ev) {
    if (ev.key === 'Escape') { ev.stopPropagation(); cerrar(); }
    else if (ev.key === 'ArrowDown') { ev.preventDefault(); sel = Math.min(filas.length - 1, sel + 1); pintar(); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); sel = Math.max(0, sel - 1); pintar(); }
    else if (ev.key === 'Enter') { ev.preventDefault(); ir(filas[sel]); }
    else if (ev.key === 'Tab') { ev.preventDefault(); }
  }
  document.addEventListener('keydown', teclas, true);
  fondo.addEventListener('mousedown', (ev) => { if (ev.target === fondo) cerrar(); });
  lista.addEventListener('click', (ev) => { const li = ev.target.closest('li[data-i]'); if (li) ir(filas[Number(li.dataset.i)]); });
  lista.addEventListener('mousemove', (ev) => {
    const li = ev.target.closest('li[data-i]');
    if (li && Number(li.dataset.i) !== sel) { sel = Number(li.dataset.i); pintar(); }
  });
  campo.addEventListener('input', () => { clearTimeout(temporizador); temporizador = setTimeout(buscar, 180); });
  filas = comandos;
  pintar();
  campo.focus();
}
