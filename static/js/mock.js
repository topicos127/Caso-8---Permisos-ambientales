// Datos simulados para el prototipo del frontend (Sprint 3)
// NO conecta a backend. Solo para maquetación y demo visual.

const MOCK_USUARIO = {
    nombre: "Consultor Uno",
    email: "consultor1@ejemplo.com",
    rol: "consultor"
};

const MOCK_EXPEDIENTES = [
    { codigo: "EXP-2026-001", proyecto: "Planta Solar Azuero", promotor: "Energía Verde S.A.", categoria: "II", estado: "evaluacion", fecha: "2026-09-10" },
    { codigo: "EXP-2026-002", proyecto: "Hotel Costero Bocas", promotor: "Inversiones del Caribe", categoria: "III", estado: "pendiente", fecha: "2026-09-05" },
    { codigo: "EXP-2026-003", proyecto: "Reforestación Darién", promotor: "ONG Ambiental", categoria: "I", estado: "aprobado", fecha: "2026-08-28" }
];

const MOCK_DOCUMENTOS_CAT1 = [
    { nombre: "Solicitud de evaluación", ok: true },
    { nombre: "Copia del título de propiedad", ok: true },
    { nombre: "Paz y salvo del Municipio", ok: false },
    { nombre: "Certificado de registro de la empresa", ok: true },
    { nombre: "Hoja de vida del profesional", ok: false }
];

function claseBadge(estado) {
    if (estado === "aprobado") return "badge badge-aprobado";
    if (estado === "evaluacion") return "badge badge-evaluacion";
    if (estado === "pendiente") return "badge badge-pendiente";
    return "badge badge-info";
}

function textoEstado(estado) {
    if (estado === "aprobado") return "Aprobado";
    if (estado === "evaluacion") return "En evaluación";
    if (estado === "pendiente") return "Pendiente de subsanación";
    return estado;
}