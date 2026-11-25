// Acceso de la administración de la plataforma (URL propia: /admin).
try {
  const u = JSON.parse(sessionStorage.getItem('usuario') || 'null');
  if (u && u.rol === 'admin') window.location.href = '/admin/panel';
} catch (e) { /* sin sesión */ }

const form = document.getElementById('adminForm');
const btn = document.getElementById('submitBtn');
const msg = document.getElementById('message');
const campoCodigo = document.getElementById('campo-codigo');
const entradaCodigo = document.getElementById('codigo');

function aviso(texto, ok) {
  msg.textContent = texto;
  msg.className = 'doc-msg show ' + (ok ? 'ok' : 'error');
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const cuerpo = {
    email: document.getElementById('email').value.trim(),
    password: document.getElementById('password').value,
  };
  if (!campoCodigo.hidden) cuerpo.codigo = entradaCodigo.value.trim();

  btn.disabled = true;
  btn.textContent = 'Verificando...';
  msg.className = 'doc-msg';
  try {
    const r = await fetch('/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo),
    });
    const d = await r.json();
    if (d.requiere_2fa) {
      campoCodigo.hidden = false;
      entradaCodigo.focus();
      aviso(d.mensaje, false);
      return;
    }
    aviso(d.mensaje, d.acceso === true);
    if (d.acceso === true) {
      sessionStorage.removeItem('terminos_ok');
      sessionStorage.removeItem('tour_ok');
      sessionStorage.setItem('usuario', JSON.stringify({
        email: d.email, rol: d.rol, nombre: d.nombre, empresa: null,
        debe_cambiar_clave: d.debe_cambiar_clave === true,
      }));
      setTimeout(() => {
        window.location.href = d.debe_cambiar_clave === true ? 'cuenta.html?obligatorio=1' : '/admin/panel';
      }, 600);
    }
  } catch (err) {
    aviso('No se pudo conectar con el servidor.', false);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
});
