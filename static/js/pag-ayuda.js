// Guía de uso y preguntas frecuentes, según el rol de quien la abre.
const usuario = requireAuth();
if (usuario) {
  pintarTopbar();

  const PASOS = {
    jefe: [
      ['Personalice su consultora', 'En «Mi consultora» ponga el nombre, el color y el logo: los verá todo su equipo.'],
      ['Invite a su equipo', 'En «Equipo» genere un enlace de invitación para cada consultor, o dé de alta a alguien con una contraseña temporal.'],
      ['Registre el primer expediente', 'En «Nuevo expediente» elija la categoría (I, II o III): el sistema crea la lista de documentos que le corresponde.'],
      ['Siga los plazos', 'El panel le muestra qué expedientes están por vencer y cuáles necesitan atención, ordenados por su Índice de Preparación.'],
    ],
    consultor: [
      ['Cree un expediente', 'En «Nuevo expediente» indique proyecto, promotor y categoría.'],
      ['Suba los documentos', 'Dentro del expediente, cada carpeta recibe un PDF (la cartografía, un ZIP con shapefile). Cada subida es una versión con su código de trazabilidad.'],
      ['Pida la aprobación interna', 'Con la documentación completa, el director de proyectos aprueba internamente y usted somete el expediente a MiAmbiente.'],
      ['Dé acceso al cliente', 'Desde el expediente puede crear la cuenta del cliente para que siga el avance. Verá solo su proyecto.'],
    ],
    promotor: [
      ['Revise su proyecto', 'En «Mis expedientes» ve el estado de cada proyecto, sus plazos y los documentos recibidos.'],
      ['Cambie su contraseña', 'La primera vez, su consultor le entrega una contraseña temporal: en «Mi perfil» cree la suya.'],
      ['Consulte cuando quiera', 'El estado se actualiza apenas la consultora avanza el trámite.'],
    ],
    admin: [
      ['Cree una empresa', 'En «Plataforma» → «Empresas» cree la consultora; el sistema genera el enlace de invitación para su director de proyectos.'],
      ['Sume a otros administradores', 'En «Administradores» genere un enlace de invitación para cada persona del equipo: es de un solo uso y cada una elige su contraseña.'],
      ['Verifique los respaldos', 'En «Respaldos» compruebe que hay uno reciente y, de vez en cuando, descárguelo y pruebe «Verificar».'],
      ['Vigile el servicio', 'En «Servicio y errores» vea el estado de la base de datos, los archivos y los últimos errores.'],
    ],
  };

  const PREGUNTAS = [
    ['¿Olvidé mi contraseña, qué hago?', ['jefe', 'consultor', 'promotor'],
      'Si guardó sus códigos de recuperación, entre a «¿Olvidó su contraseña?» en la pantalla de acceso y use uno. Si no los tiene, su director de proyectos puede generarle una contraseña temporal desde «Equipo» (al cliente se la genera su consultor desde el expediente). Al jefe se la genera el administrador de la plataforma.'],
    ['¿Cómo activo la verificación en dos pasos?', ['jefe', 'consultor', 'promotor', 'admin'],
      'En «Mi perfil» → «Seguridad de la cuenta» → «Activar». Escanee el código QR con Google Authenticator, Microsoft Authenticator, Authy o 1Password y confirme con el código de 6 dígitos. Guarde los códigos de recuperación que le mostramos: no se vuelven a ver.'],
    ['¿Cómo se cuenta el plazo legal?', ['jefe', 'consultor', 'promotor'],
      'Antes de someter el expediente, corren días calendario desde su ingreso. Una vez sometido a MiAmbiente corren días hábiles (sin sábados, domingos ni feriados de Panamá) desde la fecha de sometimiento. Los límites son 20 días en la categoría I, 40 en la II y 80 en la III.'],
    ['¿Qué es el Índice de Preparación (IPE)?', ['jefe', 'consultor'],
      'Un número de 0 a 100 que resume qué tan listo está un expediente: 50 % documentos completos, 30 % plazo y 20 % vigencia de los documentos. Ordene por IPE para ver primero lo que más atención necesita.'],
    ['¿Cuándo vence un documento?', ['jefe', 'consultor', 'promotor'],
      'Si usted registra la fecha de vencimiento real del documento (por ejemplo, un paz y salvo), esa es la que cuenta; si no, se considera un año desde que se subió. En «Mi perfil» elige con cuántos días de anticipación se le avisa (15, 30 o 45).'],
    ['¿Cómo invito a alguien de mi equipo?', ['jefe'],
      'En «Equipo» → «Invitar por enlace». Copie el enlace y compártalo por el canal que prefiera: es de un solo uso, vence en 72 horas y la persona elige su propia contraseña. Si escribe un correo, el enlace solo sirve para ese correo.'],
    ['¿Cómo cambio al responsable de un expediente?', ['jefe'],
      'Abra el expediente y use «Responsable». Queda anotado en el historial. Si alguien deja la consultora, desactívelo en «Equipo» y reasigne sus expedientes.'],
    ['¿Qué ve el cliente?', ['jefe', 'consultor'],
      'Solo su proyecto: estado, plazos y documentos recibidos. No ve el Índice de Preparación, el historial ni los comentarios internos.'],
    ['¿Los comentarios los ve el cliente?', ['jefe', 'consultor'],
      'No. Los comentarios de un expediente son internos: solo los ve el equipo de la consultora.'],
    ['¿Puedo sacar mis datos de la plataforma?', ['jefe', 'consultor'],
      'Sí. «Expedientes» → «Exportar Excel» descarga la cartera y «Historial» → «Exportar CSV» el registro de acciones. Cada expediente se descarga completo (documentos y resumen) en un ZIP.'],
    ['¿Dónde están mis documentos y quién puede verlos?', ['jefe', 'consultor', 'promotor'],
      'Cada consultora ve solo lo suyo: nadie de otra empresa puede abrir sus expedientes. La cuenta de administración gestiona empresas y respaldos, pero no tiene pantallas para ver expedientes. Cada archivo conserva su huella SHA-256 para comprobar que no fue alterado.'],
    ['¿Cómo exijo los dos pasos a todo mi equipo?', ['jefe'],
      'En «Mi consultora» → «Políticas» marque «Exigir la verificación en dos pasos». Antes debe activar los suyos en «Mi perfil»: así no queda bloqueado. Quien no los tenga activos solo podrá activarlos la próxima vez que entre. Si alguien pierde el teléfono, restablezca su contraseña en «Equipo» y se le quitan los dos pasos para que los configure de nuevo.'],
    ['¿Qué es el titular de la cuenta?', ['jefe'],
      'Es el director de proyectos que creó la cuenta de la consultora. Solo el titular invita a otros directores, asciende a un consultor a director o devuelve a un director a consultor, y puede transferir la titularidad. Todo se hace en «Mi consultora» → «Titularidad».'],
    ['¿Cómo descargo todos los datos de mi consultora?', ['jefe'],
      'En «Mi consultora» → «Mis datos» → «Descargar todo». Recibe un ZIP con la cartera en Excel, el historial, los comentarios, el equipo y todos los documentos con su índice de huellas. Puede pedir una exportación cada dos minutos.'],
    ['¿Dónde veo quién entró a la cuenta o qué cambió?', ['jefe'],
      'En «Mi consultora» → «Accesos»: inicios de sesión, intentos fallidos y cambios de configuración, con fecha, persona y dirección IP. No incluye el contenido de los expedientes. Se puede descargar en CSV.'],
    ['¿Cómo agrego a otro administrador de la plataforma?', ['admin'],
      'En «Plataforma» → «Administradores» escriba el correo (opcional) y genere el enlace. Cópielo y entréguelo por un canal seguro: es de un solo uso y vence en 72 horas. La persona se registra, entra por la dirección /admin y, en producción, activa sus dos pasos en el primer ingreso.'],
    ['¿Qué pasa si un administrador pierde su teléfono o su contraseña?', ['admin'],
      'Otro administrador abre «Administradores» y pulsa «Restablecer acceso»: se genera una contraseña temporal (se muestra una sola vez), se cierran sus sesiones y se quitan sus dos pasos para que los configure de nuevo. Nadie puede restablecer su propia cuenta de este modo ni desactivarse a sí mismo, y la plataforma siempre conserva al menos un administrador activo.'],
    ['Veo un error con un código, ¿qué hago?', ['jefe', 'consultor', 'promotor', 'admin'],
      'Anote el código que aparece (por ejemplo, 3f9a1c2e) y envíelo al administrador de la plataforma: con él se encuentra el error exacto.'],
  ];

  const rol = usuario.rol;
  const pasos = PASOS[rol] || [];
  const preguntas = PREGUNTAS.filter(p => p[1].includes(rol));
  const atajos = rol === 'admin' ? '' : `
    <div class="panel">
      <h3>Atajos de teclado</h3>
      <div class="atajos">
        <span><kbd>Ctrl</kbd> + <kbd>K</kbd></span><span>Buscar expedientes, personas y acciones</span>
        <span><kbd>/</kbd></span><span>Abrir el buscador desde cualquier pantalla</span>
        <span><kbd>Esc</kbd></span><span>Cerrar ventanas y menús</span>
      </div>
    </div>`;

  document.getElementById('ayuda-contenido').innerHTML = `
    <div class="ayuda-rejilla">
      <div class="panel" style="grid-column: 1 / -1;">
        <h3>Primeros pasos</h3>
        <ol class="ayuda-lista">${pasos.map(([t, d]) => `<li><b>${esc(t)}.</b> ${esc(d)}</li>`).join('')}</ol>
      </div>
      <div class="panel">
        <h3>Recorrido de bienvenida</h3>
        <p class="panel-note">Una vuelta rápida por lo esencial de la plataforma. Solo le salió la primera vez que entró; aquí puede repetirlo cuando quiera.</p>
        <button type="button" class="btn btn-brass" id="btn-tour">Ver el recorrido</button>
      </div>
      ${atajos}
      <div class="panel">
        <h3>Su cuenta</h3>
        <ul class="ayuda-lista" style="margin-top:0;">
          <li>Cambie la contraseña y active los dos pasos en <a href="cuenta.html">Mi perfil</a>.</li>
          <li>La sesión se cierra sola tras un rato sin actividad.</li>
          <li><a href="terminos.html">Términos de uso</a> y <a href="privacidad.html">política de privacidad</a>.</li>
          <li><a href="estado.html">Estado del servicio</a>.</li>
        </ul>
      </div>
    </div>
    <div class="panel" style="margin-top:16px;">
      <h3>Preguntas frecuentes</h3>
      ${preguntas.map(([q, , r]) => `<details class="ayuda-pregunta"><summary>${esc(q)}</summary><p>${esc(r)}</p></details>`).join('')}
    </div>`;
}

const botonTour = document.getElementById('btn-tour');
if (botonTour) botonTour.addEventListener('click', () => {
  if (!iniciarTour()) mostrarToast('Abra el panel para ver el recorrido: aquí no hay nada que señalar.', 'error');
});
