// Seguridad de la cuenta: verificación en dos pasos, códigos de recuperación y cierre de sesiones.
// Las acciones sensibles piden la contraseña actual aunque la sesión esté abierta.
(function () {
  if (!usuario || usuario.debe_cambiar_clave) return;
  const panel = document.getElementById('panel-seguridad');
  let estado = null;

  // Ventana que pide la contraseña (y, si se indica, un código). Devuelve { password, codigo } o null.
  function pedirClave({ titulo, texto, conCodigo = false, boton = 'Continuar', peligro = false }) {
    return new Promise(resolver => {
      let enviado = false;
      abrirModal({
        titulo,
        html: `<p>${esc(texto)}</p>
          <div class="doc-field"><label for="m-clave">Contraseña actual</label>
            <input type="password" id="m-clave" autocomplete="current-password"></div>
          ${conCodigo ? `<div class="doc-field"><label for="m-codigo">Código de su aplicación (o de recuperación)</label>
            <input type="text" id="m-codigo" autocomplete="one-time-code" maxlength="14" spellcheck="false"></div>` : ''}
          <div class="doc-msg" id="m-error" role="alert"></div>`,
        acciones: [
          { texto: 'Cancelar', clase: 'btn btn-ghost', alHacerClic: () => { if (!enviado) resolver(null); } },
          {
            texto: boton, clase: peligro ? 'btn btn-peligro' : 'btn btn-brass',
            alHacerClic: ({ el }) => {
              const password = el.querySelector('#m-clave').value;
              const codigo = conCodigo ? el.querySelector('#m-codigo').value.trim() : '';
              if (!password || (conCodigo && !codigo)) {
                const e = el.querySelector('#m-error');
                e.className = 'doc-msg show error';
                e.textContent = conCodigo ? 'Escriba la contraseña y el código.' : 'Escriba su contraseña actual.';
                return false;
              }
              enviado = true;
              resolver({ password, codigo });
            },
          },
        ],
      });
    });
  }

  // Muestra códigos de recuperación UNA sola vez; no se cierra hasta que la persona confirme que los guardó.
  function mostrarCodigos(codigos, titulo) {
    const texto = codigos.join('\n');
    const modal = abrirModal({
      titulo,
      cerrable: false,
      html: `<p class="aviso-unico">Guárdelos ahora en un lugar seguro. No se vuelven a mostrar.</p>
        <ul class="codigos-lista">${codigos.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
        <p>Cada código sirve una sola vez: para entrar si pierde el teléfono o para fijar una contraseña nueva sin correo.</p>`,
      acciones: [
        { texto: 'Copiar', clase: 'btn btn-ghost', alHacerClic: () => { copiarTexto(texto, 'Códigos copiados.'); return false; } },
        {
          texto: 'Descargar', clase: 'btn btn-ghost',
          alHacerClic: () => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([`Códigos de recuperación — Permisos Ambientales\n${usuario.email}\n\n${texto}\n`], { type: 'text/plain' }));
            a.download = 'codigos-de-recuperacion.txt';
            a.click();
            URL.revokeObjectURL(a.href);
            return false;
          },
        },
        { texto: 'Ya los guardé', clase: 'btn btn-brass' },
      ],
    });
    return modal;
  }

  async function llamar(url, cuerpo) {
    const r = await apiFetch(url, { method: 'POST', body: JSON.stringify(cuerpo || {}) });
    if (!r.ok) mostrarToast(r.mensaje || 'No se pudo completar la acción.', 'error');
    return r;
  }

  function pintar() {
    const dos = document.getElementById('seg-2fa');
    const cod = document.getElementById('seg-codigos');
    const ses = document.getElementById('seg-sesiones');
    if (!estado.disponible) {
      dos.innerHTML = '<h4>Verificación en dos pasos</h4><p class="panel-note">Aún no está disponible en este servidor.</p>';
    } else if (estado.dos_pasos) {
      dos.innerHTML = `<div class="seg-estado"><div><h4>Verificación en dos pasos</h4>
          <span class="status status-ok">Activada</span></div>
          <button type="button" class="btn btn-ghost" id="btn-2fa-quitar" style="border:1.5px solid var(--line);">Desactivar</button></div>
        <p class="panel-note" style="margin:0;">Al entrar le pedimos, además de la contraseña, el código de su aplicación autenticadora.</p>`;
      document.getElementById('btn-2fa-quitar').addEventListener('click', desactivar2fa);
    } else {
      dos.innerHTML = `<div class="seg-estado"><div><h4>Verificación en dos pasos</h4>
          <span class="status status-warn">Desactivada</span></div>
          <button type="button" class="btn btn-brass" id="btn-2fa-activar">Activar</button></div>
        <p class="panel-note" style="margin:0;">Protege su cuenta aunque alguien conozca su contraseña. Funciona con Google Authenticator, Microsoft Authenticator, Authy o 1Password.</p>
        <div id="seg-2fa-pasos"></div>`;
      document.getElementById('btn-2fa-activar').addEventListener('click', preparar2fa);
    }
    cod.innerHTML = `<h4>Códigos de recuperación</h4>
      <p class="panel-note" style="margin:0 0 10px;">${estado.codigos_restantes
        ? `Le quedan <b>${estado.codigos_restantes}</b> código(s) sin usar.`
        : 'No tiene códigos guardados.'} Sirven para recuperar el acceso sin correo electrónico.</p>
      <button type="button" class="btn btn-ghost" id="btn-codigos" style="border:1.5px solid var(--line);">${estado.codigos_restantes ? 'Generar códigos nuevos' : 'Generar códigos'}</button>`;
    document.getElementById('btn-codigos').addEventListener('click', regenerarCodigos);
    ses.innerHTML = `<h4>Sesiones</h4>
      <p class="panel-note" style="margin:0 0 10px;">Su sesión se cierra sola tras ${esc(estado.sesion_minutos)} minutos sin actividad. Si usó un equipo ajeno o perdió el teléfono, ciérrelas en los demás dispositivos.</p>
      <button type="button" class="btn btn-ghost" id="btn-sesiones" style="border:1.5px solid var(--line);">Cerrar sesión en los demás dispositivos</button>
      ${estado.terminos_aceptados ? `<p class="panel-note" style="margin:12px 0 0;">Términos y privacidad aceptados el ${esc(estado.terminos_aceptados)}.</p>` : ''}`;
    document.getElementById('btn-sesiones').addEventListener('click', cerrarOtras);
  }

  async function cargar() {
    estado = await apiFetch('/cuenta/seguridad');
    panel.hidden = false;
    pintar();
  }

  async function preparar2fa() {
    const datos = await pedirClave({ titulo: 'Activar la verificación en dos pasos', texto: 'Confirme su contraseña para continuar.' });
    if (!datos) return;
    const r = await llamar('/cuenta/2fa/preparar', { password: datos.password });
    if (!r.ok) return;
    const pasos = document.getElementById('seg-2fa-pasos');
    pasos.innerHTML = `<div class="qr-caja">
        <div class="qr">${r.qr}</div>
        <div>
          <p style="margin:0 0 8px; font-size:14px;"><b>1.</b> Escanee el código con su aplicación autenticadora.<br><b>2.</b> Escriba el código de 6 dígitos que muestra.</p>
          <p class="panel-note" style="margin:0 0 4px;">¿No puede escanear? Escriba esta clave:</p>
          <code class="clave-manual">${esc(r.secreto)}</code>
        </div></div>
      <div class="doc-field-row">
        <div class="doc-field"><label for="codigo-2fa">Código de 6 dígitos</label>
          <input type="text" id="codigo-2fa" inputmode="numeric" maxlength="7" autocomplete="one-time-code" placeholder="000000"></div>
        <div class="doc-field" style="align-self:end;"><button type="button" class="btn btn-brass" id="btn-2fa-confirmar">Confirmar y activar</button></div>
      </div>`;
    document.getElementById('codigo-2fa').focus();
    document.getElementById('btn-2fa-confirmar').addEventListener('click', async () => {
      const codigo = document.getElementById('codigo-2fa').value.trim();
      const a = await llamar('/cuenta/2fa/activar', { codigo });
      if (!a.ok) return;
      mostrarToast('Verificación en dos pasos activada.', 'exito');
      await cargar();
      mostrarCodigos(a.codigos, 'Sus códigos de recuperación');
    });
  }

  async function desactivar2fa() {
    const datos = await pedirClave({
      titulo: 'Desactivar la verificación en dos pasos',
      texto: 'Su cuenta quedará protegida solo por la contraseña. Confirme con su contraseña y un código.',
      conCodigo: true, boton: 'Desactivar', peligro: true,
    });
    if (!datos) return;
    const r = await llamar('/cuenta/2fa/desactivar', datos);
    if (r.ok) { mostrarToast('Verificación en dos pasos desactivada.', 'exito'); await cargar(); }
  }

  async function regenerarCodigos() {
    const datos = await pedirClave({
      titulo: 'Generar códigos de recuperación',
      texto: 'Los códigos anteriores dejarán de valer. Confirme su contraseña.',
    });
    if (!datos) return;
    const r = await llamar('/cuenta/codigos-recuperacion', { password: datos.password });
    if (!r.ok) return;
    await cargar();
    mostrarCodigos(r.codigos, 'Sus códigos de recuperación nuevos');
  }

  async function cerrarOtras() {
    const datos = await pedirClave({
      titulo: 'Cerrar sesión en los demás dispositivos',
      texto: 'Este navegador seguirá abierto; los demás tendrán que iniciar sesión otra vez.',
      boton: 'Cerrar las demás',
    });
    if (!datos) return;
    const r = await llamar('/cuenta/cerrar-sesiones', { password: datos.password });
    if (r.ok) mostrarToast(r.mensaje, 'exito');
  }

  cargar().catch(console.error);
})();
