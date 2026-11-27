# Evidencia de pruebas – Sprint 9 (22/11/2026)

Corrida completa de las pruebas del proyecto sobre el código de `sprint-9-dev` (commit `817bb56`).

## Resultado

| Suite | Casos | Resultado | Reporte |
|---|---|---|---|
| Pruebas unitarias (6 archivos) | 89 | OK | [pruebas_unitarias.txt](pruebas_unitarias.txt) |
| **Robot – Sprint 9** | 28 | **28 OK** | [report.html](report.html) · [log.html](log.html) |
| Robot – Login (HU-11) | 7 | 7 OK | [regresion login](../regresion-sprint9-20261122/login/report.html) |
| Robot – Sprint 4 | 4 | 4 OK | [regresion sprint4](../regresion-sprint9-20261122/sprint4/report.html) |
| Robot – Sprint 5 | 6 | 6 OK | [regresion sprint5](../regresion-sprint9-20261122/sprint5/report.html) |
| Robot – Sprint 6 | 7 | 7 OK | [regresion sprint6](../regresion-sprint9-20261122/sprint6/report.html) |
| Robot – Sprint 7 | 13 | 13 OK | [regresion sprint7](../regresion-sprint9-20261122/sprint7/report.html) |
| Robot – Sprint 8 | 20 | 20 OK | [regresion sprint8](../regresion-sprint9-20261122/sprint8/report.html) |
| **Total Robot** | **85** | **85 OK, 0 fallos** | |

Durante la corrida la aplicación no devolvió ningún error 500.

## Qué cubre el Sprint 9

HU-09 (consulta pública), cuentas de promotor y contraseña temporal, límite de intentos de login,
HU-01 (revisión de seguridad de archivos, versiones y código de trazabilidad), HU-14 (historial),
HU-06 (nombre del ZIP), HU-15 (Índice de Preparación del Expediente) y HU-16 (equipo de consultores).
Cada caso lleva su historia en el nombre.

## Cómo se corrió

Igual que el job de pruebas del CI (`.github/workflows/build.yml`), en un entorno desechable:

- Contenedor `python:3.11-slim` (el mismo Python del CI), Robot Framework 7.0.1 y robotframework-requests 0.9.7.
- MySQL 8 nuevo, con `schema.sql` y `python seed_usuarios.py` (sin `--demo`).
- Aplicación con `python app.py`.
- Orden: pruebas unitarias, login y Sprints 4 a 9.

Los mismos casos corren en cada Pull Request: en la pestaña *Actions*, cada corrida guarda sus
reportes como *Artifacts* (caducan; esta carpeta es la copia permanente).

## Lo que esta carpeta NO incluye

- **Escaneo de OpenVAS:** no se ejecutó en esta corrida (pendiente del paquete de calidad y seguridad).
- **Prueba de carga:** prevista para el Sprint 10.
