// Helpers de API compartidos por las pantallas internas.

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

async function apiFetch(url, opciones = {}) {
  const u = getUsuario();
  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    opciones.headers || {},
    (u && u.email) ? { 'X-Usuario-Email': u.email } : {}
  );
  const r = await fetch(url, Object.assign({}, opciones, { headers }));
  if (r.status === 401) {
    sessionStorage.removeItem('usuario');
    window.location.href = 'login.html';
    throw new Error('No autenticado');
  }
  return r.json();
}

function claseEstado(estado) {
  if (estado === 'aprobado') return 'status status-ok';
  if (estado === 'evaluacion') return 'status status-warn';
  if (estado === 'pendiente') return 'status status-bad';
  return 'status status-info';
}

function textoEstado(estado) {
  if (estado === 'aprobado') return 'Aprobado';
  if (estado === 'evaluacion') return 'En evaluación';
  if (estado === 'pendiente') return 'Pendiente';
  return estado;
}

function fichaTier(cat) {
  const t = { 'I': 'Bajo impacto', 'II': 'Impacto moderado', 'III': 'Alto impacto' };
  return `<span class="tier"><b>${cat}</b> ${t[cat] || ''}</span>`;
}

function pintarTopbar() {
  const u = getUsuario();
  const who = document.querySelector('.who');
  if (u && who) {
    const rolTexto = u.rol === 'promotor' ? 'Promotor' : 'Consultor';
    who.innerHTML = `<span class="tag">${rolTexto}</span> ${u.nombre || u.email} <a href="login.html" onclick="sessionStorage.removeItem('usuario')">Salir</a>`;
  }
  if (esPromotor()) {
    document.querySelectorAll('a[href="expediente-nuevo.html"]').forEach(a => {
      a.style.display = 'none';
    });
  }
}