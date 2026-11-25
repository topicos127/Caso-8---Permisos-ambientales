const usuario = requireAuth();
if (usuario) {
  pintarTopbar();
  if (esPromotor()) {
    document.querySelectorAll('a[href="expediente-nuevo.html"], #nav-historial').forEach(a => { a.style.display = 'none'; });
  }

  function pintarCabecera(nombre, email, rol) {
    document.getElementById('perfil-avatar').textContent = iniciales(nombre || email);
    document.getElementById('perfil-nombre').textContent = nombre || email;
    document.getElementById('perfil-rol').textContent = ROL_TEXTO[rol] || rol;
    document.getElementById('perfil-correo').textContent = email;
  }
  pintarCabecera(usuario.nombre, usuario.email, usuario.rol);

  const obligatorio = usuario.debe_cambiar_clave === true;
  if (obligatorio) {
    document.getElementById('aviso-obligatorio').style.display = 'block';
    // Sin la contraseña nueva no hay nada más que hacer: se oculta el menú.
    document.querySelectorAll('.rail nav a').forEach(a => { a.style.display = 'none'; });
  }

  // Cifras reales y preferencia de aviso (15, 30 o 45 días).
  if (!obligatorio) {
    const pintarOpciones = (actual, opciones) => {
      const cont = document.getElementById('opciones-aviso');
      cont.innerHTML = opciones.map(d =>
        `<button type="button" role="radio" aria-checked="${d === actual}" data-dias="${d}"
           class="${d === actual ? 'activo' : ''}"><b>${d}</b><span>días antes</span></button>`).join('');
      cont.querySelectorAll('button').forEach(b => b.addEventListener('click', async () => {
        const dias = Number(b.dataset.dias);
        const r = await apiFetch('/perfil', { method: 'POST', body: JSON.stringify({ aviso_vencimiento_dias: dias }) });
        const m = document.getElementById('mensaje-aviso');
        m.className = 'doc-msg show ' + (r.ok ? 'ok' : 'error');
        m.textContent = r.mensaje || (r.ok ? 'Preferencia guardada.' : 'No se pudo guardar.');
        if (r.ok) { pintarOpciones(dias, opciones); mostrarToast('Preferencia guardada.', 'exito'); }
      }));
    };
    apiFetch('/perfil').then(p => {
      pintarCabecera(p.nombre, p.email, p.rol);
      // El nombre puede haber cambiado desde el inicio de sesión: se actualiza la barra.
      if (p.nombre && p.nombre !== usuario.nombre) {
        usuario.nombre = p.nombre;
        sessionStorage.setItem('usuario', JSON.stringify(usuario));
        pintarTopbar();
      }
      if (p.empresa) {
        document.getElementById('perfil-empresa').textContent = p.empresa.nombre;
        document.getElementById('perfil-empresa-caja').hidden = false;
      }
      if (p.miembro_desde) {
        document.getElementById('perfil-desde').textContent = p.miembro_desde;
        document.getElementById('perfil-desde-caja').hidden = false;
      }
      if (p.cifras) {
        document.getElementById('cifra-expedientes').textContent = p.cifras.expedientes;
        document.getElementById('cifra-tramite').textContent = p.cifras.en_tramite;
        document.getElementById('cifra-aprobados').textContent = p.cifras.aprobados;
        const alerta = document.getElementById('cifra-alerta');
        alerta.textContent = p.cifras.plazos_en_alerta;
        alerta.classList.toggle('alerta', p.cifras.plazos_en_alerta > 0);
        document.getElementById('perfil-cifras').hidden = false;
      }
      document.getElementById('panel-aviso').style.display = 'block';
      pintarOpciones(p.aviso_vencimiento_dias, p.opciones_aviso || [15, 30, 45]);
    }).catch(console.error);
  }

  document.getElementById('formClave').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = document.getElementById('mensaje');
    const actual = document.getElementById('actual').value;
    const nueva = document.getElementById('nueva').value;
    if (nueva !== document.getElementById('nueva2').value) {
      m.className = 'doc-msg show error';
      m.textContent = 'Las contraseñas nuevas no coinciden.';
      return;
    }
    const r = await apiFetch('/cuenta/contrasena', { method: 'POST', body: JSON.stringify({ actual, nueva }) });
    m.className = 'doc-msg show ' + (r.ok ? 'ok' : 'error');
    m.textContent = r.ok ? 'Contraseña actualizada.' : (r.mensaje || 'No se pudo cambiar la contraseña.');
    if (r.ok) {
      document.getElementById('formClave').reset();
      mostrarToast('Contraseña actualizada.', 'exito');
      if (obligatorio) {
        usuario.debe_cambiar_clave = false;
        sessionStorage.setItem('usuario', JSON.stringify(usuario));
        m.textContent = 'Contraseña actualizada. Entrando al sistema...';
        setTimeout(() => window.location.href = 'dashboard.html', 1200);
      }
    }
  });
}
