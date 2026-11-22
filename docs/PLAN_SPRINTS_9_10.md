# Plan de los Sprints 9 y 10

**Caso 8 – Permisos Ambientales.** Quedan dos sprints. El Sprint 9 cierra lo que falta del
producto y el Sprint 10 es la entrega formal.

| Sprint | Fechas (a confirmar) | Objetivo |
|---|---|---|
| 9 | lun 23/11 – vie 27/11/2026 | Que las 13 historias (HU-01 a HU-11, HU-13 y HU-14) cumplan el 100% de sus criterios de aceptación, con pruebas que lo demuestren |
| 10 | lun 30/11 – vie 04/12/2026 | Congelar el código, hacer la regresión y el escaneo finales, y entregar el documento, el video y el producto desplegado |

Equipo: Nathaly Bonilla (PO y SM), Ismael Ramos (Backend y DevOps), Louis Wiltshire (Calidad y
Seguridad). Capacidad: 20 h por persona y semana, unas 40 h de desarrollo y pruebas por sprint.

---

## Actualización del 22/11/2026: decisiones del nuevo PO

**Equipo actual:** Helio Castillo (PO y SM), Ismael Ramos (Backend y DevOps), Louis Wiltshire
(Calidad y Seguridad). Lo que sigue manda sobre el plan original de más abajo.

