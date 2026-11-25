const usuario = requireAuth();
if (usuario) {
  pintarTopbar();

  // Saludo y fecha de hoy.
  const ahora = new Date();
  const hora = ahora.getHours();
  const saludo = hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches';
  const nombre = (usuario.nombre || '').trim();  // nombre completo de la persona
  document.getElementById('saludo').textContent = nombre ? `${saludo}, ${nombre}` : saludo;
  document.getElementById('fecha-hoy').textContent = ahora.toLocaleDateString('es-PA',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  if (esPromotor()) document.getElementById('btn-nuevo-panel').style.display = 'none';

  const vacio = (texto) => `<li style="color:var(--ink-faint);">${texto}</li>`;

  // ---------- Primeros pasos (jefe y consultor) ----------
  async function pintarPrimerosPasos(metricas) {
    if (!(esJefe() || esConsultor())) return;
    try { if (localStorage.getItem('pasos_ocultos_' + usuario.email) === '1') return; } catch (e) { /* sin almacenamiento */ }
    let seguridad = null;
    let equipo = null;
    try { seguridad = await apiFetch('/cuenta/seguridad'); } catch (e) { /* se omite el paso */ }
    if (esJefe()) { try { equipo = await apiFetch('/consultores'); } catch (e) { /* se omite el paso */ } }

    const tieneExpediente = !!(metricas && metricas.activos > 0);
    const pasos = [];
    if (esJefe()) {
      pasos.push({ hecho: !!(usuario.empresa && usuario.empresa.logo), titulo: 'Ponga el logo de su consultora',
        texto: 'Su equipo lo verá en el menú y en los resúmenes en PDF.', href: 'empresa.html', boton: 'Mi consultora' });
      if (equipo) pasos.push({ hecho: (equipo.consultores || []).length > 0, titulo: 'Invite a su equipo',
        texto: 'Genere un enlace de invitación para cada consultor.', href: 'equipo.html', boton: 'Equipo' });
    }
    pasos.push({ hecho: tieneExpediente, titulo: 'Registre su primer expediente',
      texto: 'Elija la categoría y el sistema arma la lista de documentos.', href: 'expediente-nuevo.html', boton: 'Nuevo expediente' });
    if (seguridad && seguridad.disponible) pasos.push({ hecho: seguridad.dos_pasos, titulo: 'Active la verificación en dos pasos',
      texto: 'Protege su cuenta aunque alguien conozca la contraseña.', href: 'cuenta.html', boton: 'Mi perfil' });
    pasos.push({ hecho: false, titulo: 'Conozca los atajos y la guía',
      texto: 'Con Ctrl+K busca cualquier expediente en un segundo.', href: 'ayuda.html', boton: 'Ver la ayuda', opcional: true });

    const obligatorios = pasos.filter(p => !p.opcional);
    if (obligatorios.every(p => p.hecho)) return;   // todo listo: la guía ya no hace falta
    document.getElementById('panel-primeros-pasos').hidden = false;
    document.getElementById('pasos-resumen').textContent =
      `${obligatorios.filter(p => p.hecho).length} de ${obligatorios.length} pasos completados.`;
    document.getElementById('lista-pasos').innerHTML = pasos.map((p, i) => `
      <li class="${p.hecho ? 'hecho' : ''}"><span class="n">${p.hecho ? '✓' : i + 1}</span>
        <div><b>${esc(p.titulo)}</b><span>${esc(p.texto)}</span></div>
        ${p.hecho ? '' : `<a class="btn btn-ghost" style="border:1.5px solid var(--line);" href="${esc(p.href)}">${esc(p.boton)}</a>`}</li>`).join('');
    document.getElementById('btn-ocultar-pasos').onclick = () => {
      try { localStorage.setItem('pasos_ocultos_' + usuario.email, '1'); } catch (e) { /* sin almacenamiento */ }
      document.getElementById('panel-primeros-pasos').hidden = true;
    };
  }

  apiFetch('/dashboard').then(d => {
    pintarPrimerosPasos(d.metricas);
    const nums = document.querySelectorAll('.stat .num');
    if (d.metricas && nums.length >= 4) {
      nums[0].textContent = d.metricas.activos;
      nums[1].textContent = d.metricas.pendientes;
      nums[2].textContent = d.metricas.alertas;
      nums[3].textContent = d.metricas.aprobados;
      if (d.metricas.alertas > 0) document.getElementById('stat-alertas').classList.add('alerta');
    }

    // HU-15: solo la consultora ve las prioridades (el cliente no recibe el dato).
    if (Array.isArray(d.prioridades) && (esJefe() || esConsultor())) {
      document.getElementById('panel-prioridades').style.display = 'block';
      const tb = document.getElementById('lista-prioridades');
      tb.innerHTML = d.prioridades.length ? ''
        : '<tr><td colspan="4" class="sin-etiqueta" data-label="" style="padding:22px; color:var(--ink-faint);">No hay expedientes abiertos.</td></tr>';
      d.prioridades.forEach(p => {
        const url = 'expediente-detalle.html?codigo=' + encodeURIComponent(p.codigo);
        tb.innerHTML += `<tr>
          <td data-label="Expediente" style="padding-left:22px;"><div style="display:flex; flex-direction:column; gap:3px;">
            <b style="font-weight:600;">${esc(p.proyecto)}</b><span class="mono" style="font-size:12px; color:var(--ink-faint);">${esc(p.codigo)}</span></div></td>
          <td data-label="Preparación">${celdaIpe({ valor: p.ipe, banda: p.banda, banda_texto: p.banda_texto })}</td>
          <td data-label="Próxima acción">${esc(p.proxima_accion || 'Sin acciones pendientes')}</td>
          <td data-label="" style="text-align:right; padding-right:22px;"><a class="btn btn-ghost" style="min-height:34px; padding:0 12px; font-size:13px;" href="${url}">Abrir</a></td>
        </tr>`;
      });

      const primero = d.prioridades[0];
      if (primero) {
        document.getElementById('panel-urgente').style.display = 'block';
        document.getElementById('urgente-medidor').innerHTML = medidorIpe(primero.ipe, primero.banda, primero.banda_texto);
        document.getElementById('urgente-texto').innerHTML =
          `<b style="color:var(--ink);">Empiece por ${esc(primero.proyecto)}.</b> ${esc(primero.proxima_accion || 'Revise el expediente.')}`;
      }
    }

    const ulR = document.getElementById('lista-recientes');
    ulR.innerHTML = '';
    if (d.recientes && d.recientes.length) {
      d.recientes.forEach(r => {
        ulR.innerHTML += `<li><span><span class="code">${esc(r.codigo)}</span>${esc(r.proyecto)}</span> <span class="${claseEstado(r.estado)}">${textoEstado(r.estado)}</span></li>`;
      });
    } else {
      ulR.innerHTML = vacio('Sin expedientes registrados.');
    }

    // HU-08: avisos de plazo para todos los roles (el cliente incluido).
    const avisos = d.avisos_plazo || [];
    if (avisos.length) {
      document.getElementById('panel-avisos-plazo').style.display = 'block';
      document.getElementById('lista-avisos-plazo').innerHTML = avisos.map(a => {
        const n = a.dias_restantes_legales;
        const unidad = a.base_plazo === 'sometimiento' ? 'días hábiles' : 'días';
        const texto = n < 0 ? `venció hace ${-n} ${unidad}` : n === 0 ? 'vence hoy' : `vence en ${n} ${unidad}`;
        const clase = a.estado_semaforo === 'vencido' ? 'status status-bad' : 'status status-warn';
        const quien = a.base_plazo === 'sometimiento' ? 'Plazo de MiAmbiente' : 'Plazo de preparación';
        return `<li><span><span class="code">${esc(a.codigo)}</span>${esc(a.proyecto)}
            <br><span class="small">${quien}: ${texto}</span></span>
          <span style="display:flex; gap:10px; align-items:center;"><span class="${clase}">${a.estado_semaforo === 'vencido' ? 'Vencido' : 'Por vencer'}</span>
          <a href="expediente-detalle.html?codigo=${encodeURIComponent(a.codigo)}">Ver</a></span></li>`;
      }).join('');
    }
    if (d.aviso_vencimiento_dias) {
      document.getElementById('nota-vencimiento').innerHTML =
        `Le avisamos ${esc(d.aviso_vencimiento_dias)} días antes del vencimiento de cada documento. <a href="cuenta.html">Cambiar</a>`;
    }

    const ulA = document.getElementById('lista-alertas');
    ulA.innerHTML = '';
    if (d.alertas && d.alertas.length) {
      d.alertas.forEach(a => {
        ulA.innerHTML += `<li>
          <span><span class="code">${esc(a.codigo)}</span>${esc(a.descripcion)}</span>
          <a href="expediente-detalle.html?codigo=${encodeURIComponent(a.codigo)}">Ver</a>
        </li>`;
      });
    } else {
      ulA.innerHTML = vacio(`Ningún documento vence en los próximos ${esc(d.aviso_vencimiento_dias || 30)} días.`);
    }
  }).catch(console.error);
}
