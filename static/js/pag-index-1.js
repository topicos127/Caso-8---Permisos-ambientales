
// HU-07: tres estados publicos. aprobado_interno se muestra como pendiente.
function pintarEtapas(estado) {
  const orden = ['pendiente', 'evaluacion', 'aprobado'];
  const actual = estado === 'aprobado_interno' ? 'pendiente' : estado;
  const i = orden.indexOf(actual);
  document.querySelectorAll('#rEtapas li').forEach((li, k) => {
    li.classList.toggle('hecho', i >= 0 && k < i);
    li.classList.toggle('on', k === i);
  });
}
new MutationObserver(() => {
  if (window.expActual) pintarEtapas(window.expActual.estado);
}).observe(document.getElementById('panelResultado'), { attributes: true, attributeFilter: ['style'] });
