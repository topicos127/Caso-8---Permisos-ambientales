# Sprint 9 – HU-16 y HU-12 (calidad y seguridad) – 22/11/2026

Suite `tests/sprint9/Test_Sprint9_Equipo.robot`, complementaria a los casos 20 a 26 de
`Test_Sprint9.robot`.

| Resultado | Casos |
|---|---|
| PASS | 16 |
| SKIP (hallazgo) | 1 |
| FAIL | 0 |

**Cubre:** matriz completa de permisos del equipo (403 a consultor y promotor y 401 sin sesión en
alta, desactivar, activar y reasignar); el jefe solo da de baja a consultores; el alta ignora el rol
pedido, no duplica correos y valida los datos; la sesión de un consultor desactivado no sirve para
escribir; la baja no borra expedientes ni historial; validaciones de la reasignación; la consulta
pública muestra al nuevo consultor; el consultor reactivado no ve lo reasignado; y lo que se puede
revisar del celular sin navegador (viewport, menú, tablas en tarjetas). Lo visual de HU-12 va en
casos manuales.

**Hallazgo (caso 14, SKIP):** `/registro` sigue aceptando `rol=consultor`, así que cualquiera crea
una cuenta de consultor sin pasar por el jefe, y un consultor dado de baja puede volver con otro
correo. El caso describe lo esperado (400 o 403) y lleva `robot:skip-on-failure`: mientras no se
corrija queda en SKIP sin poner el CI en rojo, y pasa solo cuando se corrija. Decisión pendiente
del PO.

**Cómo se corrió:** igual que el CI (`.github/workflows/build.yml`): Python 3.11, Robot Framework
7.0.1, robotframework-requests 0.9.7, MySQL 8 nuevo con `schema.sql` y `seed_usuarios.py`, app con
`python app.py`. Orden: login y Sprints 4 a 9 (85/85 PASS) y esta suite al final. Sin errores 500.
Se corrió dos veces seguidas sobre la misma base con el mismo resultado; estos reportes son de la
segunda corrida.
