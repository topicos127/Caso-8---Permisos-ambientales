// Datos simulados para el prototipo del frontend (Sprint 3)
// NO conecta al backend real. Solo para maquetación y demo visual.

const MOCK_USUARIO = {
  nombre: "Consultor Uno",
  email: "consultor1@ejemplo.com",
  rol: "consultor"
};

const MOCK_EXPEDIENTES = [
  { codigo: "SP-A8-2026-001", proyecto: "Planta Solar Azuero", promotor: "Energía Verde S.A.", categoria: "II", estado: "evaluacion", fecha: "10/09/2026" },
  { codigo: "SP-A8-2026-002", proyecto: "Hotel Costero Bocas", promotor: "Inversiones del Caribe", categoria: "III", estado: "pendiente", fecha: "05/09/2026" },
  { codigo: "SP-A8-2026-003", proyecto: "Reforestación Darién", promotor: "ONG Ambiental", categoria: "I", estado: "aprobado", fecha: "28/08/2026" }
];

const MOCK_DOCUMENTOS_CAT2 = [
  { nombre: "Solicitud de evaluación", ok: true },
  { nombre: "Copia del título de propiedad", ok: true },
  { nombre: "Paz y salvo del Municipio", ok: false },
  { nombre: "Certificado de registro de la empresa", ok: true },
  { nombre: "Hoja de vida del profesional", ok: false }
];

function claseEstado(estado) {
  if (estado === "aprobado") return "status status-ok";
  if (estado === "evaluacion") return "status status-warn";
  if (estado === "pendiente") return "status status-bad";
  return "status status-info";
}

function textoEstado(estado) {
  if (estado === "aprobado") return "Aprobado";
  if (estado === "evaluacion") return "En evaluación";
  if (estado === "pendiente") return "Pendiente de subsanación";
  return estado;
}

function fichaTier(cat) {
  return `<span class="tier"><b>${cat}</b> Categoría ${cat}</span>`;
}
