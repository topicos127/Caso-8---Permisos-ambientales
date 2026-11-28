// Administración de la plataforma: empresas, respaldos y estado del servicio. Solo el administrador.
const usuario = requireAuth();
if (usuario) {
  pintarTopbar();
  if (usuario.rol !== 'admin') {
    window.location.href = 'dashboard.html';
  } else {
    let empresas = [];

    // ---------- Pestañas ----------
    const pestanas = ['resumen', 'empresas', 'administradores', 'respaldos', 'servicio'];
    function abrirPestana(nombre) {
      pestanas.forEach(p => {
        document.getElementById('tab-' + p).setAttribute('aria-selected', String(p === nombre));
        document.getElementById('sec-' + p).hidden = p !== nombre;
      });
      if (nombre === 'resumen') cargarResumen().catch(console.error);
      if (nombre === 'empresas') cargarEmpresas().catch(console.error);
      if (nombre === 'administradores') cargarAdministradores().catch(console.error);
      if (nombre === 'respaldos') cargarRespaldos().catch(console.error);
      if (nombre === 'servicio') cargarServicio().catch(console.error);
      history.replaceState(null, '', window.location.pathname + '#' + nombre);
    }
    pestanas.forEach(p => document.getElementById('tab-' + p).addEventListener('click', () => abrirPestana(p)));

    function tamano(bytes) {
      if (bytes == null) return '—';
      return bytes > 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(bytes / 1024)) + ' KB';
    }

    // ---------- Empresas ----------
    async function cargarEmpresas() {
      const d = await apiFetch('/plataforma/empresas');
      empresas = d.empresas || [];
      const tbody = document.getElementById('tabla-empresas');
      tbody.innerHTML = empresas.length ? empresas.map(e => `
        <tr>
          <td data-label="Empresa" style="padding-left:24px;"><b>${esc(e.nombre)}</b><br><small style="color:var(--text-faint);">Creada el ${esc(e.fecha_creacion)}</small></td>
          <td data-label="Director">${e.jefe_email ? esc(e.jefe_email) : '<span class="status status-warn">Sin director todavía</span>'}</td>
          <td data-label="Usuarios" style="font-family:var(--mono);">${esc(e.usuarios)}</td>
          <td data-label="Expedientes" style="font-family:var(--mono);">${esc(e.expedientes)}</td>
          <td data-label="Estado"><span class="${e.activa ? 'status status-ok' : 'status status-bad'}">${e.activa ? 'Activa' : 'Desactivada'}</span></td>
          <td data-label="Acciones"><div class="acciones">
            ${e.jefe_id ? `<button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line);" data-restablecer="${e.jefe_id}" data-nombre="${esc(e.jefe_email)}">Restablecer acceso del director</button>` : ''}
            <button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line);" data-activa="${e.id}" data-valor="${e.activa ? 'no' : 'si'}">${e.activa ? 'Desactivar' : 'Reactivar'}</button>
          </div></td>
        </tr>`).join('')
        : '<tr><td colspan="6" class="sin-etiqueta" data-label="" style="padding:24px; text-align:center; color:var(--text-faint);">Todavía no hay empresas.</td></tr>';
    }

    document.getElementById('form-empresa').addEventListener('submit', async (e) => {
      e.preventDefault();
      const nombre = document.getElementById('emp-nombre').value.trim();
      const email_jefe = document.getElementById('emp-email').value.trim();
      if (nombre.length < 3) { mostrarToast('El nombre debe tener al menos 3 caracteres.', 'error'); return; }
      const btn = document.getElementById('btn-empresa');
      btn.disabled = true;
      try {
        const d = await apiFetch('/plataforma/empresas', { method: 'POST', body: JSON.stringify(email_jefe ? { nombre, email_jefe } : { nombre }) });
        if (!d.ok) { mostrarToast(d.mensaje || 'No se pudo crear la empresa.', 'error'); return; }
        document.getElementById('emp-resultado').innerHTML = `
          <div class="aviso-unico" style="margin-top:14px;">Copie el enlace ahora: no se vuelve a mostrar. Vence el ${esc(d.expira)}.</div>
          <div class="enlace-unico"><input type="text" readonly id="emp-enlace" value="${esc(d.enlace)}" aria-label="Enlace de invitación del director">
          <button type="button" class="btn btn-brass" id="btn-copiar-emp">Copiar enlace</button></div>`;
        document.getElementById('emp-enlace').select();
        document.getElementById('btn-copiar-emp').addEventListener('click', () => copiarTexto(d.enlace, 'Enlace copiado.'));
        document.getElementById('form-empresa').reset();
        mostrarToast('Empresa creada.', 'exito');
        await cargarEmpresas();
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById('tabla-empresas').addEventListener('click', async (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.activa) {
        const apagar = b.dataset.valor === 'no';
        if (apagar && !(await confirmar('Desactivar la empresa', 'Nadie de esa empresa podrá entrar hasta que la reactive. Sus datos se conservan.', 'Desactivar', true))) return;
        const r = await apiFetch(`/plataforma/empresas/${b.dataset.activa}/activa`, { method: 'POST', body: JSON.stringify({ activa: !apagar }) });
        mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
        await cargarEmpresas();
      } else if (b.dataset.restablecer) {
        if (!(await confirmar('Restablecer el acceso del director',
          `Se genera una contraseña temporal para ${b.dataset.nombre}, se cierran sus sesiones y se quitan sus dos pasos. La verá una sola vez.`, 'Restablecer'))) return;
        const r = await apiFetch(`/plataforma/jefes/${b.dataset.restablecer}/restablecer`, { method: 'POST', body: '{}' });
        if (!r.ok) { mostrarToast(r.mensaje || 'No se pudo restablecer.', 'error'); return; }
        abrirModal({
          titulo: 'Contraseña temporal',
          html: `<p class="aviso-unico">Entréguela por un canal seguro. No se vuelve a mostrar.</p>
            <p style="margin-top:12px;">${esc(r.email)}</p><code class="clave-manual">${esc(r.password_temporal)}</code>`,
          cerrable: false,
          acciones: [
            { texto: 'Copiar', clase: 'btn btn-ghost', alHacerClic: () => { copiarTexto(r.password_temporal, 'Contraseña copiada.'); return false; } },
            { texto: 'Listo', clase: 'btn btn-brass' },
          ],
        });
      }
    });

    // ---------- Administradores ----------
    const ESTADO_INVITACION = { pendiente: ['status status-info', 'Pendiente'], usada: ['status status-ok', 'Usada'],
      vencida: ['status status-warn', 'Vencida'], revocada: ['status status-bad', 'Revocada'] };
    const BOTON = 'btn btn-ghost';

    async function cargarAdministradores() {
      const d = await apiFetch('/plataforma/administradores');
      const nota = document.getElementById('adm-dominio');
      nota.hidden = !(d.dominios && d.dominios.length);
      if (!nota.hidden) nota.textContent = 'Solo se aceptan correos ' + d.dominios.map(x => '@' + x).join(' o ') + '.';
      const sin2fa = d.administradores.filter(a => a.activo && !a.totp_activo);
      document.getElementById('adm-avisos').innerHTML = sin2fa.length
        ? `<div class="panel" style="margin-bottom:20px;"><p style="margin:0;"><span class="status status-warn">Para atender</span> &nbsp;${sin2fa.length === 1 ? 'Un administrador no tiene' : sin2fa.length + ' administradores no tienen'} los dos pasos activos: ${sin2fa.map(a => esc(a.nombre)).join(', ')}. Estas cuentas pueden restaurar respaldos y ver todas las empresas.</p></div>`
        : '';
      document.getElementById('tabla-administradores').innerHTML = d.administradores.map(a => `
        <tr>
          <td data-label="Administrador" style="padding-left:24px;"><b>${esc(a.nombre)}</b>${a.es_usted ? ' <span class="status status-neutral">Usted</span>' : ''}<br><small style="color:var(--text-faint);">${esc(a.email)} · desde el ${esc(a.fecha_creacion)}</small></td>
          <td data-label="Estado"><span class="${a.activo ? 'status status-ok' : 'status status-bad'}">${a.activo ? 'Activo' : 'Desactivado'}</span></td>
          <td data-label="Dos pasos"><span class="${a.totp_activo ? 'status status-ok' : 'status status-warn'}">${a.totp_activo ? 'Activados' : 'Sin activar'}</span></td>
          <td data-label="Último acceso">${esc(a.ultimo_acceso || 'Sin accesos')}</td>
          <td data-label="Acciones"><div class="acciones">${a.es_usted ? '<small style="color:var(--text-faint);">Su cuenta se gestiona en «Mi perfil»</small>' : `
            <button type="button" class="${BOTON}" style="border:1.5px solid var(--line);" data-restablecer="${a.id}" data-nombre="${esc(a.email)}">Restablecer acceso</button>
            <button type="button" class="${BOTON}" style="border:1.5px solid var(--line);" data-activo="${a.id}" data-valor="${a.activo ? 'no' : 'si'}" data-nombre="${esc(a.nombre)}">${a.activo ? 'Desactivar' : 'Reactivar'}</button>`}
          </div></td>
        </tr>`).join('');
      document.getElementById('tabla-admin-invitaciones').innerHTML = d.invitaciones.length ? d.invitaciones.map(i => {
        const [clase, texto] = ESTADO_INVITACION[i.estado] || ESTADO_INVITACION.pendiente;
        return `<tr>
          <td data-label="Correo" style="padding-left:22px;">${i.email ? esc(i.email) : '<span style="color:var(--text-faint);">Cualquiera con el enlace</span>'}</td>
          <td data-label="Creada por">${esc(i.creada_por)}<br><small style="color:var(--text-faint);">${esc(i.fecha_creacion)}</small></td>
          <td data-label="Vence">${esc(i.expira)}</td>
          <td data-label="Estado"><span class="${clase}">${texto}</span></td>
          <td data-label="Acciones">${i.estado === 'pendiente' ? `<button type="button" class="${BOTON}" style="border:1.5px solid var(--line);" data-revocar="${i.id}">Revocar</button>` : ''}</td>
        </tr>`;
      }).join('') : '<tr><td colspan="5" class="sin-etiqueta" data-label="" style="padding:24px; text-align:center; color:var(--text-faint);">Todavía no hay invitaciones.</td></tr>';
      document.getElementById('adm-eventos').innerHTML = d.eventos.length ? `<ul class="lista-simple">${d.eventos.map(e => `
        <li><span><b>${esc(e.texto)}</b>${e.nombre || e.email ? ' · ' + esc(e.nombre || e.email) : ''}${e.detalle ? ` <small style="display:inline; color:var(--text-faint);">(${esc(e.detalle)})</small>` : ''}</span>
          <small style="display:inline; color:var(--text-faint);">${esc(e.fecha)}${e.ip ? ' · ' + esc(e.ip) : ''}</small></li>`).join('')}</ul>`
        : '<p class="panel-note" style="margin:0;">Todavía no hay actividad registrada.</p>';
    }

    document.getElementById('form-admin').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('adm-email').value.trim();
      const btn = document.getElementById('btn-admin');
      btn.disabled = true;
      try {
        const d = await apiFetch('/plataforma/administradores/invitaciones', { method: 'POST', body: JSON.stringify(email ? { email } : {}) });
        if (!d.ok) { mostrarToast(d.mensaje || 'No se pudo crear la invitación.', 'error'); return; }
        document.getElementById('adm-resultado').innerHTML = `
          <div class="aviso-unico" style="margin-top:14px;">Copie el enlace ahora: no se vuelve a mostrar. Vence el ${esc(d.expira)}.</div>
          <div class="enlace-unico"><input type="text" readonly id="adm-enlace" value="${esc(d.enlace)}" aria-label="Enlace de invitación del administrador">
          <button type="button" class="btn btn-brass" id="btn-copiar-adm">Copiar enlace</button></div>`;
        document.getElementById('adm-enlace').select();
        document.getElementById('btn-copiar-adm').addEventListener('click', () => copiarTexto(d.enlace, 'Enlace copiado.'));
        document.getElementById('form-admin').reset();
        mostrarToast('Invitación creada.', 'exito');
        await cargarAdministradores();
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById('sec-administradores').addEventListener('click', async (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.revocar) {
        if (!(await confirmar('Revocar la invitación', 'El enlace dejará de funcionar.', 'Revocar', true))) return;
        const r = await apiFetch(`/plataforma/administradores/invitaciones/${b.dataset.revocar}`, { method: 'DELETE' });
        mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
        await cargarAdministradores();
      } else if (b.dataset.activo) {
        const apagar = b.dataset.valor === 'no';
        if (apagar && !(await confirmar('Desactivar al administrador', `${b.dataset.nombre} no podrá entrar a la administración y se cierran sus sesiones abiertas. Se puede reactivar.`, 'Desactivar', true))) return;
        const r = await apiFetch(`/plataforma/administradores/${b.dataset.activo}/activo`, { method: 'POST', body: JSON.stringify({ activo: !apagar }) });
        mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
        await cargarAdministradores();
      } else if (b.dataset.restablecer) {
        if (!(await confirmar('Restablecer el acceso del administrador',
          `Se genera una contraseña temporal para ${b.dataset.nombre}, se cierran sus sesiones y se quitan sus dos pasos. La verá una sola vez.`, 'Restablecer'))) return;
        const r = await apiFetch(`/plataforma/administradores/${b.dataset.restablecer}/restablecer`, { method: 'POST', body: '{}' });
        if (!r.ok) { mostrarToast(r.mensaje || 'No se pudo restablecer.', 'error'); return; }
        abrirModal({
          titulo: 'Contraseña temporal',
          html: `<p class="aviso-unico">Entréguela por un canal seguro. No se vuelve a mostrar.</p>
            <p style="margin-top:12px;">${esc(r.email)}</p><code class="clave-manual">${esc(r.password_temporal)}</code>`,
          cerrable: false,
          acciones: [
            { texto: 'Copiar', clase: 'btn btn-ghost', alHacerClic: () => { copiarTexto(r.password_temporal, 'Contraseña copiada.'); return false; } },
            { texto: 'Listo', clase: 'btn btn-brass' },
          ],
        });
      }
    });

    // ---------- Respaldos ----------
    async function cargarRespaldos() {
      const d = await apiFetch('/plataforma/respaldos');
      document.getElementById('resp-nota').textContent = d.automatico
        ? `Respaldo automático cada día a las ${String(d.hora).padStart(2, '0')}:00 (hora de Panamá). Se conservan los últimos ${d.conservar}.`
        : 'El respaldo automático está desactivado: cree respaldos a mano o active RESPALDO_AUTOMATICO.';
      const tbody = document.getElementById('tabla-respaldos');
      tbody.innerHTML = d.respaldos.length ? d.respaldos.map(r => `
        <tr>
          <td data-label="Respaldo" style="padding-left:24px; font-family:var(--mono); font-size:13px;">${esc(r.nombre)}</td>
          <td data-label="Creado">${esc(r.creado)}</td>
          <td data-label="Tipo"><span class="status status-neutral">${esc(r.tipo)}</span></td>
          <td data-label="Tamaño">${esc(tamano(r.tamano))}</td>
          <td data-label="Acciones"><div class="acciones">
            <a class="btn btn-ghost" style="border:1.5px solid var(--line);" href="/plataforma/respaldos/${encodeURIComponent(r.nombre)}" download>Descargar</a>
            <button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line);" data-verificar="${esc(r.nombre)}">Verificar</button>
            <button type="button" class="btn btn-brass" data-restaurar="${esc(r.nombre)}">Restaurar</button>
            <button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line);" data-borrar="${esc(r.nombre)}">Eliminar</button>
          </div></td>
        </tr>`).join('')
        : '<tr><td colspan="5" class="sin-etiqueta" data-label="" style="padding:24px; text-align:center; color:var(--text-faint);">Todavía no hay respaldos.</td></tr>';
    }

    document.getElementById('btn-respaldo').addEventListener('click', async () => {
      const r = await apiFetch('/plataforma/respaldos', { method: 'POST', body: '{}' });
      if (r.ok) {
        mostrarToast(`Respaldo creado (${r.respaldo.tablas} tablas, ${r.respaldo.filas} filas, ${r.respaldo.archivos} archivos).`, 'exito');
        await cargarRespaldos();
      } else mostrarToast(r.mensaje || 'No se pudo crear el respaldo.', 'error');
    });

    document.getElementById('tabla-respaldos').addEventListener('click', async (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.verificar) {
        const r = await apiFetch(`/plataforma/respaldos/${encodeURIComponent(b.dataset.verificar)}/verificar`, { method: 'POST', body: '{}' });
        mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
      } else if (b.dataset.borrar) {
        if (!(await confirmar('Eliminar el respaldo', b.dataset.borrar, 'Eliminar', true))) return;
        const r = await apiFetch(`/plataforma/respaldos/${encodeURIComponent(b.dataset.borrar)}`, { method: 'DELETE' });
        mostrarToast(r.mensaje || 'Listo.', r.ok ? 'exito' : 'error');
        await cargarRespaldos();
      } else if (b.dataset.restaurar) {
        const nombre = b.dataset.restaurar;
        abrirModal({
          titulo: 'Restaurar este respaldo',
          html: `<p class="aviso-unico">Esto reemplaza TODOS los datos actuales (empresas, usuarios, expedientes y documentos) por los de este respaldo.</p>
            <p style="margin-top:12px;">${esc(nombre)}<br>Antes se guarda un respaldo del estado actual. Para continuar, escriba <b>RESTAURAR</b>.</p>
            <div class="doc-field"><input type="text" id="m-confirmar" autocomplete="off" spellcheck="false" aria-label="Escriba RESTAURAR"></div>
            <div class="doc-msg" id="m-error" role="alert"></div>`,
          acciones: [
            { texto: 'Cancelar', clase: 'btn btn-ghost' },
            {
              texto: 'Restaurar', clase: 'btn btn-peligro',
              alHacerClic: async ({ el }) => {
                if (el.querySelector('#m-confirmar').value.trim() !== 'RESTAURAR') {
                  const m = el.querySelector('#m-error');
                  m.className = 'doc-msg show error';
                  m.textContent = 'Escriba RESTAURAR para confirmar.';
                  return false;
                }
                const r = await apiFetch(`/plataforma/respaldos/${encodeURIComponent(nombre)}/restaurar`,
                  { method: 'POST', body: JSON.stringify({ confirmar: 'RESTAURAR' }) });
                mostrarToast(r.mensaje || (r.ok ? 'Datos restaurados.' : 'No se pudo restaurar.'), r.ok ? 'exito' : 'error');
                await cargarRespaldos();
                await cargarEmpresas();
              },
            },
          ],
        });
      }
    });

    // ---------- Servicio y errores ----------
    async function cargarServicio() {
      const [estado, errores] = await Promise.all([apiFetch('/plataforma/estado'), apiFetch('/plataforma/errores')]);
      const luz = (ok, titulo, texto) => `<div class="indicador ${ok ? '' : 'falla'}"><span class="luz" aria-hidden="true"></span>
        <div><b>${esc(titulo)}</b><span>${esc(ok ? texto : 'No responde')}</span></div></div>`;
      document.getElementById('indicadores').innerHTML =
        luz(estado.base_de_datos, 'Base de datos', 'Conectada')
        + luz(estado.archivos, 'Almacenamiento de archivos', estado.almacenamiento === 's3' ? 'Servicio S3 conectado' : 'Disco local')
        + `<div class="indicador"><span class="luz" aria-hidden="true"></span><div><b>Versión ${esc(estado.version)}</b><span>Activo desde ${esc(estado.activo_desde)}</span></div></div>`
        + `<div class="indicador ${estado.errores ? 'falla' : ''}"><span class="luz" aria-hidden="true"></span><div><b>${esc(estado.errores)} errores</b><span>${esc(estado.peticiones)} peticiones desde el inicio</span></div></div>`;
      const t = estado.totales || {};
      const ult = estado.ultimo_respaldo;
      document.getElementById('panel-totales').innerHTML = `<h3>Resumen</h3>
        <p style="margin:0;">${esc(t.empresas ?? '—')} empresas · ${esc(t.usuarios ?? '—')} usuarios · ${esc(t.expedientes ?? '—')} expedientes · ${esc(t.documentos ?? '—')} documentos.</p>
        <p class="panel-note" style="margin:8px 0 0;">${ult ? `Último respaldo: ${esc(ult.creado)} (${esc(ult.tipo)}).` : '<b style="color:var(--status-warn);">Todavía no hay ningún respaldo.</b>'}</p>`;
      const lista = document.getElementById('lista-errores');
      lista.innerHTML = errores.errores.length ? errores.errores.map(x => `
        <div class="error-fila"><b>${esc(x.cuando)}</b> · <code>${esc(x.id)}</code> · ${esc(x.metodo)} ${esc(x.ruta)}
          <div>${esc(x.error)}</div><pre>${esc(x.detalle)}</pre></div>`).join('')
        : '<p class="panel-note" style="margin:0;">Sin errores desde que arrancó el servidor.</p>';
    }

    // ---------- Resumen (tablero) ----------
    const ESTADOS = [
      ['pendiente', 'Pendiente de subsanación', '#e09a1a'], ['aprobado_interno', 'Aprobado internamente', '#7c5ac8'],
      ['evaluacion', 'En evaluación', '#3b6bea'], ['aprobado', 'Aprobado', '#1f9d67'], ['rechazado', 'Rechazado', '#e04b3f'],
    ];
    const NIVEL = { alta: ['status status-bad', 'Urgente'], media: ['status status-warn', 'Atender'], info: ['status status-info', 'Para saber'] };
    const num = (n) => Number(n || 0).toLocaleString('es-PA');

    function kpi(etiqueta, valor, sub, icono) {
      return `<div class="stat"><div class="top"><span class="lbl">${esc(etiqueta)}</span><span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">${icono}</svg></span></div>
        <div class="num">${esc(num(valor))}</div><div class="kpi-sub">${sub}</div></div>`;
    }

    function graficoActividad(serie) {
      const max = Math.max(1, ...serie.map(p => p.n));
      const ancho = 640, alto = 170, base = 140, paso = ancho / serie.length, barra = paso * 0.62;
      const total = serie.reduce((a, p) => a + p.n, 0);
      const barras = serie.map((p, i) => {
        const h = Math.round((p.n / max) * (base - 22));
        const x = i * paso + (paso - barra) / 2;
        return `<g><title>${esc(p.dia)}: ${esc(p.n)} acciones</title>
          <rect x="${x.toFixed(1)}" y="${base - h}" width="${barra.toFixed(1)}" height="${Math.max(h, 2)}" rx="4" fill="var(--brand)" opacity="${p.n ? 1 : 0.25}"/>
          ${p.n ? `<text x="${(x + barra / 2).toFixed(1)}" y="${base - h - 6}" text-anchor="middle" font-size="11" fill="var(--text-soft)">${esc(p.n)}</text>` : ''}
          <text x="${(x + barra / 2).toFixed(1)}" y="${base + 18}" text-anchor="middle" font-size="10.5" fill="var(--text-faint)">${i % 2 === 0 ? esc(p.dia) : ''}</text></g>`;
      }).join('');
      return `<svg viewBox="0 0 ${ancho} ${alto}" width="100%" role="img" aria-label="Acciones por día en los últimos ${serie.length} días: ${total} en total">
        <line x1="0" y1="${base}" x2="${ancho}" y2="${base}" stroke="var(--line-strong)"/>${barras}</svg>`;
    }

    function barrasHorizontales(filas, total) {
      return filas.map(([nombre, n, color]) => `
        <div class="barra-fila"><div class="barra-cab"><span>${esc(nombre)}</span><b>${esc(num(n))}</b></div>
        <div class="barra-pista"><div class="barra-relleno" style="width:${total ? Math.round(n / total * 100) : 0}%; background:${color};"></div></div></div>`).join('');
    }

    async function cargarResumen() {
      const d = await apiFetch('/plataforma/resumen');
      const ic = {
        emp: '<path d="M4 20V6.5L12 3l8 3.5V20"/><path d="M9 20v-5h6v5"/>',
        per: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
        exp: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
        doc: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
      };
      document.getElementById('res-kpis').innerHTML =
        kpi('Empresas activas', d.empresas.activas, `${esc(d.empresas.nuevas_30d)} ${palabra(d.empresas.nuevas_30d, 'nueva', 'nuevas')} en 30 días${d.empresas.desactivadas ? ` · ${esc(d.empresas.desactivadas)} ${palabra(d.empresas.desactivadas, 'desactivada', 'desactivadas')}` : ''}`, ic.emp)
        + kpi('Personas', d.usuarios.total, `${esc(d.usuarios.nuevos_30d)} ${palabra(d.usuarios.nuevos_30d, 'nueva', 'nuevas')} en 30 días`, ic.per)
        + kpi('Expedientes', d.expedientes.total, `${esc(d.expedientes.en_tramite)} en trámite · ${esc(d.expedientes.nuevos_30d)} nuevos en 30 días`, ic.exp)
        + kpi('Documentos', d.documentos.recibidos, `${esc(d.documentos.versiones)} versiones guardadas`, ic.doc);

      // Avisos: lo que conviene mirar hoy
      const av = d.avisos || [];
      document.getElementById('res-avisos').innerHTML = av.length
        ? `<div class="panel" style="margin-bottom:20px;"><h3>Para atender</h3><ul class="lista-simple">${av.map((a, i) => {
            const [clase, texto] = NIVEL[a.nivel] || NIVEL.info;
            return `<li><span style="display:flex; gap:10px; align-items:center;"><span class="${clase}">${texto}</span>${esc(a.texto)}</span>
              <button type="button" class="btn btn-ghost" style="border:1.5px solid var(--line); padding:4px 12px; font-size:13px;" data-ir="${esc(a.pestana)}">Ver</button></li>`;
          }).join('')}</ul></div>`
        : '<div class="panel" style="margin-bottom:20px; border-color:rgba(31,157,103,.35);"><p style="margin:0;"><span class="status status-ok">Todo en orden</span> &nbsp;No hay nada urgente que atender.</p></div>';

      document.getElementById('res-actividad').innerHTML = graficoActividad(d.actividad);

      // Empresas
      document.getElementById('res-ranking').innerHTML = d.ranking.length ? d.ranking.map(r => `
        <tr><td data-label="Empresa" style="padding-left:22px;"><span class="punto-empresa" style="background:${esc(r.color)};"></span><b>${esc(r.nombre)}</b>
            ${r.activa ? '' : ' <span class="status status-bad">Desactivada</span>'}${r.inactiva ? ' <span class="status status-warn">Inactiva</span>' : ''}</td>
          <td data-label="Equipo" style="font-family:var(--mono);">${esc(r.equipo)}</td>
          <td data-label="Clientes" style="font-family:var(--mono);">${esc(r.clientes)}</td>
          <td data-label="Expedientes" style="font-family:var(--mono);">${esc(r.expedientes)}</td>
          <td data-label="En trámite" style="font-family:var(--mono);">${esc(r.en_tramite)}</td>
          <td data-label="Última actividad">${esc(r.ultima_actividad || 'Sin actividad')}</td></tr>`).join('')
        : '<tr><td colspan="6" class="sin-etiqueta" data-label="" style="padding:24px; text-align:center; color:var(--text-faint);">Todavía no hay empresas.</td></tr>';

      // Estados
      const pe = d.expedientes.por_estado || {};
      document.getElementById('res-estados').innerHTML = d.expedientes.total
        ? barrasHorizontales(ESTADOS.map(([k, nombre, color]) => [nombre, pe[k] || 0, color]), d.expedientes.total)
          + `<p class="panel-note" style="margin:12px 0 0;">Por categoría: ${['I', 'II', 'III'].map(c => `${c}: <b>${esc((d.expedientes.por_categoria || {})[c] || 0)}</b>`).join(' · ')}</p>`
        : '<p class="panel-note" style="margin:0;">Todavía no hay expedientes.</p>';

      // Personas y seguridad
      const roles = [['jefe', 'Director de proyectos'], ['consultor', 'Consultor ambiental'], ['promotor', 'Cliente'], ['admin', 'Administración']];
      document.getElementById('res-personas').innerHTML = `<ul class="lista-simple">${roles.map(([k, nombre]) => {
        const r = (d.usuarios.por_rol || {})[k] || { total: 0, activos: 0 };
        return `<li><span>${esc(nombre)}</span><span><b>${esc(r.total)}</b>${r.activos !== r.total ? ` <small style="display:inline;">(${esc(r.activos)} activas)</small>` : ''}</span></li>`;
      }).join('')}</ul>`;
      const internos = ['jefe', 'consultor'].map(k => (d.usuarios.por_rol || {})[k] || { total: 0, con_2fa: 0 });
      const totalInt = internos.reduce((a, r) => a + r.total, 0);
      const con2fa = internos.reduce((a, r) => a + r.con_2fa, 0);
      document.getElementById('res-seguridad').innerHTML = `<ul class="lista-simple">
        <li><span>Equipos con dos pasos</span><span><b>${totalInt ? Math.round(con2fa / totalInt * 100) : 0}%</b> <small style="display:inline;">(${esc(con2fa)} de ${esc(totalInt)})</small></span></li>
        <li><span>Sin aceptar términos</span><b>${esc(d.usuarios.sin_terminos)}</b></li>
        <li><span>Invitaciones pendientes</span><b>${esc(d.invitaciones.pendientes)}</b></li>
        <li><span>Invitaciones vencidas</span><b>${esc(d.invitaciones.vencidas)}</b></li>
        <li><span>Invitaciones usadas en 30 días</span><b>${esc(d.invitaciones.usadas_30d)}</b></li></ul>`;
    }

    document.getElementById('res-avisos').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-ir]');
      if (b) abrirPestana(b.dataset.ir);
    });

    const inicial = window.location.hash.replace('#', '');
    abrirPestana(pestanas.includes(inicial) ? inicial : 'resumen');
  }
}
