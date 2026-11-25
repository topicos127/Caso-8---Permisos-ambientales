  // Si ya hay sesión, redirigir directo al dashboard
  try {
    const u = JSON.parse(sessionStorage.getItem('usuario') || 'null');
    if (u && u.email) {
      window.location.href = 'dashboard.html';
    }
  } catch (e) { /* ignorar */ }

  const form = document.getElementById('loginForm');
  const btn = document.getElementById('submitBtn');
  const msg = document.getElementById('message');

  function showMessage(text, ok) {
    msg.textContent = text;
    msg.className = 'doc-msg show ' + (ok ? 'ok' : 'error');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    btn.disabled = true;
    btn.textContent = 'Verificando...';
    msg.className = 'doc-msg';

    try {
      const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      showMessage(data.mensaje, data.acceso === true);

      if (data.acceso === true) {
        sessionStorage.setItem('usuario', JSON.stringify({
          email: data.email || email,
          rol: data.rol,
          nombre: data.nombre,
          debe_cambiar_clave: data.debe_cambiar_clave === true
        }));
        // Sprint 9: con una contraseña temporal, lo primero es cambiarla.
        const destino = data.debe_cambiar_clave === true ? 'cuenta.html?obligatorio=1' : 'dashboard.html';
        setTimeout(() => window.location.href = destino, 900);
      }
    } catch (err) {
      showMessage('No se pudo conectar con el servidor.', false);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Entrar';
    }
  });
