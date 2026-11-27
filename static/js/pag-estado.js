// Estado del servicio (público): se consulta /estado cada 30 segundos.
const contenedor = document.getElementById('indicadores');
const fecha = document.getElementById('estado-actualizado');

function luz(ok, titulo, texto) {
  const caja = document.createElement('div');
  caja.className = 'indicador' + (ok ? '' : ' falla');
  const punto = document.createElement('span');
  punto.className = 'luz';
  punto.setAttribute('aria-hidden', 'true');
  const cuerpo = document.createElement('div');
  const t = document.createElement('b');
  t.textContent = titulo;
  const d = document.createElement('span');
  d.textContent = ok ? texto : 'No responde';
  cuerpo.append(t, d);
  caja.append(punto, cuerpo);
  return caja;
}

async function consultar() {
  let e = null;
  try {
    const r = await fetch('/estado', { cache: 'no-store' });
    e = await r.json();
  } catch (err) {
    e = null;
  }
  contenedor.replaceChildren();
  if (!e) {
    contenedor.append(luz(false, 'Servicio', ''));
    fecha.textContent = 'No se pudo consultar el estado.';
    return;
  }
  contenedor.append(
    luz(e.servicio === 'operativo', 'Servicio', e.servicio === 'operativo' ? 'Operativo' : 'Con problemas'),
    luz(e.base_de_datos, 'Base de datos', 'Conectada'),
    luz(e.archivos, 'Almacenamiento de archivos', 'Disponible'),
    luz(true, `Versión ${e.version}`, `Activo desde ${e.activo_desde}`)
  );
  fecha.textContent = 'Actualizado a las ' + new Date().toLocaleTimeString('es-PA', { hour: '2-digit', minute: '2-digit' });
}

consultar();
setInterval(consultar, 30000);
