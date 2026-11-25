const usuario = requireAuth();
if (!usuario) throw new Error('Sin sesión');
if (usuario.rol === 'promotor') { window.location.href = 'expedientes.html'; }
pintarTopbar();

const CARPETAS_POR_CAT = {
  "I": [
    { nombre: "Línea Base",            hint: "PDF" },
    { nombre: "Plan de Manejo",        hint: "PDF" },
    { nombre: "Anexos Legales",        hint: "PDF" }
  ],
  "II": [
    { nombre: "Línea Base",            hint: "PDF" },
    { nombre: "Plan de Manejo",        hint: "PDF" },
    { nombre: "Anexos Legales",        hint: "PDF" },
    { nombre: "Cartografía",           hint: "ZIP · shapefile" }
  ],
  "III": [
    { nombre: "Línea Base",            hint: "PDF" },
    { nombre: "Plan de Manejo",        hint: "PDF" },
    { nombre: "Anexos Legales",        hint: "PDF" },
    { nombre: "Cartografía",           hint: "ZIP · shapefile" },
    { nombre: "Evidencia Foro Público", hint: "PDF · ZIP" }
  ]
};

const DESCRIPCION_CAT = {
  "I":   "bajo impacto",
  "II":  "impacto moderado",
  "III": "alto impacto"
};

let categoriaActual = "II";

function categoriaDesdeSelect(valor) {
  if (valor.includes("III")) return "III";
  if (valor.includes("I —")) return "I";
  return "II";
}

function renderCarpetas(cat) {
  const grid = document.getElementById('folder-grid');
  grid.innerHTML = '';
  CARPETAS_POR_CAT[cat].forEach(c => {
    grid.innerHTML += `
      <div class="folder">
        <div class="name">${c.nombre}</div>
        <div class="hint">${c.hint}</div>
      </div>
    `;
  });
}

function renderChecklist(cat) {
  const ul = document.getElementById('checklist');
  ul.innerHTML = '';
  CARPETAS_POR_CAT[cat].forEach(c => {
    ul.innerHTML += `
      <li>
        <span class="name">${c.nombre}</span>
        <span class="tag-missing">Pendiente</span>
      </li>
    `;
  });
}

const sel = document.getElementById('selectCategoria');
sel.addEventListener('change', () => {
  categoriaActual = categoriaDesdeSelect(sel.value);
  document.getElementById('cat-note').innerHTML =
    `<span class="tier"><b>${categoriaActual}</b> Categoría ${categoriaActual} — ${DESCRIPCION_CAT[categoriaActual]}</span>`;
  renderCarpetas(categoriaActual);
  renderChecklist(categoriaActual);
});

renderCarpetas(categoriaActual);
renderChecklist(categoriaActual);

document.getElementById('btnGuardar').addEventListener('click', async () => {
  const proyecto = document.getElementById('proyecto').value.trim();
  const promotor = document.getElementById('promotor').value.trim();
  const promotor_email = (document.getElementById('promotor_email').value || '').trim();

  if (!proyecto || !promotor) {
    mostrarToast('Completa el nombre del proyecto y el promotor.', 'error');
    return;
  }

  const btn = document.getElementById('btnGuardar');
  btn.disabled = true;
  btn.textContent = 'Guardando...';

  try {
    const r = await apiFetch('/expedientes', {
      method: 'POST',
      body: JSON.stringify({
        proyecto,
        promotor,
        promotor_email,
        categoria: categoriaActual,
        acceso_publico: document.getElementById('acceso_publico').checked
      })
    });

    if (r.ok) {
      mostrarToast(`Expediente ${r.codigo} creado correctamente.`, 'exito');
      setTimeout(() => window.location.href = 'expediente-detalle.html?codigo=' + r.codigo, 1500);
    } else {
      mostrarToast(r.mensaje || 'Error al crear.', 'error');
      btn.disabled = false;
      btn.textContent = 'Guardar expediente';
    }
  } catch (err) {
    mostrarToast('Error de red al guardar.', 'error');
    btn.disabled = false;
    btn.textContent = 'Guardar expediente';
  }
});
