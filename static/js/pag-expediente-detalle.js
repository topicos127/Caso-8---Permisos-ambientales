const usuario = requireAuth();
if (usuario) {
  pintarTopbar();

  const params = new URLSearchParams(window.location.search);
  const codigo = params.get('codigo') || 'SP-A8-2026-001';
  const esPromotorUsuario = esPromotor();

  // HU-14: el director de proyectos y los consultores ven el historial; el cliente no.
  if (!esPromotorUsuario) {
    const linkHistorial = document.getElementById('link-historial');
    linkHistorial.href = 'historial.html?codigo=' + encodeURIComponent(codigo);
    linkHistorial.style.display = 'inline-flex';
  }

  let estadoExpedienteActual = 'pendiente';

  const CARPETAS_POR_CAT_LOCAL = {
    "I":   ["Línea Base", "Plan de Manejo", "Anexos Legales"],
    "II":  ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía"],
    "III": ["Línea Base", "Plan de Manejo", "Anexos Legales", "Cartografía", "Evidencia Foro Público"],
  };

  function mensaje(texto, tipo) {
    const el = document.getElementById('upload-status');
    el.textContent = texto;
    el.className = 'doc-msg show ' + (tipo === 'error' ? 'error' : 'ok');
    if (!texto) el.className = 'doc-msg';
  }

  function formatearTamano(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  function renderDocumentos(docs) {
    const ul = document.getElementById('lista-docs');
    ul.innerHTML = '';

    docs.forEach(doc => {
      const recibido = doc.estado === 'recibido' && doc.archivo_nombre;
      const editable = estadoExpedienteActual === 'pendiente' && !esPromotorUsuario;

      const li = document.createElement('li');
      li.style.display = 'block';
      li.style.padding = '14px 0';

      const header = document.createElement('div');
      header.style.display = 'flex';
      header.style.alignItems = 'center';
      header.style.justifyContent = 'space-between';
      header.style.flexWrap = 'wrap';  // HU-12: en celular las acciones pasan a otra linea
      header.style.gap = '10px 14px';

      const nombre = document.createElement('span');
      nombre.className = 'name';
      nombre.textContent = doc.carpeta;

      const acciones = document.createElement('div');
      acciones.style.display = 'flex';
      acciones.style.gap = '8px';
      acciones.style.flexWrap = 'wrap';
      acciones.style.alignItems = 'center';

      if (recibido) {
        const tagOk = document.createElement('span');
        tagOk.className = 'tag-ok';
        tagOk.textContent = 'Recibido';
        acciones.appendChild(tagOk);

        const btnDesc = document.createElement('a');
        btnDesc.className = 'btn btn-ghost';
        btnDesc.style.padding = '6px 12px';
        btnDesc.style.fontSize = '12.5px';
        btnDesc.style.border = '1px solid var(--line)';
        btnDesc.textContent = 'Descargar';
        btnDesc.href = `/expedientes/${codigo}/documentos/${encodeURIComponent(doc.carpeta)}/descargar`;
        btnDesc.setAttribute('download', doc.archivo_nombre);
        btnDesc.addEventListener('click', async (ev) => {
          ev.preventDefault();
          try {
            const resp = await fetch(btnDesc.href, {
              headers: cabecerasApi(),
              credentials: 'same-origin'
            });
            if (!resp.ok) {
              mensaje('No se pudo descargar el archivo.', 'error');
              return;
            }
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = doc.archivo_nombre;
            a.click();
            URL.revokeObjectURL(url);
          } catch (e) {
            mensaje('Error de red al descargar.', 'error');
          }
        });
        acciones.appendChild(btnDesc);

        if (editable) {
          const inputReempl = document.createElement('input');
          inputReempl.type = 'file';
          inputReempl.accept = '.pdf,.zip';
          inputReempl.style.display = 'none';
          inputReempl.addEventListener('change', () => subirArchivo(doc.carpeta, inputReempl));

          const btnReemp = document.createElement('button');
          btnReemp.className = 'btn btn-ghost';
          btnReemp.style.padding = '6px 12px';
          btnReemp.style.fontSize = '12.5px';
          btnReemp.style.border = '1px solid var(--line)';
          btnReemp.textContent = 'Nueva versión';
          btnReemp.title = 'Los documentos no se eliminan: cada corrección es una versión nueva.';
          btnReemp.addEventListener('click', () => inputReempl.click());

          acciones.appendChild(btnReemp);
          acciones.appendChild(inputReempl);
        }


        // HU-01: historial de versiones (nunca se eliminan).
        const btnVers = document.createElement('button');
        btnVers.className = 'btn btn-ghost';
        btnVers.style.padding = '6px 12px';
        btnVers.style.fontSize = '12.5px';
        btnVers.style.border = '1px solid var(--line)';
        btnVers.textContent = 'Versiones';
        btnVers.addEventListener('click', () => alternarVersiones(doc.carpeta, li));
        acciones.appendChild(btnVers);
      } else {
        const tagMissing = document.createElement('span');
        tagMissing.className = 'tag-missing';
        tagMissing.textContent = 'Pendiente';
        acciones.appendChild(tagMissing);

        if (editable) {
          const inputSubir = document.createElement('input');
          inputSubir.type = 'file';
          inputSubir.accept = '.pdf,.zip';
          inputSubir.style.display = 'none';
          inputSubir.addEventListener('change', () => subirArchivo(doc.carpeta, inputSubir));

          const btnSubir = document.createElement('button');
          btnSubir.className = 'btn btn-brass';
          btnSubir.style.padding = '6px 12px';
          btnSubir.style.fontSize = '12.5px';
          btnSubir.textContent = 'Subir archivo';
          btnSubir.addEventListener('click', () => inputSubir.click());

          acciones.appendChild(btnSubir);
          acciones.appendChild(inputSubir);
        }
      }

      header.appendChild(nombre);
      header.appendChild(acciones);
      li.appendChild(header);

      if (recibido && doc.archivo_nombre) {
        const info = document.createElement('div');
        info.style.fontFamily = 'var(--mono)';
        info.style.fontSize = '11.5px';
        info.style.color = 'var(--ink-faint)';
        info.style.marginTop = '6px';
        info.textContent = `↳ ${doc.archivo_nombre}${doc.archivo_tamano ? ' · ' + formatearTamano(doc.archivo_tamano) : ''}${doc.fecha_subida ? ' · ' + doc.fecha_subida : ''}`;
        li.appendChild(info);

        // HU-05 (Sprint 10): vencimiento real del documento, o estimado a un año.
        if (doc.vence) {
          const vence = document.createElement('div');
          vence.style.fontSize = '12.5px';
          vence.style.marginTop = '4px';
          const dias = doc.dias_para_vencer;
          const aviso = dias != null && dias < 30;
          vence.style.color = dias != null && dias < 0 ? 'var(--status-bad)' : aviso ? 'var(--status-warn)' : 'var(--ink-faint)';
          vence.style.fontWeight = aviso ? '600' : '400';
          const cuando = dias < 0 ? `venció hace ${-dias} días` : `vence el ${doc.vence} (en ${dias} días)`;
          vence.textContent = (doc.vencimiento_real ? 'Vigencia: ' : 'Vigencia estimada: ') + cuando;
          li.appendChild(vence);
        }

        if (doc.codigo_trazabilidad) {
          const traza = document.createElement('div');
          traza.style.fontFamily = 'var(--mono)';
          traza.style.fontSize = '11.5px';
          traza.style.color = 'var(--ink-soft)';
          traza.style.marginTop = '3px';
          traza.textContent = `Versión ${doc.version} · Código de trazabilidad: ${doc.codigo_trazabilidad}`;
          li.appendChild(traza);
        }
      }

      ul.appendChild(li);
    });
  }

  async function descargarArchivo(url, nombre) {
    try {
      const resp = await fetch(url, { headers: cabecerasApi(), credentials: 'same-origin' });
      if (!resp.ok) {
        mensaje('No se pudo descargar el archivo.', 'error');
        return;
      }
      const blobUrl = URL.createObjectURL(await resp.blob());
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = nombre;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch (e) {
      mensaje('Error de red al descargar.', 'error');
    }
  }

  async function alternarVersiones(carpeta, li) {
    const previo = li.querySelector('.lista-versiones');
    if (previo) { previo.remove(); return; }
    const caja = document.createElement('div');
    caja.className = 'lista-versiones';
    caja.style.margin = '10px 0 0 14px';
    caja.style.fontSize = '12.5px';
    caja.textContent = 'Cargando versiones...';
    li.appendChild(caja);
    try {
      const data = await apiFetch(`/expedientes/${codigo}/documentos/${encodeURIComponent(carpeta)}/versiones`);
      const versiones = data.versiones || [];
      if (!versiones.length) {
        caja.textContent = 'Sin versiones registradas.';
        return;
      }
      caja.innerHTML = '';
      versiones.forEach((v, i) => {
        const fila = document.createElement('div');
        fila.style.display = 'flex';
        fila.style.flexWrap = 'wrap';
        fila.style.gap = '10px';
        fila.style.alignItems = 'center';
        fila.style.padding = '4px 0';
        fila.style.borderTop = i ? '1px dashed var(--line)' : 'none';
        fila.innerHTML = `<b>v${esc(v.version)}</b>${i === 0 ? ' <span class="tag-ok">Vigente</span>' : ''}
          <span style="font-family:var(--mono);">${esc(v.codigo_trazabilidad)}</span>
          <span style="color:var(--ink-faint);">${esc(v.archivo_nombre)} · ${esc(formatearTamano(v.archivo_tamano))} · ${esc(v.fecha_subida || '')}${v.subido_por ? ' · ' + esc(v.subido_por) : ''}</span>`;
        if (v.sha256) fila.title = 'SHA-256: ' + v.sha256;
        const enlace = document.createElement('a');
        enlace.href = '#';
        enlace.textContent = 'Descargar';
        enlace.addEventListener('click', ev => {
          ev.preventDefault();
          descargarArchivo(`/expedientes/${codigo}/documentos/${encodeURIComponent(carpeta)}/versiones/${v.version}/descargar`,
                           v.archivo_nombre);
        });
        fila.appendChild(enlace);
        caja.appendChild(fila);
      });
    } catch (e) {
      caja.textContent = 'No se pudieron cargar las versiones.';
    }
  }

  function renderVerificacion(verif) {
    const panel = document.getElementById('panel-verificacion');
    const resumen = document.getElementById('verif-resumen');
    const lista = document.getElementById('verif-lista');
    const warn = document.getElementById('verif-warn');
    const ok = document.getElementById('verif-ok');

    panel.style.display = 'block';
    lista.innerHTML = '';

    resumen.innerHTML = `<span class="tier"><b>${esc(verif.categoria)}</b> ${esc(verif.completos)} de ${esc(verif.total_requeridos)} documentos obligatorios completos</span>`;

    const requeridos = CARPETAS_POR_CAT_LOCAL[verif.categoria] || [];
    requeridos.forEach(carpeta => {
      const completo = !verif.faltantes.includes(carpeta);
      lista.innerHTML += `
        <li>
          <span class="name">${carpeta}</span>
          <span class="${completo ? 'tag-ok' : 'tag-missing'}">${completo ? 'Completo' : 'Falta'}</span>
        </li>
      `;
    });

    if (verif.puede_someter) {
      warn.style.display = 'none';
      ok.className = 'doc-msg show ok';
      ok.textContent = 'Todos los documentos obligatorios están completos.';
    } else {
      warn.style.display = 'block';
      ok.className = 'doc-msg';
      ok.textContent = '';
    }
  }

  let resolucionActual = null;
  let observacionesActuales = [];

  function pintarObservaciones() {
    const cont = document.getElementById('observaciones-lista');
    if (!observacionesActuales.length) { cont.innerHTML = ''; return; }
    cont.innerHTML = '<h4 style="margin-bottom:8px;">Observaciones del director</h4>' + observacionesActuales.map(o =>
      `<div style="margin-top:8px; padding:12px 14px; background:var(--status-warn-bg); border-radius:12px;">
        <div style="font-size:12px; color:var(--status-warn); font-weight:600;">${esc(o.fecha)} · ${esc(o.autor || 'Director')}</div>
        <div style="margin-top:4px; font-size:14px;">${esc(o.texto)}</div>
      </div>`).join('');
  }

  function textoResolucion(r) {
    return r ? `Resolución ${r.numero} del ${r.fecha_resolucion}${r.registrado_por ? ', registrada por ' + r.registrado_por : ''}.` : '';
  }

  async function renderAprobacion(estado, verif) {
    const panel = document.getElementById('panel-aprobacion');
    const note = document.getElementById('aprobacion-note');
    const formDiv = document.getElementById('aprobacion-form');
    const avisoFaltantes = document.getElementById('aprobacion-aviso-faltantes');
    const infoDiv = document.getElementById('aprobacion-info');
    const btnSometerDiv = document.getElementById('aprobacion-btn-someter');
    const btnSimularDiv = document.getElementById('aprobacion-btn-simular');
    const completaDiv = document.getElementById('aprobacion-completa');
    const rechazadaDiv = document.getElementById('aprobacion-rechazada');
    const devolverDiv = document.getElementById('devolver-form');

    rechazadaDiv.style.display = 'none';
    devolverDiv.style.display = 'none';
    pintarObservaciones();
    if (resolucionActual) {
      document.getElementById('resolucion-aprobado').textContent = textoResolucion(resolucionActual);
      document.getElementById('resolucion-rechazado').textContent = textoResolucion(resolucionActual);
    }
    // Sprint 10: el director de proyectos puede devolver lo que aún no se ha sometido.
    if (!esPromotorUsuario && esJefe() && (estado === 'pendiente' || estado === 'aprobado_interno')) {
      devolverDiv.style.display = 'block';
    }

    formDiv.style.display = 'none';
    avisoFaltantes.style.display = 'none';
    infoDiv.innerHTML = '';
    btnSometerDiv.style.display = 'none';
    btnSimularDiv.style.display = 'none';
    completaDiv.style.display = 'none';

    if (esPromotorUsuario) {
      if (estado === 'pendiente') {
        note.textContent = 'El consultor aún no ha completado los documentos.';
      } else if (estado === 'aprobado_interno') {
        note.textContent = 'El expediente fue aprobado internamente. Pronto será sometido a MiAmbiente.';
      } else if (estado === 'evaluacion') {
        note.textContent = 'El expediente está en evaluación por MiAmbiente.';
      } else if (estado === 'aprobado') {
        note.textContent = 'El expediente fue aprobado por MiAmbiente.';
        completaDiv.style.display = 'block';
      } else if (estado === 'rechazado') {
        note.textContent = 'MiAmbiente emitió su resolución.';
        rechazadaDiv.style.display = 'block';
      }
      await cargarRegistroAprobaciones(infoDiv);
      return;
    }

    if (estado === 'pendiente') {
      if (verif && verif.puede_someter && esJefe()) {
        note.textContent = 'Todos los documentos están completos. Puedes aprobar internamente el expediente.';
        formDiv.style.display = 'block';
      } else if (verif && verif.puede_someter) {
        // HU-13: la aprobación interna es solo del director de proyectos.
        note.textContent = 'Todos los documentos están completos. Falta la aprobación interna del director de proyectos.';
      } else {
        note.textContent = 'Aprueba internamente el expediente antes de someterlo a MiAmbiente.';
        avisoFaltantes.style.display = 'block';
      }
    } else if (estado === 'aprobado_interno') {
      note.innerHTML = '<span style="color:var(--status-ok);">Expediente aprobado internamente.</span> Listo para someter a MiAmbiente.';
      btnSometerDiv.style.display = 'block';
      await cargarRegistroAprobaciones(infoDiv);
    } else if (estado === 'evaluacion') {
      note.textContent = 'El expediente fue sometido a MiAmbiente. Está en evaluación.';
      btnSimularDiv.style.display = 'block';
      const fechaRes = document.getElementById('res-fecha');
      fechaRes.max = new Date().toISOString().slice(0, 10);
      await cargarRegistroAprobaciones(infoDiv);
    } else if (estado === 'aprobado') {
      note.textContent = 'Expediente aprobado por MiAmbiente.';
      completaDiv.style.display = 'block';
      await cargarRegistroAprobaciones(infoDiv);
    } else if (estado === 'rechazado') {
      note.textContent = 'MiAmbiente emitió su resolución.';
      rechazadaDiv.style.display = 'block';
      await cargarRegistroAprobaciones(infoDiv);
    }
  }

  // Sprint 9 (HU-09 y opción a del registro): el director de proyectos publica o retira el
  // proyecto de la consulta pública; el consultor o el director de proyectos crean la cuenta
  // del cliente con una contraseña temporal que se muestra una sola vez.
  function renderAcceso(e) {
    if (esPromotorUsuario) return;
    document.getElementById('panel-acceso').style.display = 'block';

    document.getElementById('acceso-estado').textContent = e.acceso_publico
      ? 'Visible en la consulta pública: proyecto, promotor, categoría, estado y consultor responsable.'
      : 'No visible en la consulta pública: el sistema no entrega ningún dato del proyecto.';
    const btnAcceso = document.getElementById('btnAcceso');
    if (esJefe()) {
      btnAcceso.style.display = 'inline-block';
      btnAcceso.textContent = e.acceso_publico ? 'Retirar de la consulta pública' : 'Publicar en la consulta pública';
      btnAcceso.onclick = async () => {
        const r = await apiFetch(`/expedientes/${codigo}/acceso-publico`, {
          method: 'POST',
          body: JSON.stringify({ acceso_publico: !e.acceso_publico })
        });
        if (r.ok) {
          mostrarToast(r.acceso_publico ? 'Proyecto publicado.' : 'Proyecto retirado de la consulta pública.', 'exito');
          setTimeout(() => location.reload(), 1200);
        } else {
          mostrarToast(r.mensaje || 'No se pudo cambiar el acceso.', 'error');
        }
      };
    }

    const nota = document.getElementById('promotor-nota');
    const btnCuenta = document.getElementById('btnCuentaPromotor');
    if (!e.promotor_email) {
      nota.textContent = 'El expediente no tiene correo de cliente, así que no se le puede dar acceso.';
      return;
    }
    nota.textContent = `El cliente entra con ${e.promotor_email}. Su cuenta no se crea por registro público: la crea su consultor desde aquí.`;
    btnCuenta.style.display = 'inline-block';
    const btnReset = document.getElementById('btnResetPromotor');
    btnReset.style.display = 'inline-block';
    btnReset.onclick = async () => {
      if (!(await confirmar('Restablecer contraseña',
        `Se genera una contraseña temporal nueva para ${e.promotor_email} y se cierran sus sesiones. La verá una sola vez.`, 'Restablecer'))) return;
      const r = await apiFetch(`/expedientes/${codigo}/promotor/clave`, { method: 'POST', body: '{}' });
      if (!r.ok) { mostrarToast(r.mensaje || 'No se pudo restablecer.', 'error'); return; }
      abrirModal({
        titulo: 'Contraseña temporal',
        html: `<p class="aviso-unico">Entréguela al cliente por un canal seguro. No se vuelve a mostrar.</p>
          <p style="margin-top:12px;">${esc(r.email)}</p><code class="clave-manual">${esc(r.password_temporal)}</code>`,
        cerrable: false,
        acciones: [
          { texto: 'Copiar', clase: 'btn btn-ghost', alHacerClic: () => { copiarTexto(r.password_temporal, 'Contraseña copiada.'); return false; } },
          { texto: 'Listo', clase: 'btn btn-brass' },
        ],
      });
    };
    btnCuenta.onclick = async () => {
      if (!confirm(`¿Crear el acceso de ${e.promotor_email}? Verás una contraseña temporal una sola vez.`)) return;
      const r = await apiFetch(`/expedientes/${codigo}/promotor/cuenta`, { method: 'POST', body: '{}' });
      const salida = document.getElementById('promotor-resultado');
      salida.replaceChildren();
      if (r.ok) {
        salida.className = 'doc-msg show ok';
        const titulo = document.createElement('div');
        titulo.textContent = 'Acceso creado. Entregue estos datos al cliente por un canal seguro; se muestran una sola vez:';
        const datos = document.createElement('div');
        datos.style.cssText = 'margin-top:8px; font-family:var(--mono);';
        datos.textContent = `${r.email} · ${r.password_temporal}`;
        const aviso = document.createElement('div');
        aviso.style.marginTop = '8px';
        aviso.textContent = 'El cliente debe cambiarla en «Mi cuenta» al entrar.';
        salida.append(titulo, datos, aviso);
        btnCuenta.style.display = 'none';
      } else {
        salida.className = 'doc-msg show error';
        salida.textContent = r.mensaje || 'No se pudo crear el acceso.';
      }
    };
  }

  // Responsable del expediente: lo ve la consultora; solo el director de proyectos lo cambia.
  async function renderResponsable(resp) {
    if (esPromotorUsuario || !resp) return;
    document.getElementById('fact-responsable-caja').style.display = '';
    const cont = document.getElementById('fact-responsable');
    cont.textContent = resp.nombre;
    if (!esJefe()) return;
    try {
      const d = await apiFetch('/consultores');
      const activos = (d.consultores || []).filter(c => c.activo);
      if (!activos.length) return;
      cont.innerHTML = `<span id="resp-nombre"></span>
        <select id="select-responsable" aria-label="Nuevo responsable">${activos.map(c =>
          `<option value="${esc(c.id)}"${c.id === resp.id ? ' selected' : ''}>${esc(c.nombre)}</option>`).join('')}</select>
        <button type="button" class="btn btn-ghost" id="btn-responsable" style="border:1.5px solid var(--line); padding:4px 12px;">Cambiar</button>`;
      cont.querySelector('#resp-nombre').textContent = activos.some(c => c.id === resp.id) ? '' : resp.nombre;
      cont.querySelector('#btn-responsable').onclick = async () => {
        const nuevo = Number(cont.querySelector('#select-responsable').value);
        if (nuevo === resp.id) { mostrarToast('Ya es la persona responsable.', 'error'); return; }
        const r = await apiFetch(`/expedientes/${codigo}/responsable`, { method: 'POST', body: JSON.stringify({ usuario_id: nuevo }) });
        mostrarToast(r.mensaje || (r.ok ? 'Responsable actualizado.' : 'No se pudo cambiar.'), r.ok ? 'exito' : 'error');
        if (r.ok) setTimeout(() => location.reload(), 900);
      };
    } catch (err) { console.error(err); }
  }

  // Comentarios internos del equipo.
  async function cargarComentarios() {
    if (esPromotorUsuario) return;
    document.getElementById('panel-comentarios').style.display = 'block';
    const d = await apiFetch(`/expedientes/${codigo}/comentarios`);
    const lista = document.getElementById('lista-comentarios');
    lista.innerHTML = (d.comentarios || []).length
      ? d.comentarios.map(c => `<div class="comentario"><div class="cab"><b>${esc(c.autor)}</b><span>${esc(ROL_TEXTO[c.autor_rol] || c.autor_rol)} · ${esc(c.fecha)}</span></div><p>${esc(c.texto)}</p></div>`).join('')
      : '<p class="panel-note" style="margin:0;">Todavía no hay comentarios.</p>';
  }

  document.getElementById('form-comentario').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const campo = document.getElementById('texto-comentario');
    const texto = campo.value.trim();
    if (!texto) { mostrarToast('Escriba el comentario.', 'error'); return; }
    const r = await apiFetch(`/expedientes/${codigo}/comentarios`, { method: 'POST', body: JSON.stringify({ texto }) });
    if (r.ok) { campo.value = ''; mostrarToast('Comentario publicado.', 'exito'); await cargarComentarios(); }
    else mostrarToast(r.mensaje || 'No se pudo publicar.', 'error');
  });

  // HU-15: el IPE y sus proximas acciones; el servidor solo lo envia a la consultora.
  function renderIpe(ipe) {
    const panel = document.getElementById('panel-ipe');
    if (!ipe) { panel.style.display = 'none'; return; }
    panel.style.display = 'block';
    document.getElementById('ipe-valor').innerHTML = medidorIpe(ipe.ipe, ipe.banda, ipe.banda_texto);
    const bandaDe = (v) => v >= 80 ? 'listo' : v >= 50 ? 'en_preparacion' : 'en_riesgo';
    const factor = (id, nombre, valor, peso, detalle) => {
      document.getElementById(id).innerHTML = anilloIpe(valor, bandaDe(valor))
        + `<div class="txt"><b>${nombre} · ${esc(valor)}</b><span>${detalle}</span></div>`
        + `<span class="chip">Peso ${peso}%</span>`;
    };
    const c = ipe.componentes;
    factor('ipe-documentos', 'Documentos', c.documentos, 50, 'Recibidos de los requeridos');
    factor('ipe-plazo', 'Plazo', c.plazo, 30, c.plazo === 100 ? 'En plazo o resuelto' : c.plazo === 50 ? 'Por vencer' : 'Vencido');
    factor('ipe-vigencia', 'Vigencia', c.vigencia, 20, c.vigencia === 100 ? 'Nada vence en 30 días' : 'Hay documentos por vencer');
    const ul = document.getElementById('ipe-acciones');
    ul.innerHTML = ipe.acciones.length
      ? ipe.acciones.map(a => `<li>${esc(a.texto)}</li>`).join('')
      : '<li style="color:var(--ink-faint);">No hay acciones pendientes.</li>';
  }

  async function cargarRegistroAprobaciones(infoDiv) {
    try {
      const ap = await apiFetch('/expedientes/' + codigo + '/aprobaciones');
      if (ap.aprobaciones && ap.aprobaciones.length) {
        infoDiv.innerHTML = ap.aprobaciones.map(a =>
          `<div style="margin-top:10px; padding:12px 14px; background:var(--surface-2); border-radius:12px;">
            <div style="font-family:var(--mono); font-size:11px; color:var(--ink-faint);">${esc(a.fecha)} · ${esc(a.aprobado_por_nombre || 'Usuario')}</div>
            <div style="margin-top:4px; font-size:14px;">${esc(a.motivo)}</div>
          </div>`
        ).join('');
      }
    } catch (err) { /* ignorar */ }
  }

  // HU-07: el backend decide el estado del semaforo (en_plazo, por_vencer,
  // vencido o resuelto) y el limite de la categoria. Aqui solo se pinta.
  const SEMAFORO = {
    en_plazo:   { clase: 'status status-ok',      texto: 'En plazo',   color: '#1f9d67' },
    por_vencer: { clase: 'status status-warn',    texto: 'Por vencer', color: '#e09a1a' },
    vencido:    { clase: 'status status-bad',     texto: 'Vencido',    color: '#e04b3f' },
    resuelto:   { clase: 'status status-neutral', texto: 'Resuelto',   color: '#c9cfcb' },
  };

  function renderPlazos(alertas) {
    const panel = document.getElementById('panel-plazos');
    panel.style.display = 'block';

    const sem = SEMAFORO[alertas.estado_semaforo] || SEMAFORO.en_plazo;
    const resuelto = alertas.estado_semaforo === 'resuelto';
    const limite = alertas.limite_dias;

    document.getElementById('plazo-categoria').innerHTML = fichaTier(alertas.categoria);
    document.getElementById('plazo-transcurridos').textContent =
      resuelto ? '—' : alertas.dias_transcurridos + ' días';
    document.getElementById('plazo-restantes').textContent =
      resuelto ? '—' : alertas.dias_restantes_legales + ' días';
    document.getElementById('plazo-estado').innerHTML = `<span class="${sem.clase}">${sem.texto}</span>`;

    const nota = document.getElementById('plazo-nota');
    const fmt = (iso) => iso ? iso.split('-').reverse().join('/') : '';
    const habiles = alertas.base_plazo === 'sometimiento';
    if (!resuelto) {
      const unidad = habiles ? ' días hábiles' : ' días';
      document.getElementById('plazo-transcurridos').textContent = alertas.dias_transcurridos + unidad;
      document.getElementById('plazo-restantes').textContent = alertas.dias_restantes_legales + unidad;
    }
    document.getElementById('plazo-desde').textContent = habiles ? 'Sometimiento' : 'Ingreso';
    const linkCal = document.getElementById('link-calendario');
    linkCal.href = `/expedientes/${encodeURIComponent(codigo)}/plazos.ics`;
    linkCal.setAttribute('download', `${codigo}_plazos.ics`);
    if (nota) {
      // HU-08 (Sprint 10): el plazo de MiAmbiente corre en días hábiles desde el sometimiento.
      nota.textContent = resuelto
        ? 'El expediente ya fue resuelto: el plazo dejó de correr.'
        : habiles
          ? `Plazo de MiAmbiente: ${limite} días hábiles desde el sometimiento (${fmt(alertas.fecha_inicio)}), sin fines de semana ni feriados. Vence el ${fmt(alertas.fecha_limite)}. Se marca "Por vencer" cuando quedan ${alertas.umbral_por_vencer} días hábiles o menos.`
          : `Aún no se somete: se mide la preparación en días calendario desde el ingreso (${limite} días, hasta el ${fmt(alertas.fecha_limite)}). Al someter, el plazo de MiAmbiente corre en días hábiles.`;
    }

    const barra = document.getElementById('plazo-barra');
    const porcentaje = resuelto
      ? 100
      : Math.min(100, Math.max(0, (alertas.dias_transcurridos / limite) * 100));
    barra.style.background = sem.color;
    barra.style.width = porcentaje + '%';
  }

  async function cargarExpediente() {
    try {
      const d = await apiFetch('/expedientes/' + codigo);
      const e = d.expediente;

      estadoExpedienteActual = e.estado;

      document.getElementById('titulo-exp').innerHTML =
        `<span class="case-tag" style="font-size:16px; margin-right:10px; vertical-align:2px;">${esc(e.codigo)}</span>${esc(e.proyecto)}`;
      document.getElementById('fact-estado').innerHTML =
        `<span class="${claseEstado(e.estado)}">${textoEstado(e.estado)}</span>`;
      document.getElementById('fact-categoria').innerHTML = fichaTier(e.categoria);
      document.getElementById('fact-promotor').textContent = e.promotor;
      document.getElementById('fact-fecha').textContent = e.fecha_ingreso;
      renderResponsable(d.responsable);
      cargarComentarios();

      // Pintar la Línea de Tiempo (Timeline)
      const pasos = {
        'pendiente': ['step-creado'],
        'aprobado_interno': ['step-creado', 'step-interno'],
        'evaluacion': ['step-creado', 'step-interno', 'step-evaluacion'],
        'aprobado': ['step-creado', 'step-interno', 'step-evaluacion', 'step-aprobado'],
        'rechazado': ['step-creado', 'step-interno', 'step-evaluacion']
      };
      
      // Etapas alcanzadas en verde; la siguiente, en curso.
      const pasosActivos = pasos[e.estado] || ['step-creado'];
      const orden = ['step-creado', 'step-interno', 'step-evaluacion', 'step-aprobado'];
      orden.forEach(id => {
        const li = document.getElementById(id).closest('.etapa');
        li.classList.remove('hecha', 'actual');
      });
      pasosActivos.forEach(id => document.getElementById(id).closest('.etapa').classList.add('hecha'));
      const ultima = document.getElementById('step-aprobado').closest('.etapa');
      ultima.classList.remove('rechazada');
      ultima.querySelector('.nombre').textContent = 'Aprobado por MiAmbiente';
      if (e.estado === 'rechazado') {
        // Sprint 10: la resolución puede ser un rechazo.
        ultima.classList.add('rechazada');
        ultima.querySelector('.nombre').textContent = 'Rechazado por MiAmbiente';
      } else {
        const siguiente = orden[pasosActivos.length];
        if (siguiente) document.getElementById(siguiente).closest('.etapa').classList.add('actual');
      }

      resolucionActual = d.resolucion || null;
      observacionesActuales = d.observaciones || [];
      // HU-05: la fecha de vencimiento se pide solo a quien puede subir archivos.
      const campoVence = document.getElementById('campo-vencimiento');
      campoVence.style.display = (!esPromotorUsuario && e.estado === 'pendiente') ? 'block' : 'none';
      const manana = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
      document.getElementById('input-vencimiento').min = manana;

      renderDocumentos(d.documentos);
      renderIpe(d.ipe);

      if (d.verificacion) {
        renderVerificacion(d.verificacion);
      }

      await renderAprobacion(e.estado, d.verificacion);
      renderAcceso(e);

      try {
        const alertas = await apiFetch('/expedientes/' + codigo + '/alertas');
        renderPlazos(alertas);
      } catch (err) {
        console.error('Error al cargar plazos:', err);
      }

      if (esPromotorUsuario) {
        document.getElementById('panel-note-docs').textContent =
          'Consulta el estado de los documentos y descarga los que ya fueron subidos.';
      }
    } catch (e) {
      const panels = ['panel-resumen', 'panel-docs', 'panel-aprobacion', 'panel-verificacion', 'panel-plazos', 'panel-timeline', 'panel-acceso', 'panel-ipe', 'panel-comentarios'];
      panels.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
      });

      const panelDenegado = document.getElementById('panel-denegado');
      if (panelDenegado) panelDenegado.style.display = 'block';

      document.getElementById('titulo-exp').textContent = 'Expediente no disponible';
    }
  }

  async function subirArchivo(carpeta, input) {
    if (!input.files || !input.files[0]) return;
    const archivo = input.files[0];

    const ext = archivo.name.split('.').pop().toLowerCase();
    if (!['pdf', 'zip'].includes(ext)) {
      mensaje('Solo se aceptan archivos PDF y ZIP.', 'error');
      input.value = '';
      return;
    }

    if (archivo.size > 20 * 1024 * 1024) {
      mensaje('El archivo supera el límite de 20 MB.', 'error');
      input.value = '';
      return;
    }

    mensaje(`Subiendo ${archivo.name}...`, 'ok');

    const formData = new FormData();
    formData.append('archivo', archivo);
    const vence = document.getElementById('input-vencimiento');
    if (vence && vence.value) formData.append('fecha_vencimiento', vence.value);

    try {
      const resp = await fetch(
        `/expedientes/${codigo}/documentos/${encodeURIComponent(carpeta)}/subir`,
        {
          method: 'POST',
          headers: cabecerasApi(),
          credentials: 'same-origin',
          body: formData,
        }
      );
      const data = await resp.json();

      if (data.ok) {
        mensaje(`${data.archivo_nombre} subido como versión ${data.version} · ${data.codigo_trazabilidad}`
          + (data.fecha_vencimiento ? ` · vence el ${data.fecha_vencimiento.split('-').reverse().join('/')}` : ''), 'ok');
        if (vence) vence.value = '';
        await cargarExpediente();
      } else {
        mensaje(data.mensaje || 'Error al subir el archivo.', 'error');
      }
    } catch (err) {
      mensaje('Error de red al subir el archivo.', 'error');
    } finally {
      input.value = '';
    }
  }

  document.getElementById('btnZip').addEventListener('click', async () => {
    try {
      const resp = await fetch(`/expedientes/${codigo}/descargar-todo`, {
        headers: cabecerasApi(),
        credentials: 'same-origin'
      });
      if (!resp.ok) {
        mensaje('No se pudo descargar el expediente.', 'error');
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = codigo + '_completo.zip';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      mensaje('Error al descargar el ZIP.', 'error');
    }
  });

  document.getElementById('btnPdf').addEventListener('click', async () => {
    try {
      const d = await apiFetch('/expedientes/' + codigo);
      const e = d.expediente;
      const docs = d.documentos;

      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();

      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.text("Resumen de Expediente", 20, 25);
      
      doc.setFontSize(12);
      doc.setFont("helvetica", "normal");
      
      doc.text("Codigo: " + e.codigo, 20, 40);
      doc.text("Proyecto: " + e.proyecto, 20, 50);
      doc.text("Promotor: " + e.promotor, 20, 60);
      doc.text("Categoria: " + e.categoria, 20, 70);
      doc.text("Estado: " + textoEstado(e.estado), 20, 80);
      doc.text("Fecha de Ingreso: " + e.fecha_ingreso, 20, 90);

      doc.setFont("helvetica", "bold");
      doc.text("Documentos del expediente:", 20, 105);
      
      doc.setFont("helvetica", "normal");
      let y = 115;
      docs.forEach(docItem => {
        const estadoDoc = docItem.estado === 'recibido' ? "Recibido" : "Pendiente";
        doc.text("- " + docItem.carpeta + ": " + estadoDoc, 20, y);
        y += 10;
      });

      doc.save(e.codigo + '-resumen.pdf');
    } catch (err) {
      mensaje('Error al generar el PDF.', 'error');
    }
  });

  const btnAprobar = document.getElementById('btnAprobar');
  if (btnAprobar) {
    btnAprobar.addEventListener('click', async () => {
      const motivo = document.getElementById('input-motivo').value.trim();
      if (!motivo) { mostrarToast('Escribe un motivo.', 'error'); return; }
      const r = await apiFetch(`/expedientes/${codigo}/aprobar`, {
        method: 'POST',
        body: JSON.stringify({ motivo })
      });
      if (r.ok) {
        mostrarToast('Expediente aprobado internamente.', 'exito');
        setTimeout(() => location.reload(), 1500);
      } else {
        mostrarToast(r.mensaje || 'Error al aprobar.', 'error');
      }
    });
  }

  const btnSometer = document.getElementById('btnSometer');
  if (btnSometer) {
    btnSometer.addEventListener('click', async () => {
      if (!confirm('¿Confirmas que quieres someter este expediente a MiAmbiente?')) return;
      const r = await apiFetch(`/expedientes/${codigo}/someter`, {
        method: 'POST',
        body: JSON.stringify({})
      });
      if (r.ok) {
        mostrarToast('Expediente sometido a MiAmbiente.', 'exito');
        setTimeout(() => location.reload(), 1500);
      } else {
        mostrarToast(r.mensaje || 'Error al someter.', 'error');
      }
    });
  }

  // Sprint 10: resolución real de MiAmbiente (resultado, número y fecha).
  const btnResolucion = document.getElementById('btnResolucion');
  if (btnResolucion) {
    btnResolucion.addEventListener('click', async () => {
      const resultado = document.getElementById('res-resultado').value;
      const numero = document.getElementById('res-numero').value.trim();
      const fecha = document.getElementById('res-fecha').value;
      if (!numero || !fecha) { mostrarToast('Escriba el número y la fecha de la resolución.', 'error'); return; }
      const texto = resultado === 'aprobado' ? 'aprobó' : 'rechazó';
      if (!confirm(`¿Registrar que MiAmbiente ${texto} el expediente con la resolución ${numero}?`)) return;
      const r = await apiFetch(`/expedientes/${codigo}/resolucion`, {
        method: 'POST',
        body: JSON.stringify({ resultado, numero, fecha })
      });
      if (r.ok) {
        mostrarToast(r.mensaje || 'Resolución registrada.', 'exito');
        setTimeout(() => location.reload(), 1500);
      } else {
        mostrarToast(r.mensaje || 'No se pudo registrar la resolución.', 'error');
      }
    });
  }

  // Sprint 10: el director de proyectos devuelve el expediente al consultor con observaciones.
  const btnDevolver = document.getElementById('btnDevolver');
  if (btnDevolver) {
    btnDevolver.addEventListener('click', async () => {
      const observaciones = document.getElementById('input-observaciones').value.trim();
      if (!observaciones) { mostrarToast('Escriba qué debe corregir el consultor.', 'error'); return; }
      if (!confirm('¿Devolver el expediente al consultor con estas observaciones?')) return;
      const r = await apiFetch(`/expedientes/${codigo}/devolver`, {
        method: 'POST',
        body: JSON.stringify({ observaciones })
      });
      if (r.ok) {
        mostrarToast(r.mensaje || 'Expediente devuelto.', 'exito');
        setTimeout(() => location.reload(), 1500);
      } else {
        mostrarToast(r.mensaje || 'No se pudo devolver el expediente.', 'error');
      }
    });
  }

  cargarExpediente();
}
