// Mi consultora: marca, datos, políticas, uso, exportación, accesos y titularidad. Solo el director de proyectos.
const usuario = requireAuth();
if (usuario) {
  pintarTopbar();
  if (usuario.rol !== 'jefe') {
    window.location.href = 'dashboard.html';
  } else {
    // ---------- Pestañas ----------
    const pestanas = ['marca', 'datos', 'politicas', 'uso', 'datos-exportar', 'accesos', 'titularidad'];
    const cargadas = new Set();
    const cargadores = {
      marca: () => cargarMarca(), datos: () => cargarDatos(), politicas: () => cargarPoliticas(), uso: () => cargarUso(),
      accesos: () => cargarAccesos(), titularidad: () => cargarTitularidad(),
    };
    function abrirPestana(nombre, forzar) {
      pestanas.forEach(p => {
        document.getElementById('tab-' + p).setAttribute('aria-selected', String(p === nombre));
        document.getElementById('sec-' + p).hidden = p !== nombre;
      });
      history.replaceState(null, '', window.location.pathname + '#' + nombre);
      if (cargadores[nombre] && (forzar || !cargadas.has(nombre))) {
        cargadas.add(nombre);
        Promise.resolve(cargadores[nombre]()).catch(console.error);
      }
    }
    pestanas.forEach(p => document.getElementById('tab-' + p).addEventListener('click', () => abrirPestana(p)));

    const num = (n) => Number(n || 0).toLocaleString('es-PA');
    const tamano = (b) => b >= 1073741824 ? (b / 1073741824).toFixed(2) + ' GB' : b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(0, Math.round(b / 1024)) + ' KB';

    // Pide la contraseña actual (y opcionalmente otro dato) en una ventana. Devuelve valores o null.
    function pedirClave({ titulo, texto, boton = 'Continuar', peligro = false }) {
      return new Promise(resolver => {
        let enviado = false;
        abrirModal({
          titulo,
          html: `<p>${esc(texto)}</p><div class="doc-field"><label for="m-clave">Contraseña actual</label>
            <input type="password" id="m-clave" autocomplete="current-password"></div><div class="doc-msg" id="m-error" role="alert"></div>`,
          acciones: [
            { texto: 'Cancelar', clase: 'btn btn-ghost', alHacerClic: () => { if (!enviado) resolver(null); } },
            {
              texto: boton, clase: peligro ? 'btn btn-peligro' : 'btn btn-brass',
              alHacerClic: ({ el }) => {
                const password = el.querySelector('#m-clave').value;
                if (!password) { const e = el.querySelector('#m-error'); e.className = 'doc-msg show error'; e.textContent = 'Escriba su contraseña actual.'; return false; }
                enviado = true;
                resolver({ password });
              },
            },
          ],
        });
      });
    }
    const avisar = (r, ok = 'Listo.') => mostrarToast(r.mensaje || (r.ok ? ok : 'No se pudo completar.'), r.ok ? 'exito' : 'error');

    // ================= Marca =================
    let empresa = null;
    let colores = [];
    let elegido = null;

    function guardarEnSesion(nueva) {
      empresa = nueva;
      usuario.empresa = nueva;
      sessionStorage.setItem('usuario', JSON.stringify(usuario));
      pintarRail();
      pintarMarca();
    }
    function pintarMarca() {
      document.getElementById('nombre-empresa').value = empresa.nombre;
      elegido = empresa.color;
      document.getElementById('colores').innerHTML = colores.map(c =>
        `<button type="button" role="radio" aria-checked="${c === elegido}" aria-label="Color ${esc(c)}" data-color="${esc(c)}" style="background:${esc(c)};"></button>`).join('');
      const marco = document.getElementById('logo-marco');
      if (empresa.logo) marco.innerHTML = `<img src="${esc(empresa.logo)}" alt="Logo actual">`;
      else marco.textContent = iniciales(empresa.nombre);
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
      vista.innerHTML = `${sello}<div><b>${esc(nombre)}</b><span>Apto</span></div>`;
    }
    async function cargarMarca() {
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
      const r = await apiFetch('/organizacion', { method: 'POST', body: JSON.stringify({ nombre: document.getElementById('nombre-empresa').value.trim(), color: elegido }) });
      if (r.ok) { guardarEnSesion(r.empresa); mostrarToast('Marca actualizada.', 'exito'); } else avisar(r);
    });
    document.getElementById('archivo-logo').addEventListener('change', async (e) => {
      const archivo = e.target.files[0];
      e.target.value = '';
      if (!archivo) return;
      if (archivo.size > 1024 * 1024) { mostrarToast('El logo no puede superar 1 MB.', 'error'); return; }
      const datos = new FormData();
      datos.append('logo', archivo);
      const r = await apiFetch('/organizacion/logo', { method: 'POST', body: datos });
      if (r.ok) { guardarEnSesion(r.empresa); mostrarToast('Logo actualizado.', 'exito'); } else avisar(r);
    });
    document.getElementById('btn-quitar-logo').addEventListener('click', async () => {
      if (!(await confirmar('Quitar el logo', 'El menú volverá a mostrar las iniciales de la consultora.', 'Quitar', true))) return;
      const r = await apiFetch('/organizacion/logo', { method: 'DELETE' });
      if (r.ok) { guardarEnSesion({ ...empresa, logo: null }); mostrarToast('Logo eliminado.', 'exito'); } else avisar(r);
    });

    // ================= Datos de la empresa =================
    const CAMPOS = ['razon_social', 'ruc', 'direccion', 'telefono', 'email_contacto', 'pie_documento'];
    async function cargarDatos() {
      const d = await apiFetch('/organizacion/datos');
      if (!d.datos) { document.getElementById('form-datos').hidden = true; mostrarToast(d.mensaje || 'No disponible.', 'error'); return; }
      CAMPOS.forEach(c => { document.getElementById('d-' + c).value = d.datos[c] || ''; });
    }
    document.getElementById('form-datos').addEventListener('submit', async (e) => {
      e.preventDefault();
      const cuerpo = {};
      CAMPOS.forEach(c => { cuerpo[c] = document.getElementById('d-' + c).value.trim(); });
      avisar(await apiFetch('/organizacion/datos', { method: 'POST', body: JSON.stringify(cuerpo) }), 'Datos guardados.');
    });

    // ================= Políticas =================
    async function cargarPoliticas() {
      const [p, eq] = await Promise.all([apiFetch('/organizacion/politica'), apiFetch('/organizacion/equipo')]);
      if (p.mensaje && p.ok === false) { document.getElementById('form-politica').hidden = true; mostrarToast(p.mensaje, 'error'); return; }
      const casilla = document.getElementById('p-2fa');
      casilla.checked = !!p.exigir_2fa;
      casilla.disabled = !p.mi_2fa && !p.exigir_2fa;
      document.getElementById('p-2fa-aviso').hidden = p.mi_2fa || p.exigir_2fa;
      document.getElementById('p-sesion').innerHTML = '<option value="">Valor general (120 min)</option>'
        + p.opciones_sesion.map(m => `<option value="${m}">${m} minutos</option>`).join('');
      document.getElementById('p-sesion').value = p.sesion_minutos || '';
      document.getElementById('p-aviso').innerHTML = '<option value="">Sin definir (cada persona elige)</option>'
        + p.opciones_aviso.map(d => `<option value="${d}">${d} días antes</option>`).join('');
      document.getElementById('p-aviso').value = p.aviso_defecto || '';
      const filas = eq.equipo || [];
      document.getElementById('tabla-seguridad').innerHTML = filas.map(f => `
        <tr><td data-label="Persona" style="padding-left:22px;"><b>${esc(f.nombre)}</b>${f.titular ? ' <span class="status status-info">Titular</span>' : ''}<br><small style="color:var(--text-faint);">${esc(f.email)}</small></td>
          <td data-label="Rol">${esc(ROL_TEXTO[f.rol] || f.rol)}</td>
          <td data-label="Dos pasos"><span class="${f.dos_pasos ? 'status status-ok' : 'status status-warn'}">${f.dos_pasos ? 'Activos' : 'Sin activar'}</span></td>
          <td data-label="Último acceso">${esc(f.ultimo_acceso || 'Sin registro')}</td>
          <td data-label="Estado">${f.activo ? '' : '<span class="status status-bad">Desactivado</span>'}</td></tr>`).join('')
        || '<tr><td colspan="5" class="sin-etiqueta" data-label="" style="padding:20px; text-align:center;">Sin personas.</td></tr>';
    }
    document.getElementById('form-politica').addEventListener('submit', async (e) => {
      e.preventDefault();
      const aviso = document.getElementById('p-aviso').value;
      const cuerpo = {
        exigir_2fa: document.getElementById('p-2fa').checked,
        sesion_minutos: document.getElementById('p-sesion').value ? Number(document.getElementById('p-sesion').value) : null,
        aviso_defecto: aviso ? Number(aviso) : null,
        aplicar_aviso: document.getElementById('p-aplicar').checked && !!aviso,
      };
      const r = await apiFetch('/organizacion/politica', { method: 'POST', body: JSON.stringify(cuerpo) });
      avisar(r, 'Política guardada.');
      if (r.ok) { document.getElementById('p-aplicar').checked = false; cargarPoliticas(); }
    });
    document.getElementById('btn-cerrar-equipo').addEventListener('click', async () => {
      const datos = await pedirClave({ titulo: 'Cerrar las sesiones del equipo',
        texto: 'Toda su consultora tendrá que iniciar sesión otra vez. La suya seguirá abierta. Confirme con su contraseña.', boton: 'Cerrar sesiones', peligro: true });
      if (!datos) return;
      avisar(await apiFetch('/organizacion/cerrar-sesiones', { method: 'POST', body: JSON.stringify(datos) }));
    });

    // ================= Uso =================
    async function cargarUso() {
      const d = await apiFetch('/organizacion/uso');
      const p = d.personas || {};
      const tarjeta = (titulo, valor, sub) => `<div class="stat"><div class="top"><span class="lbl">${esc(titulo)}</span></div><div class="num">${esc(valor)}</div><div class="kpi-sub">${sub}</div></div>`;
      const equipo = (p.jefe ? p.jefe.activos : 0) + (p.consultor ? p.consultor.activos : 0);
      document.getElementById('uso-tarjetas').innerHTML =
        tarjeta('Equipo activo', num(equipo), `${num(p.jefe ? p.jefe.activos : 0)} ${palabra(p.jefe ? p.jefe.activos : 0, 'director', 'directores')} y ${num(p.consultor ? p.consultor.activos : 0)} ${palabra(p.consultor ? p.consultor.activos : 0, 'consultor', 'consultores')}`)
        + tarjeta('Clientes con acceso', num(p.promotor ? p.promotor.total : 0), 'cuentas de cliente')
        + tarjeta('Expedientes', num(d.expedientes.total), `${num(d.expedientes.en_tramite)} en trámite`)
        + tarjeta('Documentos', num(d.documentos.recibidos), `${num(d.documentos.versiones)} ${palabra(d.documentos.versiones, 'versión guardada', 'versiones guardadas')}`)
        + tarjeta('Almacenamiento', tamano(d.documentos.bytes), 'ocupado por los documentos')
        + tarjeta('Comentarios internos', num(d.comentarios), `${num(d.invitaciones_pendientes)} ${palabra(d.invitaciones_pendientes, 'invitación pendiente', 'invitaciones pendientes')}`);
    }

    // ================= Mis datos (exportar) =================
    async function descargar(url, mensajeOk) {
      const boton = document.activeElement;
      try {
        const r = await fetch(url, { credentials: 'same-origin', headers: cabecerasApi() });
        if (!r.ok) { const d = await r.json().catch(() => ({})); mostrarToast(d.mensaje || 'No se pudo generar el archivo.', 'error'); return; }
        const blob = await r.blob();
        const nombre = (r.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)"?/);
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = nombre ? nombre[1] : 'descarga';
        a.click();
        URL.revokeObjectURL(a.href);
        mostrarToast(mensajeOk, 'exito');
      } finally { if (boton && boton.blur) boton.blur(); }
    }
    document.getElementById('btn-exportar').addEventListener('click', () => descargar('/organizacion/exportar', 'Exportación lista.'));
    document.getElementById('btn-exportar-csv').addEventListener('click', () => descargar('/organizacion/auditoria.csv', 'Registro descargado.'));

    // ================= Accesos =================
    let paginaAccesos = 1;
    async function cargarAccesos() {
      const tipo = document.getElementById('a-tipo').value;
      const d = await apiFetch(`/organizacion/auditoria?pagina=${paginaAccesos}` + (tipo ? `&tipo=${encodeURIComponent(tipo)}` : ''));
      const sel = document.getElementById('a-tipo');
      if (sel.options.length <= 1) {
        sel.innerHTML = '<option value="">Todos los eventos</option>' + d.tipos.map(t => `<option value="${esc(t.clave)}">${esc(t.texto)}</option>`).join('');
        sel.value = tipo;
      }
      const marcaFallo = (t) => t === 'acceso_fallido' ? 'status status-bad' : t === 'acceso' ? 'status status-neutral' : 'status status-info';
      document.getElementById('tabla-accesos').innerHTML = d.eventos.length ? d.eventos.map(ev => `
        <tr><td data-label="Fecha" style="padding-left:22px; white-space:nowrap; font-family:var(--mono); font-size:12.5px;">${esc(ev.fecha)}</td>
          <td data-label="Evento"><span class="${marcaFallo(ev.tipo)}">${esc(ev.texto)}</span></td>
          <td data-label="Persona">${esc(ev.quien)}</td><td data-label="Detalle">${esc(ev.detalle || '')}</td>
          <td data-label="IP" style="font-family:var(--mono); font-size:12.5px;">${esc(ev.ip || '')}</td></tr>`).join('')
        : '<tr><td colspan="5" class="sin-etiqueta" data-label="" style="padding:22px; text-align:center; color:var(--text-faint);">Sin eventos.</td></tr>';
      const pg = d.paginacion;
      document.getElementById('a-pie').textContent = `Página ${pg.pagina} de ${pg.paginas} · ${num(pg.total)} ${palabra(pg.total, 'evento', 'eventos')}`;
      document.getElementById('a-ant').disabled = pg.pagina <= 1;
      document.getElementById('a-sig').disabled = pg.pagina >= pg.paginas;
    }
    document.getElementById('a-tipo').addEventListener('change', () => { paginaAccesos = 1; cargarAccesos(); });
    document.getElementById('a-ant').addEventListener('click', () => { paginaAccesos = Math.max(1, paginaAccesos - 1); cargarAccesos(); });
    document.getElementById('a-sig').addEventListener('click', () => { paginaAccesos += 1; cargarAccesos(); });

    // ================= Titularidad =================
    let datosTitular = null;
    async function cargarTitularidad() {
      const d = await apiFetch('/organizacion/directores');
      datosTitular = d;
      document.getElementById('t-nota').textContent = d.soy_titular
        ? 'Usted es el titular de la cuenta: puede invitar a otros directores, cambiar roles y transferir la titularidad.'
        : 'Solo el titular de la cuenta puede invitar a otros directores, cambiar roles o transferir la titularidad.';
      document.getElementById('t-directores').innerHTML = d.directores.map(p => `
        <li><span><b>${esc(p.nombre)}</b> ${p.titular ? '<span class="status status-info">Titular</span>' : ''}${p.activo ? '' : ' <span class="status status-bad">Desactivado</span>'}<small>${esc(p.email)}</small></span>
          <span class="acciones">${d.soy_titular && !p.titular ? `
            <button type="button" class="btn btn-ghost" data-titular="${p.id}" data-nombre="${esc(p.nombre)}">Hacer titular</button>
            <button type="button" class="btn btn-ghost" data-bajar="${p.id}" data-nombre="${esc(p.nombre)}">Pasar a consultor</button>` : ''}</span></li>`).join('');
      document.getElementById('t-candidatos').innerHTML = d.candidatos.length ? d.candidatos.map(p => `
        <li><span><b>${esc(p.nombre)}</b><small>${esc(p.email)}</small></span>
          <span class="acciones">${d.soy_titular ? `<button type="button" class="btn btn-ghost" data-subir="${p.id}" data-nombre="${esc(p.nombre)}">Ascender a director</button>` : ''}</span></li>`).join('')
        : '<li><span class="panel-note" style="margin:0;">No hay consultores activos.</span></li>';
      document.getElementById('t-invitar').hidden = !d.soy_titular;
    }
    document.getElementById('sec-titularidad').addEventListener('click', async (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.subir || b.dataset.bajar) {
        const id = b.dataset.subir || b.dataset.bajar;
        const sube = !!b.dataset.subir;
        if (!(await confirmar(sube ? 'Ascender a director de proyectos' : 'Pasar a consultor',
          sube ? `${b.dataset.nombre} podrá ver todos los expedientes y gestionar el equipo. Tendrá que volver a iniciar sesión.`
               : `${b.dataset.nombre} dejará de gestionar el equipo y solo verá sus expedientes. Tendrá que volver a iniciar sesión.`,
          sube ? 'Ascender' : 'Pasar a consultor', !sube))) return;
        avisar(await apiFetch(`/organizacion/directores/${id}/rol`, { method: 'POST', body: JSON.stringify({ rol: sube ? 'jefe' : 'consultor' }) }));
        cargarTitularidad();
      } else if (b.dataset.titular) {
        const datos = await pedirClave({ titulo: 'Transferir la titularidad',
          texto: `${b.dataset.nombre} pasará a ser el titular de la cuenta y usted dejará de serlo. Confirme con su contraseña.`, boton: 'Transferir', peligro: true });
        if (!datos) return;
        const r = await apiFetch('/organizacion/titular', { method: 'POST', body: JSON.stringify({ usuario_id: Number(b.dataset.titular), ...datos }) });
        avisar(r);
        cargarTitularidad();
      }
    });
    document.getElementById('t-form-invitar').addEventListener('submit', async (e) => {
      e.preventDefault();
      const correo = document.getElementById('t-correo').value.trim();
      const r = await apiFetch('/invitaciones', { method: 'POST', body: JSON.stringify(correo ? { rol: 'jefe', email: correo } : { rol: 'jefe' }) });
      if (!r.ok) { avisar(r); return; }
      document.getElementById('t-enlace').innerHTML = `<div class="aviso-unico" style="margin-top:12px;">Copie el enlace ahora: no se vuelve a mostrar. Vence el ${esc(r.expira)}.</div>
        <div class="enlace-unico"><input type="text" readonly id="t-enlace-campo" value="${esc(r.enlace)}" aria-label="Enlace de invitación del director"><button type="button" class="btn btn-brass" id="t-copiar">Copiar enlace</button></div>`;
      document.getElementById('t-enlace-campo').select();
      document.getElementById('t-copiar').addEventListener('click', () => copiarTexto(r.enlace, 'Enlace copiado.'));
      document.getElementById('t-form-invitar').reset();
    });

    const inicial = window.location.hash.replace('#', '');
    abrirPestana(pestanas.includes(inicial) ? inicial : 'marca');
  }
}
