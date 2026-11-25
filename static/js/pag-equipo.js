// HU-16 (equipo de consultores): solo el jefe. El servidor responde 403 a cualquier otro rol.
let consultores = [];

function aviso(texto, ok, extra) {
  const el = document.getElementById('aviso-equipo');
  el.className = 'panel ' + (ok ? 'ok' : 'error');
  el.replaceChildren(document.createTextNode(texto));
  if (extra) el.append(extra);
  el.style.display = 'block';
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function datosDeAcceso(email, temporal) {
  // Igual que la cuenta del promotor: la contraseña temporal se muestra una sola vez.
  const caja = document.createElement('div');
  caja.style.marginTop = '8px';
  const titulo = document.createElement('div');
  titulo.textContent = 'Entrégale estos datos por un canal seguro; se muestran una sola vez:';
  const datos = document.createElement('div');
  datos.id = 'datos-acceso';
  datos.style.cssText = 'margin-top:6px; font-family:var(--mono); word-break:break-all;';
  datos.textContent = `${email} · ${temporal}`;
  caja.append(titulo, datos);
  return caja;
}

function problemaDePassword(p) {
  // Misma politica que el servidor (Sprint 6).
  if (p.length < 8) return 'La contraseña debe tener al menos 8 caracteres.';
  if (!/[0-9]/.test(p)) return 'La contraseña debe incluir al menos un número.';
  if (!/[A-ZÁÉÍÓÚÑ]/.test(p)) return 'La contraseña debe incluir al menos una letra mayúscula.';
  return null;
}

function accionesDe(c) {
  if (c.activo) {
    return `<button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line);"
              data-desactivar="${c.id}">Desactivar</button>`;
  }
  const destinos = consultores.filter(d => d.activo && d.id !== c.id);
  let reasignar = '';
  if (c.expedientes > 0 && destinos.length) {
    reasignar = `
      <select data-destino-de="${c.id}" aria-label="Consultor que recibe los expedientes">
        ${destinos.map(d => `<option value="${d.id}">${esc(d.nombre)}</option>`).join('')}
      </select>
      <button type="button" class="btn btn-brass" data-reasignar="${c.id}">Reasignar</button>`;
  } else if (c.expedientes > 0) {
    reasignar = '<span class="panel-note" style="margin:0;">No hay otro consultor activo para recibir sus expedientes.</span>';
  }
  return `${reasignar}
    <button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line);"
            data-activar="${c.id}">Reactivar</button>`;
}

function render() {
  const tbody = document.getElementById('tabla-equipo');
  if (!consultores.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="sin-etiqueta" data-label="" style="padding:24px; color:var(--ink-faint); text-align:center;">Todavía no hay consultores.</td></tr>';
    return;
  }
  tbody.innerHTML = consultores.map(c => `
    <tr>
      <td data-label="Nombre" style="padding-left:24px;">${esc(c.nombre)}</td>
      <td data-label="Correo">${esc(c.email)}</td>
      <td data-label="Estado" style="white-space:nowrap;">
        <span class="${c.activo ? 'status status-ok' : 'status status-bad'}">${c.activo ? 'Activo' : 'Desactivado'}</span>
      </td>
      <td data-label="Expedientes" style="white-space:nowrap; font-family:var(--mono);">${esc(c.expedientes)}</td>
      <td data-label="Acciones"><div class="acciones">${accionesDe(c)}</div></td>
    </tr>`).join('');
}

async function cargar() {
  const d = await apiFetch('/consultores');
  if (d.error) { aviso(d.error, false); return; }
  consultores = d.consultores || [];
  render();
}

async function enviar(url, cuerpo) {
  const d = await apiFetch(url, { method: 'POST', body: JSON.stringify(cuerpo || {}) });
  if (d.ok) await cargar();
  const extra = d.ok && d.password_temporal ? datosDeAcceso(d.email, d.password_temporal) : null;
  aviso(d.mensaje || d.error || 'Listo.', !!d.ok, extra);
  return d;
}

const usuario = requireAuth();
if (usuario) {
  pintarTopbar();
  if (!esJefe()) {
    window.location.href = 'expedientes.html';
  } else {
    document.getElementById('form-alta').addEventListener('submit', async (e) => {
      e.preventDefault();
      const nombre = document.getElementById('alta-nombre').value.trim();
      const email = document.getElementById('alta-email').value.trim();
      const password = document.getElementById('alta-password').value;
      const password2 = document.getElementById('alta-password2').value;
      if (!nombre || !email) { aviso('Nombre y correo son obligatorios.', false); return; }
      const cuerpo = { nombre, email };
      if (password || password2) {
        if (password !== password2) { aviso('Las contraseñas no coinciden.', false); return; }
        const problema = problemaDePassword(password);
        if (problema) { aviso(problema, false); return; }
        cuerpo.password = password;
      }
      const btn = document.getElementById('btn-alta');
      btn.disabled = true;
      try {
        const d = await enviar('/consultores', cuerpo);
        if (d.ok) document.getElementById('form-alta').reset();
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById('tabla-equipo').addEventListener('click', async (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      const c = consultores.find(x => String(x.id) === (b.dataset.desactivar || b.dataset.activar || b.dataset.reasignar));
      if (!c) return;
      if (b.dataset.desactivar) {
        if (!confirm(`¿Desactivar a ${c.nombre}? Ya no podrá iniciar sesión. Sus expedientes y su historial se conservan.`)) return;
        await enviar(`/consultores/${c.id}/desactivar`);
      } else if (b.dataset.activar) {
        await enviar(`/consultores/${c.id}/activar`);
      } else if (b.dataset.reasignar) {
        const sel = document.querySelector(`select[data-destino-de="${c.id}"]`);
        const destino = consultores.find(x => String(x.id) === sel.value);
        if (!confirm(`¿Pasar los ${c.expedientes} expediente(s) de ${c.nombre} a ${destino.nombre}?`)) return;
        await enviar(`/consultores/${c.id}/reasignar`, { destino_id: Number(sel.value) });
      }
    });

    cargar().catch(console.error);
  }
}
