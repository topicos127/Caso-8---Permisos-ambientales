// Mi consultora: nombre, color y logo. Solo el director de proyectos puede cambiarlos (el servidor lo exige).
const usuario = requireAuth();
if (usuario) {
  pintarTopbar();
  if (usuario.rol !== 'jefe') {
    window.location.href = 'dashboard.html';
  } else {
    let empresa = null;
    let colores = [];
    let elegido = null;

    function guardarEnSesion(nueva) {
      empresa = nueva;
      usuario.empresa = nueva;
      sessionStorage.setItem('usuario', JSON.stringify(usuario));
      pintarRail();   // el menú de esta pantalla ya muestra la marca nueva
      pintarMarca();
    }

    function pintarMarca() {
      document.getElementById('nombre-empresa').value = empresa.nombre;
      elegido = empresa.color;
      const cont = document.getElementById('colores');
      cont.innerHTML = colores.map(c =>
        `<button type="button" role="radio" aria-checked="${c === elegido}" aria-label="Color ${esc(c)}" data-color="${esc(c)}" style="background:${esc(c)};"></button>`).join('');
      const marco = document.getElementById('logo-marco');
      if (empresa.logo) {
        marco.innerHTML = `<img src="${esc(empresa.logo)}" alt="Logo actual">`;
      } else {
        marco.textContent = iniciales(empresa.nombre);
      }
      document.getElementById('btn-quitar-logo').hidden = !empresa.logo;
      pintarVista();
    }

    function pintarVista() {
      const nombre = document.getElementById('nombre-empresa').value.trim() || empresa.nombre;
      const sello = empresa.logo
        ? `<div class="seal seal-logo"><img src="${esc(empresa.logo)}" alt=""></div>`
        : `<div class="seal seal-iniciales" aria-hidden="true">${esc(iniciales(nombre))}</div>`;
      const vista = document.getElementById('vista-marca');
      vista.style.setProperty('--empresa', elegido);
      vista.innerHTML = `${sello}<div><b>${esc(nombre)}</b><span>Permisos Ambientales</span></div>`;
    }

    async function cargar() {
      const d = await apiFetch('/organizacion');
      empresa = d.empresa;
      colores = d.colores || [];
      pintarMarca();
    }

    document.getElementById('colores').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-color]');
      if (!b) return;
      elegido = b.dataset.color;
      document.querySelectorAll('#colores button').forEach(x => x.setAttribute('aria-checked', String(x === b)));
      pintarVista();
    });
    document.getElementById('nombre-empresa').addEventListener('input', pintarVista);

    document.getElementById('form-marca').addEventListener('submit', async (e) => {
      e.preventDefault();
      const r = await apiFetch('/organizacion', {
        method: 'POST',
        body: JSON.stringify({ nombre: document.getElementById('nombre-empresa').value.trim(), color: elegido }),
      });
      if (r.ok) { guardarEnSesion(r.empresa); mostrarToast('Marca actualizada.', 'exito'); }
      else mostrarToast(r.mensaje || 'No se pudo guardar.', 'error');
    });

    document.getElementById('archivo-logo').addEventListener('change', async (e) => {
      const archivo = e.target.files[0];
      e.target.value = '';
      if (!archivo) return;
      if (archivo.size > 1024 * 1024) { mostrarToast('El logo no puede superar 1 MB.', 'error'); return; }
      const datos = new FormData();
      datos.append('logo', archivo);
      const r = await apiFetch('/organizacion/logo', { method: 'POST', body: datos });
      if (r.ok) { guardarEnSesion(r.empresa); mostrarToast('Logo actualizado.', 'exito'); }
      else mostrarToast(r.mensaje || 'No se pudo subir el logo.', 'error');
    });

    document.getElementById('btn-quitar-logo').addEventListener('click', async () => {
      if (!(await confirmar('Quitar el logo', 'El menú volverá a mostrar las iniciales de la consultora.', 'Quitar', true))) return;
      const r = await apiFetch('/organizacion/logo', { method: 'DELETE' });
      if (r.ok) { guardarEnSesion({ ...empresa, logo: null }); mostrarToast('Logo eliminado.', 'exito'); }
      else mostrarToast(r.mensaje || 'No se pudo quitar el logo.', 'error');
    });

    cargar().catch(console.error);
  }
}
