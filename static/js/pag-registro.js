// Registro solo por invitación: el enlace trae ?invitacion=<token>.
const token = new URLSearchParams(window.location.search).get('invitacion') || '';
const formulario = document.getElementById('formRegistro');
const mensaje = document.getElementById('mensaje');
const lede = document.getElementById('lede');

function aviso(texto, ok) {
  mensaje.className = 'doc-msg show ' + (ok ? 'ok' : 'error');
  mensaje.textContent = texto;
}

function sinInvitacion(texto) {
  lede.textContent = texto;
  document.getElementById('sin-invitacion').hidden = false;
}

async function validarInvitacion() {
  if (!token) { sinInvitacion('No se encontró una invitación.'); return; }
  try {
    const r = await fetch('/invitaciones/validar?token=' + encodeURIComponent(token));
    const d = await r.json();
    if (!r.ok || !d.ok) { sinInvitacion(d.mensaje || 'La invitación no es válida, ya se usó o venció.'); return; }
    const rol = d.rol === 'jefe' ? 'director de proyectos' : 'consultor ambiental';
    lede.innerHTML = '';
    lede.append('Se une a ');
    const negrita = document.createElement('b');
    negrita.textContent = d.empresa;
    lede.append(negrita, ` como ${rol}.`);
    if (d.email) {
      const campo = document.getElementById('email');
      campo.value = d.email;
      campo.readOnly = true;
    }
    formulario.hidden = false;
    document.getElementById('nombre').focus();
  } catch (e) {
    sinInvitacion('No se pudo comprobar la invitación. Revise su conexión e intente de nuevo.');
  }
}

formulario.addEventListener('submit', async (e) => {
  e.preventDefault();
  mensaje.className = 'doc-msg';
  mensaje.textContent = '';

  const nombre = document.getElementById('nombre').value.trim();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const password2 = document.getElementById('password2').value;
  const acepto = document.getElementById('terminos').checked;

  if (password !== password2) { aviso('Las contraseñas no coinciden.', false); return; }
  if (!acepto) { aviso('Debe aceptar los términos y la política de privacidad.', false); return; }

  try {
    const resp = await fetch('/registro', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, email, password, invitacion: token, acepto_terminos: true })
    });
    const data = await resp.json();
    if (data.ok) {
      aviso('Cuenta creada. Redirigiendo para iniciar sesión…', true);
      setTimeout(() => window.location.href = 'login.html', 1400);
    } else {
      aviso(data.mensaje || 'No se pudo crear la cuenta.', false);
    }
  } catch (err) {
    aviso('Error de conexión con el servidor.', false);
  }
});

validarInvitacion();