**Hecho en `sprint-9-dev` (PR #3):** refactor a `permisos/`, HU-09 con acceso público real,
textos de estado de la HU-07, nombre del ZIP (HU-06), historial completo (HU-14), límite de
intentos de login, cuentas de promotor con contraseña temporal obligatoria, Índice de
Preparación del Expediente (HU-15, innovación) y datos de demostración.

| Tema | Decisión |
|---|---|
| HU-01: tipos de archivo | **Solo PDF y ZIP.** Se corrige el criterio, que decía DOCX. |
| HU-01: seguridad | **Hecho.** Se rechazan los PDF con JavaScript, `/Launch` o archivos incrustados y los ZIP con ejecutables o scripts, rutas inseguras, comprimidos anidados o bombas de descompresión. |
| HU-01: inmutabilidad | **Hecho.** Un documento nunca se elimina: cada subida es una versión nueva con SHA-256 y un código de trazabilidad único (`<expediente>-D<doc>-V<n>-<hash>`). |
| HU-01: validación de shapefile | Sprint 10 |
| HU-05: fecha real de vencimiento y aviso | Sprint 10 (los ítems 4 y 5 del backlog salen del Sprint 9) |
| HU-08: sometimiento, días hábiles y aviso | Sprint 10 |
| Resolución de MiAmbiente (aprobado o rechazado, número y fecha) | Sprint 10, en lugar del botón simulado |
| "Devolver con observaciones" del jefe | Sprint 10 |
| Migración a Railway (ítem 14) | Sprint 10 |
| `k8s/` (ítem 13) | No se toca antes de la presentación |
| Documentos del proyecto | Viven en la rama `context`, fuera de las ramas de desarrollo |

---

## Punto de partida

La revisión del 20/11 comparó cada criterio de aceptación del documento con el código:

| Estado | Historias |
|---|---|
| Completas | HU-02, HU-03, HU-04, HU-10, HU-11, HU-13, HU-14 |
| Casi completas | HU-01 (no valida shapefile ni acepta DOCX), HU-06 (al ZIP le falta la fecha en el nombre), HU-07 (los textos no son los 3 del criterio) |
| Con criterios centrales sin hacer | **HU-05** (no hay fecha de vencimiento ni aviso configurable), **HU-08** (no hay fecha de sometimiento, cuenta días calendario y no notifica), **HU-09** (no respeta `acceso_publico`, no muestra el consultor y no hay forma de cambiar el acceso) |

Todo esto **no suma puntos nuevos**: son criterios de historias que ya están en el backlog de
27 puntos. En el documento se registran como "cierre de criterios" y tareas técnicas.

---

## Sprint 9: cierre de criterios y endurecimiento

### Backlog del sprint

Orden = prioridad. Si falta tiempo, se recorta desde abajo (ver "Qué se recorta").

| # | Elemento | Responsable | Horas | Hecho cuando… |
|---|---|---|---|---|
| 1 | **Refactor estructural** (hecho en la rama `sprint-9-dev`): `app.py` pasa a un paquete `permisos/` con blueprints | Louis (regresión) | 2 (validar) | Las suites de Robot de los Sprints 4 a 8 pasan en Docker y el PR se integra con el pipeline en verde |
| 2 | **HU-09: acceso público real.** `/consulta/<codigo>` devuelve el consultor responsable y el estado del semáforo; si `acceso_publico` es falso, no devuelve el resumen ni permite el PDF (lo decide el backend). Endpoint para que el jefe o el consultor dueño active o desactive el acceso, con su interruptor en el detalle | Ismael | 6 | Prueba: con el acceso desactivado, la consulta no trae el resumen y el PDF no se puede descargar; con el acceso activo, sí |
| 3 | **HU-07: tres estados.** La interfaz muestra *Aprobado*, *En evaluación* o *Pendiente de subsanación* (mapa: `pendiente` y `aprobado_interno` → Pendiente de subsanación, `evaluacion` → En evaluación, `aprobado` → Aprobado). Los estados internos siguen en el detalle | Ismael | 2 | Prueba: cada estado de la base se ve con su texto del criterio |
| 4 | **HU-08: plazo legal desde el sometimiento.** Columna `fecha_sometimiento`, que se llena en `/someter`. El plazo corre desde esa fecha en **días hábiles** (lunes a viernes, sin los feriados nacionales de Panamá cargados en una lista). Aviso en pantalla al promotor cuando el plazo entra en "por vencer" | Ismael | 8 | Unittests de días hábiles (fin de semana y feriado) y prueba Robot del semáforo antes y después de someter |
| 5 | **HU-05: vencimiento de documentos.** Fecha de vencimiento opcional al subir el documento; preferencia de aviso del usuario (15, 30 o 45 días, por defecto 30) en un endpoint `/perfil`; el dashboard usa ambos datos y deja un registro en `alertas` (o se elimina esa tabla si no se usa) | Ismael | 8 | Prueba: un documento que vence dentro del umbral aparece en el dashboard; si se cambia la preferencia, cambia el resultado |
| 6 | **HU-06: nombre del ZIP** `{codigo}_{AAAA-MM-DD}.zip` | Ismael | 0,5 | La prueba del Sprint 5 revisa el nombre en `Content-Disposition` |
| 7 | **HU-01: cartografía.** Si la carpeta es *Cartografía*, el ZIP debe traer `.shp`, `.shx` y `.dbf`. Sobre DOCX, **decide la PO**: (a) se acepta DOCX validando que sea un ZIP de Office, o (b) se corrige el criterio a "solo PDF" (es lo que se decidió en el Sprint 4 por seguridad). Recomendación: (b) | Ismael / Nathaly | 3 | Prueba: un ZIP de cartografía sin `.shp` se rechaza con 400 |
| 8 | **HU-14: historial completo.** Registrar también *eliminó documento*, *sometió*, *aprobación MiAmbiente (simulada)* y *cambió acceso público* | Ismael | 2 | Prueba: cada acción deja su entrada |
| 9 | **Seguridad:** límite de intentos en `/login` (5 por minuto por correo e IP, responde 429); cabecera `Content-Security-Policy` básica; escaneo de OpenVAS sobre Railway | Louis | 6 | Prueba Robot del 429 y reporte de OpenVAS con 0 hallazgos medios o altos de la app (o su análisis) |
| 10 | **Pruebas:** suite `Test_Sprint9.robot` con los ítems 2 a 9, integrada al pipeline; unittests de las reglas nuevas; regresión de los Sprints 4 a 8 | Louis | 8 | Pipeline en verde con todas las suites |
| 11 | **Migraciones de base:** las columnas nuevas se agregan al arrancar, como ya se hace con el historial (idempotente), y se documentan en `sql/sprint9_manual.sql` como plan B para Aiven | Ismael | 2 | La app arranca contra una base del Sprint 8 y contra una vacía |
| 12 | **Repositorio:** proteger `main` (solo PR con pipeline en verde); borrar `tests/test_sprint4.robot` (duplicado viejo) y `test_login.robot`; sacar del control de versiones `results/` y los reportes de `tests/sprint4/`; agregar `tests/sprint8` al comando del README | Louis / Nathaly | 2 | `git ls-files` sin reportes generados |
| 13 | **Kubernetes:** completar `k8s/` (Service de MySQL y un ejemplo de Secret) **o** declararlo histórico en el README, porque el despliegue real es Railway y Aiven. Recomendación: declararlo histórico | Ismael | 1 | La métrica "% infraestructura en YAML" del documento queda explicada |
| 14 | **Migración de Render a Railway:** `Dockerfile` con `PORT`, `scripts/init_db.py` como pre-deploy, volumen para `/app/uploads`, variables de Aiven; Render se da de baja al validar | Ismael | 2 | La app responde en el dominio de Railway y un documento subido sobrevive a un redespliegue |

Total estimado: unas 50 h. Con 40 h disponibles, **los ítems 1 a 8, 10 y 11 son
obligatorios**; del 9, 12 y 13 se hace lo que alcance.

### Decisiones que la PO debe tomar al inicio del sprint

1. **HU-08:** antes de someter, ¿el semáforo no corre (aparece como "sin plazo") o sigue
   midiendo desde la fecha de ingreso como hoy? El criterio dice "desde que se sometió".
   Recomendación: no corre hasta el sometimiento.
2. **HU-01:** DOCX sí o no (ver ítem 7).
3. **HU-08, criterio 3 ("envía una notificación"):** ¿alcanza con el aviso en pantalla o hace
   falta correo? El correo exige un servicio SMTP y sus credenciales en Railway.
   Recomendación: aviso en pantalla y el correo como trabajo futuro.

### Qué se recorta si falta tiempo

En este orden: CSP (ítem 9), Kubernetes (ítem 13), preferencia configurable de HU-05 (queda fijo
en 30 días, pero sí con fecha de vencimiento real), validación de shapefile (ítem 7). Nada de
esto deja una historia sin su criterio principal, salvo el último, que se documenta como deuda.

---

## Sprint 10: entrega formal

**Regla del sprint:** desde el lunes 30/11 el código está congelado. Solo entran
correcciones de errores, por PR y con el pipeline en verde.

| # | Elemento | Responsable | Hecho cuando… |
|---|---|---|---|
| 1 | **Regresión final** de las suites de los Sprints 4 a 9 en CI y en local, con los reportes guardados | Louis | Todas en PASS; reportes adjuntos al documento |
| 2 | **Escaneo final de OpenVAS** sobre Railway, con el análisis de cada hallazgo | Louis | Reporte y tabla de hallazgos en el documento |
| 3 | **Prueba de carga básica** para cerrar la métrica "Eficiencia de rendimiento", que sigue "por definir": 20 usuarios simultáneos sobre login, listado y detalle. Meta: p95 menor a 1 s | Louis | Meta escrita en la tabla GQM y su resultado medido |
| 4 | **Release** `v1.0`: tag en `main`, imagen `ghcr.io/...:v1.0` publicada por el pipeline y desplegada en Railway | Ismael | El dominio de Railway responde con la versión 1.0 |
| 5 | **README de despliegue:** pasos de Railway y Aiven (variables, volumen, pre-deploy, `JEFE_PASSWORD`) y cómo correr las pruebas | Ismael | Otra persona despliega siguiendo solo el README |
| 6 | **Documento final** (ver la lista de abajo) | Nathaly (con todos) | Revisión cruzada de los tres integrantes |
| 7 | **Video de 10 minutos como máximo**, un bloque por criterio de la rúbrica (ver guion) | Todos | Video subido y probado |
| 8 | **Demo:** revisar el uso y el último despliegue en Railway antes de empezar, usuarios de prueba verificados y plan B con Docker local | Ismael | Ensayo completo un día antes |

### Correcciones al documento final

- Agregar las secciones de los **Sprints 8, 9 y 10** con la misma estructura (objetivo,
  incremento, evidencias de Scrum, calidad, seguridad y DevOps, métricas y retrospectiva).
- Agregar **HU-13 y HU-14** al backlog, con sus criterios y puntos, y decidir si HU-12
  (responsive) entra formalmente.
- **Tabla de trazabilidad:** cada criterio de cada HU con la prueba (archivo y caso) o la
  evidencia que lo respalda. Es la métrica "% criterios verificados" del propio documento.
- **Presupuesto:** reconciliar los $300.000 asignados (50% personal) con la tabla, que suma
  $210.000 y tiene $14.740 de honorarios. También aclarar "10 semanas" frente a 11 sprints
  (0 a 10).
- Explicar el salto de "8 HU, 35 puntos" (Sprint 1) a "11 HU, 27 puntos".
- Escribir la **reflexión del Sprint 6**, que falta, y las de los Sprints 8, 9 y 10.
- Aclarar que las pruebas del Sprint 5 se migraron de `X-Usuario-Email` a sesión real en el
  Sprint 7.
- Declarar como **simulación** la aprobación de MiAmbiente, de acuerdo con el alcance (la
  decisión final es de un evaluador humano).
- **Lecciones aprendidas** del equipo (lo pide la entrega final).

### Guion del video (10 minutos)

| Minuto | Bloque de la rúbrica | Qué se muestra |
|---|---|---|
| 0:00 – 1:00 | Contexto | Problema, actores y alcance (consultoras y promotores, Ley 41) |
| 1:00 – 3:30 | Calidad del software | Demo del flujo completo: crear, subir, verificar, aprobar (jefe), someter, semáforo, consulta pública; pipeline con todas las suites en verde |
| 3:30 – 5:30 | Seguridad del desarrollo | Sesión firmada, CSRF, permisos por rol (403), magic bytes, historial de solo lectura, límite de login, OpenVAS y su análisis, Ley 81 en la consulta pública |
| 5:30 – 7:30 | Agilidad y DevOps | Ramas y PR, quality gate, GHCR, Docker Compose, Railway y Aiven, evolución desde Minikube y Render |
| 7:30 – 9:30 | Gestión del proyecto | Backlog 27/27, transferencia de equipo, presupuesto, métricas GQM y sus resultados |
| 9:30 – 10:00 | Cierre | Lecciones aprendidas y trabajo futuro |

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| HU-08 y HU-05 cambian el esquema y el despliegue en Aiven falla | Migraciones idempotentes al arrancar y `sql/sprint9_manual.sql` como plan B (igual que en el Sprint 8) |
| El cambio de semántica del semáforo (HU-08) rompe pruebas de sprints anteriores | Se decide el primer día y se ajustan las pruebas viejas en el mismo PR |
| No alcanzan las horas del Sprint 9 | Recorte en el orden indicado; nada nuevo entra en el Sprint 10 |
| Falla de Railway o de Aiven durante la demo | Docker local listo y video de la demo grabado |
| El refactor rompe algo que solo se ve con base de datos | El PR del refactor no se integra hasta que pasen las suites de Robot de los Sprints 4 a 8 |

## Definición de "hecho" para la entrega

- [ ] Cada criterio de aceptación de las 13 HU tiene una prueba o evidencia en la tabla de trazabilidad
- [ ] Pipeline en verde en `main`, con todas las suites
- [ ] OpenVAS sin hallazgos medios ni altos atribuibles a la aplicación
- [ ] `v1.0` desplegada en Railway y en GHCR
- [ ] README que permite levantar el proyecto en local y desplegarlo
- [ ] Documento final, video y lecciones aprendidas entregados
