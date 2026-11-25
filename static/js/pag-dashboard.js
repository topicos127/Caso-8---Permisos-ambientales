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

  // ---------- Graficos del panel ----------
  const COLOR_ESTADO = { pendiente: '#e09a1a', aprobado_interno: '#7c5ac8', evaluacion: '#3b6bea', aprobado: '#1f9d67', rechazado: '#e04b3f' };
  const NOMBRE_ESTADO = { pendiente: 'Pendiente de subsanación', aprobado_interno: 'Aprobado internamente', evaluacion: 'En evaluación', aprobado: 'Aprobado', rechazado: 'Rechazado' };
  function widget(titulo, nota, cuerpo, ancho) {
    return `<section class="widget${ancho ? ' doble' : ''}"><header><h3>${esc(titulo)}</h3>${nota ? `<p>${esc(nota)}</p>` : ''}</header>${cuerpo}</section>`;
  }

  function pintarGraficos(gr, metricas) {
    if (!gr) return;
    const cont = document.getElementById('widgets');
    const total = Object.values(gr.por_estado || {}).reduce((a, n) => a + n, 0);
    if (!total) return;
    const piezas = [];

    const estados = Object.keys(COLOR_ESTADO).filter(k => gr.por_estado[k]).map(k => ({ etiqueta: NOMBRE_ESTADO[k], valor: gr.por_estado[k], color: COLOR_ESTADO[k] }));
    piezas.push(widget('Expedientes por estado', `${total} en total`, graficoDona(estados, String(total), 'expedientes')));

    const s = gr.por_semaforo || {};
    const abiertos = (s.en_plazo || 0) + (s.por_vencer || 0) + (s.vencido || 0);
    piezas.push(widget('Plazos en trámite', abiertos ? `${abiertos} expediente(s) con plazo en curso` : 'Ninguno en curso',
      graficoDona([{ etiqueta: 'En plazo', valor: s.en_plazo || 0, color: '#2fa66b' },
                   { etiqueta: 'Por vencer', valor: s.por_vencer || 0, color: '#f08a1c' },
                   { etiqueta: 'Vencidos', valor: s.vencido || 0, color: '#ef4444' }], String(abiertos), 'en curso')));

    if (gr.ipe_bandas) {
      const b = gr.ipe_bandas;
      piezas.push(widget('Preparación (IPE)', 'Promedio de los expedientes en trámite',
        `<div class="ipe-resumen"><div class="ipe-promedio"><b>${esc(gr.ipe_promedio ?? '—')}</b><span>/100</span></div>
          ${graficoDona([{ etiqueta: 'Listos (80+)', valor: b.listo, color: '#1f9d67' },
                         { etiqueta: 'En preparación', valor: b.en_preparacion, color: '#e09a1a' },
                         { etiqueta: 'En riesgo (<50)', valor: b.en_riesgo, color: '#e04b3f' }], '', '')}</div>`));
    }

    if (gr.por_consultor && gr.por_consultor.length) {
      const max = Math.max(...gr.por_consultor.map(c => c.total), 1);
      piezas.push(widget('Carga por consultor', 'Expedientes de cada persona (el tono fuerte es lo que sigue en trámite)',
        gr.por_consultor.map(c => `<div class="barra-fila"><div class="barra-cab"><span><span class="avatar-mini" style="background:${colorDe(c.nombre)};">${esc(iniciales(c.nombre))}</span> ${esc(c.nombre)}</span><b>${esc(c.total)}</b></div>
          <div class="barra-pista"><div class="barra-relleno" style="width:${Math.round(c.total / max * 100)}%; background:${colorDe(c.nombre)}55;"><div class="barra-relleno" style="width:${c.total ? Math.round(c.en_tramite / c.total * 100) : 0}%; background:${colorDe(c.nombre)};"></div></div></div></div>`).join('')));
    }

    if (gr.actividad && gr.actividad.some(a => a.n)) {
      const suma = gr.actividad.reduce((a, p) => a + p.n, 0);
      piezas.push(widget('Actividad de la consultora', `${suma} acciones en 14 días`, graficoBarrasDia(gr.actividad, `${suma} acciones en los últimos 14 días`), true));
    }
    cont.innerHTML = piezas.join('');
    cont.hidden = false;
  }

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
    pintarGraficos(d.graficos, d.metricas);
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
        const uno = Math.abs(n) === 1;
        const unidad = a.base_plazo === 'sometimiento' ? (uno ? 'día hábil' : 'días hábiles') : (uno ? 'día' : 'días');
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
