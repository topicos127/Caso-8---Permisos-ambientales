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