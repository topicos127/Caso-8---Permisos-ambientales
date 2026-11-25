// Landing: carrusel de funcionalidades, aparicion al desplazarse, menu que
// marca la seccion visible y fotos opcionales (portada y mosaico).
(function () {
  'use strict';
  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- Aviso de novedad ----------
  const aviso = document.querySelector('.anuncio');
  if (aviso) {
    try { if (sessionStorage.getItem('anuncio_cerrado') === '1') aviso.remove(); } catch (e) { /* sin almacenamiento */ }
    const cerrar = aviso.querySelector('.anuncio-cerrar');
    if (cerrar) cerrar.addEventListener('click', () => {
      aviso.remove();
      try { sessionStorage.setItem('anuncio_cerrado', '1'); } catch (e) { /* sin almacenamiento */ }
    });
  }

  // ---------- Fotos opcionales ----------
  // <section class="hero" data-foto="img/landing/portada.webp">: si data-foto
  // tiene una ruta, se usa como fondo. Lo mismo en cada .foto-espacio del mosaico.
  document.querySelectorAll('[data-foto]').forEach((el) => {
    const ruta = (el.getAttribute('data-foto') || '').trim();
    if (!ruta) return;
    const img = new Image();
    img.onload = () => {
      // Ruta absoluta: dentro del CSS una ruta relativa se resolveria desde /css/.
      el.style.setProperty('--foto', `url("${new URL(ruta, document.baseURI).href}")`);
      el.classList.add('con-foto');
    };
    img.src = ruta;
  });

  // ---------- Aparecer al desplazarse ----------
  // El contenido es visible sin JavaScript: la clase que lo oculta la pone este script.
  const revelables = document.querySelectorAll('.revelar');
  if (!reducir && 'IntersectionObserver' in window) {
    document.documentElement.classList.add('js-revelar');
    const obs = new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revelables.forEach((el) => obs.observe(el));
  }

  // ---------- Encabezado y menu ----------
  const cabecera = document.querySelector('.l-header');
  const alDesplazar = () => cabecera && cabecera.classList.toggle('con-sombra', window.scrollY > 8);
  window.addEventListener('scroll', alDesplazar, { passive: true });
  alDesplazar();

  const enlaces = [...document.querySelectorAll('.l-nav a[href^="#"]')];
  const secciones = enlaces.map((a) => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  if ('IntersectionObserver' in window && secciones.length) {
    const espia = new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (!e.isIntersecting) return;
        enlaces.forEach((a) => a.classList.toggle('activo', a.getAttribute('href') === '#' + e.target.id));
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    secciones.forEach((s) => espia.observe(s));
  }

  // ---------- Carrusel ----------
  document.querySelectorAll('.carrusel').forEach((carrusel) => {
    const pista = carrusel.querySelector('.carrusel-pista');
    const diapositivas = [...carrusel.querySelectorAll('.diapositiva')];
    const puntos = [...carrusel.querySelectorAll('.carrusel-punto')];
    const anterior = carrusel.querySelector('.carrusel-anterior');
    const siguiente = carrusel.querySelector('.carrusel-siguiente');
    const pausa = carrusel.querySelector('.carrusel-pausa');
    const vivo = carrusel.querySelector('.carrusel-vivo');
    const INTERVALO = 7000;
    let actual = 0;
    let temporizador = null;
    let detenido = reducir;  // con movimiento reducido no avanza solo

    function ir(i, anunciar) {
      actual = (i + diapositivas.length) % diapositivas.length;
      pista.style.transform = `translateX(-${actual * 100}%)`;
      diapositivas.forEach((d, k) => {
        const activa = k === actual;
        d.setAttribute('aria-hidden', activa ? 'false' : 'true');
        d.classList.toggle('activa', activa);
        d.querySelectorAll('a, button').forEach((el) => { el.tabIndex = activa ? 0 : -1; });
      });
      puntos.forEach((p, k) => {
        p.setAttribute('aria-selected', k === actual ? 'true' : 'false');
        p.tabIndex = k === actual ? 0 : -1;
        p.classList.remove('corriendo');
      });
      if (!detenido) {
        void puntos[actual].offsetWidth;  // reinicia la barra de progreso del punto
        puntos[actual].classList.add('corriendo');
      }
      if (anunciar && vivo) {
        vivo.textContent = `Funcionalidad ${actual + 1} de ${diapositivas.length}: ` +
          (diapositivas[actual].querySelector('h3') || {}).textContent;
      }
      programar();
    }

    function programar() {
      clearTimeout(temporizador);
      if (!detenido) temporizador = setTimeout(() => ir(actual + 1, false), INTERVALO);
    }

    function detener(si) {
      detenido = si;
      carrusel.classList.toggle('pausado', si);
      if (pausa) {
        pausa.setAttribute('aria-pressed', si ? 'true' : 'false');
        pausa.setAttribute('aria-label', si ? 'Reanudar el carrusel' : 'Pausar el carrusel');
      }
      ir(actual, false);
    }

    anterior.addEventListener('click', () => ir(actual - 1, true));
    siguiente.addEventListener('click', () => ir(actual + 1, true));
    puntos.forEach((p, k) => p.addEventListener('click', () => ir(k, true)));
    if (pausa) pausa.addEventListener('click', () => detener(!detenido));

    // Teclado sobre los puntos: flechas, Inicio y Fin.
    carrusel.querySelector('.carrusel-puntos').addEventListener('keydown', (e) => {
      const mapa = { ArrowRight: actual + 1, ArrowLeft: actual - 1, Home: 0, End: diapositivas.length - 1 };
      if (!(e.key in mapa)) return;
      e.preventDefault();
      ir(mapa[e.key], true);
      puntos[actual].focus();
    });

    // Se detiene mientras el usuario lo mira o lo recorre con el teclado.
    let pausaTemporal = false;
    const congelar = (si) => {
      if (detenido) return;
      pausaTemporal = si;
      carrusel.classList.toggle('en-espera', si);
      if (si) clearTimeout(temporizador); else ir(actual, false);  // reinicia tiempo y barra juntos
    };
    carrusel.addEventListener('mouseenter', () => congelar(true));
    carrusel.addEventListener('mouseleave', () => congelar(false));
    carrusel.addEventListener('focusin', () => congelar(true));
    carrusel.addEventListener('focusout', (e) => { if (!carrusel.contains(e.relatedTarget)) congelar(false); });

    // Deslizar con el dedo o el mouse.
    let inicioX = null;
    pista.addEventListener('pointerdown', (e) => { inicioX = e.clientX; });
    window.addEventListener('pointerup', (e) => {
      if (inicioX === null) return;
      const dx = e.clientX - inicioX;
      inicioX = null;
      if (Math.abs(dx) > 50) ir(actual + (dx < 0 ? 1 : -1), true);
    });

    // Fuera de la pantalla no avanza.
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => {
        if (detenido || pausaTemporal) return;
        if (e.isIntersecting) programar(); else clearTimeout(temporizador);
      }, { threshold: 0.3 }).observe(carrusel);
    }

    carrusel.classList.toggle('pausado', detenido);
    ir(0, false);
  });
})();
