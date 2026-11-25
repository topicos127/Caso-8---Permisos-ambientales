  document.getElementById('formRegistro').addEventListener('submit', async (e) => {
    e.preventDefault();
    const m = document.getElementById('mensaje');
    m.className = 'doc-msg';
    m.textContent = '';

    const nombre = document.getElementById('nombre').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const password2 = document.getElementById('password2').value;
    const rol = document.getElementById('tipo').value;

    if (password !== password2) {
      m.className = 'doc-msg show error';
      m.textContent = 'Las contraseñas no coinciden.';
      return;
    }

    try {
      const resp = await fetch('/registro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, email, password, rol })
      });
      
      const data = await resp.json();
      
      if (data.ok) {
        m.className = 'doc-msg show ok';
        m.textContent = 'Usuario registrado correctamente. Redirigiendo al login...';
        setTimeout(() => window.location.href = 'login.html', 1500);
      } else {
        m.className = 'doc-msg show error';
        m.textContent = data.mensaje || 'Error al registrar usuario.';
      }
    } catch (err) {
      m.className = 'doc-msg show error';
      m.textContent = 'Error de conexión con el servidor.';
    }
  });
