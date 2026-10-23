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
  toast.innerHTML = `<span>${icon}</span> <span>${mensaje}</span>`;
  
  container.appendChild(toast);

  // Desaparece después de 3 segundos
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}