// Recuperar la contraseña con un código de recuperación (sin correo electrónico).
const form = document.getElementById('formRecuperar');
const btn = document.getElementById('submitBtn');
const msg = document.getElementById('message');

function aviso(texto, ok) {
  msg.textContent = texto;
  msg.className = 'doc-msg show ' + (ok ? 'ok' : 'error');
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('email').value.trim();
  const codigo = document.getElementById('codigo').value.trim();
  const password = document.getElementById('password').value;
  if (password !== document.getElementById('password2').value) {
    aviso('Las contraseñas no coinciden.', false);
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Verificando...';
  msg.className = 'doc-msg';
  try {
    const r = await fetch('/recuperar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, codigo, password })
    });
    const d = await r.json();
    aviso(d.mensaje || (d.ok ? 'Contraseña actualizada.' : 'No se pudo cambiar la contraseña.'), d.ok === true);
    if (d.ok) setTimeout(() => window.location.href = 'login.html', 1600);
  } catch (err) {
    aviso('No se pudo conectar con el servidor.', false);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Cambiar contraseña';
  }
});
