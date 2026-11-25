// Si ya hay sesión, redirigir directo a la pantalla de inicio de su rol.
function destinoDe(rol, cambiarClave) {
  if (cambiarClave) return 'cuenta.html?obligatorio=1';
  return rol === 'admin' ? 'plataforma.html' : 'dashboard.html';
}

try {
  const u = JSON.parse(sessionStorage.getItem('usuario') || 'null');
  if (u && u.email) {
    window.location.href = destinoDe(u.rol, false);
  }
} catch (e) { /* ignorar */ }

const form = document.getElementById('loginForm');
const btn = document.getElementById('submitBtn');
const msg = document.getElementById('message');
const campoCodigo = document.getElementById('campo-codigo');
const entradaCodigo = document.getElementById('codigo');

function showMessage(text, ok) {
  msg.textContent = text;
  msg.className = 'doc-msg show ' + (ok ? 'ok' : 'error');
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const cuerpo = { email, password };
  if (!campoCodigo.hidden) cuerpo.codigo = entradaCodigo.value.trim();

  btn.disabled = true;
  btn.textContent = 'Verificando...';
  msg.className = 'doc-msg';

  try {
    const response = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo)
    });
    const data = await response.json();

    // Segundo paso: la cuenta tiene verificación en dos pasos.
    if (data.requiere_2fa) {
      campoCodigo.hidden = false;
      entradaCodigo.focus();
      showMessage(data.mensaje, false);
      return;
    }

    showMessage(data.mensaje, data.acceso === true);
    if (data.acceso === true) {
      sessionStorage.removeItem('terminos_ok');
      sessionStorage.setItem('usuario', JSON.stringify({
        email: data.email || email,
        rol: data.rol,
        nombre: data.nombre,
        empresa: data.empresa || null,
        debe_cambiar_clave: data.debe_cambiar_clave === true
      }));
      // Con una contraseña temporal, lo primero es cambiarla.
      setTimeout(() => window.location.href = destinoDe(data.rol, data.debe_cambiar_clave === true), 700);
    }
  } catch (err) {
    showMessage('No se pudo conectar con el servidor.', false);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
});
