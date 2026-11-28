// Capa de interaccion (HCI): toda accion del usuario tiene su indicador.
//
// - Barra de carga arriba mientras haya peticiones al servidor.
// - El boton que inicio una peticion queda "en espera" (spinner, aria-busy)
//   hasta la respuesta; luego marca exito (pulso verde) o error (sacudida roja).
// - Onda al presionar cualquier boton y aviso al iniciar una descarga.
//
// Se carga en el <head> de cada pantalla, antes de sus scripts, para envolver
// fetch() sin tocar el codigo de cada boton.
(function () {
  'use strict';
  // Color por rol: <html data-rol="jefe|consultor|promotor"> antes de que la pagina se pinte.
  try {
    const u = JSON.parse(sessionStorage.getItem('usuario') || 'null');
    if (u && u.rol) document.documentElement.setAttribute('data-rol', u.rol);
  } catch (e) { /* sin sesion: queda el verde de la marca */ }
  // Paginas publicas (estado, terminos, privacidad): quien llega desde dentro de la plataforma vuelve a su
  // panel, no al landing. La administracion tiene su propio panel; el resto, el suyo.
  document.addEventListener('DOMContentLoaded', () => {
    try {
      const u = JSON.parse(sessionStorage.getItem('usuario') || 'null');
      if (!u || !u.rol) return;
      document.querySelectorAll('a.volver').forEach((a) => {
        a.setAttribute('href', u.rol === 'admin' ? '/admin/panel' : 'dashboard.html');
        a.textContent = '← Volver al panel';
      });
    } catch (e) { /* sin sesion: sigue apuntando al inicio */ }
  });
  const fetchOriginal = window.fetch.bind(window);
  const VENTANA_MS = 8000;  // un clic "reclama" la siguiente peticion por este tiempo
  let ultimoBoton = null;
  let ultimoClic = 0;
  let pendientes = 0;
  let barra = null;

  function selectorBoton(el) {
    return el && el.closest ? el.closest('button, .btn, .btn-stamp, .btn-menu, a.btn, .who a') : null;
  }

  // La onda solo en los botones con estilo propio (tienen position: relative).
  function botonConOnda(el) {
    return el && el.closest ? el.closest('.btn, .btn-stamp, .btn-menu, .who a') : null;
  }

  // ---------- Barra de carga ----------
  function asegurarBarra() {
    if (barra || !document.body) return barra;
    barra = document.createElement('div');
    barra.id = 'barra-carga';
    barra.setAttribute('role', 'progressbar');
    barra.setAttribute('aria-label', 'Cargando');
    barra.setAttribute('aria-hidden', 'true');
    document.body.appendChild(barra);
    return barra;
  }

  function actualizarBarra() {
    const b = asegurarBarra();
    if (!b) return;
    const activa = pendientes > 0;
    b.classList.toggle('activa', activa);
    b.setAttribute('aria-hidden', activa ? 'false' : 'true');
    document.documentElement.classList.toggle('trabajando', activa);
  }

  // ---------- Estado del boton ----------
  function enEspera(boton, si) {
    boton.classList.toggle('cargando', si);
    if (si) boton.setAttribute('aria-busy', 'true');
    else boton.removeAttribute('aria-busy');
  }

  function marcar(boton, ok) {
    const clase = ok ? 'hecho' : 'fallo';
    boton.classList.remove('hecho', 'fallo');
    void boton.offsetWidth;  // reinicia la animacion si se repite
    boton.classList.add(clase);
    setTimeout(() => boton.classList.remove(clase), 1100);
  }

  window.fetch = async function (...args) {
    let boton = null;
    if (ultimoBoton && performance.now() - ultimoClic < VENTANA_MS && document.contains(ultimoBoton)) {
      boton = ultimoBoton;
      ultimoBoton = null;  // una peticion por clic: las siguientes solo mueven la barra
    }
    if (boton) enEspera(boton, true);
    pendientes++;
    actualizarBarra();
    try {
      const respuesta = await fetchOriginal(...args);
      if (boton) marcar(boton, respuesta.ok);
      return respuesta;
    } catch (error) {
      if (boton) marcar(boton, false);
      throw error;
    } finally {
      pendientes = Math.max(0, pendientes - 1);
      actualizarBarra();
      if (boton) enEspera(boton, false);
    }
  };

  // ---------- Clics: onda, boton reclamado y descargas ----------
  document.addEventListener('pointerdown', (e) => {
    const boton = botonConOnda(e.target);
    if (!boton || boton.disabled) return;
    const caja = boton.getBoundingClientRect();
    const onda = document.createElement('span');
    onda.className = 'onda';
    const lado = Math.max(caja.width, caja.height) * 2;
    onda.style.width = onda.style.height = lado + 'px';
    onda.style.left = (e.clientX - caja.left - lado / 2) + 'px';
    onda.style.top = (e.clientY - caja.top - lado / 2) + 'px';
    boton.appendChild(onda);
    setTimeout(() => onda.remove(), 650);
  }, true);

  document.addEventListener('click', (e) => {
    const boton = selectorBoton(e.target);
    if (boton) { ultimoBoton = boton; ultimoClic = performance.now(); }
    const descarga = e.target.closest && e.target.closest('a[download]');
    if (descarga && typeof window.mostrarToast === 'function') {
      window.mostrarToast('Descarga iniciada.', 'exito');
      marcar(descarga, true);
    }
  }, true);

  // Teclado: Enter o Espacio sobre un boton tambien "reclama" la peticion.
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const boton = selectorBoton(e.target);
    if (boton) { ultimoBoton = boton; ultimoClic = performance.now(); }
  }, true);

  // Al enviar un formulario, su boton de envio es el que espera.
  document.addEventListener('submit', (e) => {
    const boton = e.submitter || (e.target.querySelector && e.target.querySelector('[type="submit"]'));
    if (boton) { ultimoBoton = boton; ultimoClic = performance.now(); }
  }, true);

  // Al salir de la pagina por un enlace, la barra indica que se esta cargando.
  window.addEventListener('beforeunload', () => {
    pendientes++;
    actualizarBarra();
  });
  // Al volver con el boton Atras (pagina restaurada de la cache), no queda cargando.
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) { pendientes = 0; actualizarBarra(); }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', actualizarBarra);
  } else {
    actualizarBarra();
  }
})();
