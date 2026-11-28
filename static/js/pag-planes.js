// Planes: interruptor mensual / anual (pagando el año se ahorran dos meses: 10 meses de precio).
(function () {
  'use strict';
  const botones = document.querySelectorAll('[data-conmutador] button');
  if (!botones.length) return;
  const formato = (n) => 'US$ ' + n.toLocaleString('es-PA');
  function aplicar(periodo) {
    botones.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.periodo === periodo)));
    document.querySelectorAll('.plan-precio[data-precio]').forEach((el) => {
      const mensual = Number(el.dataset.precio);
      const anual = periodo === 'anual';
      el.querySelector('b').textContent = formato(anual ? mensual * 10 : mensual);
      el.querySelector('span').textContent = anual ? '/año' : '/mes';
      const nota = el.parentElement.querySelector('[data-nota]');
      if (nota) nota.textContent = anual ? `Equivale a ${formato(Math.round(mensual * 10 / 12 * 100) / 100)} al mes · 2 meses gratis` : 'Facturado cada mes';
    });
  }
  botones.forEach((b) => b.addEventListener('click', () => aplicar(b.dataset.periodo)));
})();
