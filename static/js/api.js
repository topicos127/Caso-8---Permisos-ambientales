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
  if (!u || !u.email) { window.location.href = 'login.html'; return null; }
  // Sprint 9: con una contraseña temporal, solo "Mi cuenta" está disponible.
  if (u.debe_cambiar_clave && !window.location.pathname.endsWith('cuenta.html')) {
    window.location.href = 'cuenta.html?obligatorio=1';
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

// HU-13: el jefe de la consultora ve todo y es quien aprueba internamente.
function esJefe() {
  const u = getUsuario();
  return u && u.rol === 'jefe';
}

const ROL_TEXTO = { promotor: 'Promotor', consultor: 'Consultor', jefe: 'Jefe' };

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
    sessionStorage.removeItem('usuario');
    window.location.href = 'login.html';
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
  try {
    await fetch('/logout', { method: 'POST', headers: cabecerasApi(), credentials: 'same-origin' });
  } catch (e) { /* aunque falle la red, se limpia la sesion local */ }
  sessionStorage.removeItem('usuario');
  window.location.href = 'login.html';
}

function claseEstado(estado) {
  if (estado === 'aprobado') return 'status status-ok';
  if (estado === 'evaluacion') return 'status status-info';
  if (estado === 'aprobado_interno') return 'status status-violet';
  if (estado === 'pendiente') return 'status status-warn';
  if (estado === 'rechazado') return 'status status-bad';
  return 'status status-info';
}

// HU-07: el promotor y el publico ven solo tres estados (Aprobado, En
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
  if (esPromotor()) {
    document.querySelectorAll('a[href="expediente-nuevo.html"], #nav-historial').forEach(a => {
      a.style.display = 'none';
    });
  }
  // HU-15: solo el jefe gestiona el equipo de consultores.
  if (esJefe()) {
    document.querySelectorAll('#nav-equipo').forEach(a => { a.style.display = ''; });
  }
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

