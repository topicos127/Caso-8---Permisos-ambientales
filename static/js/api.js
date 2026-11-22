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
  resuelto:   ['status status-info', 'Resuelto'],
};

function etiquetaPlazo(plazo) {
  if (!plazo) return '—';
  const [clase, texto] = PLAZO_ETIQUETA[plazo.estado_semaforo] || ['status status-info', '—'];
  const dias = plazo.estado_semaforo === 'resuelto' || plazo.dias_restantes_legales == null
    ? '' : ` · ${esc(plazo.dias_restantes_legales)} d`;
  return `<span class="${clase}">${texto}${dias}</span>`;
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
  return r.json();
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
  if (estado === 'aprobado_interno') return 'status status-warn';
  if (estado === 'pendiente') return 'status status-bad';
  return 'status status-info';
}

function textoEstado(estado) {
  if (estado === 'aprobado') return 'Aprobado por MiAmbiente';
  if (estado === 'evaluacion') return 'En evaluación (MiAmbiente)';
  if (estado === 'aprobado_interno') return 'Aprobado internamente';
  if (estado === 'pendiente') return 'Pendiente de documentos';
  return esc(estado);
}

function fichaTier(cat) {
  const t = { 'I': 'Bajo impacto', 'II': 'Impacto moderado', 'III': 'Alto impacto' };
  return `<span class="tier"><b>${esc(cat)}</b> ${t[cat] || ''}</span>`;
}

function pintarTopbar() {
  const u = getUsuario();
  const who = document.querySelector('.who');
  if (u && who) {
    const rolTexto = ROL_TEXTO[u.rol] || u.rol;
    who.innerHTML = `<span class="tag">${rolTexto}</span> ${esc(u.nombre || u.email)} <a href="login.html" id="link-salir">Salir</a>`;
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
  
  const icon = tipo === 'exito' ? '✅' : '⚠️';
  toast.innerHTML = `<span>${icon}</span> <span>${esc(mensaje)}</span>`;
  
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

