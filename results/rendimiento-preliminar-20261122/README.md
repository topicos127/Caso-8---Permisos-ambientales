# Medición preliminar de rendimiento – Sprint 9 (22/11/2026)

Primera medición del tiempo de respuesta, que en el documento del proyecto figuraba como "por definir".

## Qué se midió

20 usuarios simultáneos. Cada uno inicia sesión una vez y repite 10 veces el listado de expedientes, el detalle de
un expediente y el panel (620 peticiones, solo lecturas). Los resultados están en [resultado.json](resultado.json).

| Operación | Peticiones | Media | p95 | Máximo |
|---|---|---|---|---|
| Inicio de sesión | 20 | 512 ms | 695 ms | 705 ms |
| Listado de expedientes | 200 | 232 ms | 291 ms | 356 ms |
| Detalle de un expediente | 200 | 186 ms | 230 ms | 294 ms |
| Panel del jefe | 200 | 231 ms | 296 ms | 334 ms |
| **Todas** | **620** | **226 ms** | **313 ms** | **705 ms** |

Sin errores; unas 87 peticiones por segundo. Meta de la plantilla: p95 menor a 1 s.

## Cómo se midió

- Aplicación y MySQL en Docker local (`docker compose`), un proceso de gunicorn con 8 hilos, con los datos de
  demostración. Docker limitado a 5.5 GB de memoria.
- Script: [medir_rendimiento.py](medir_rendimiento.py). Requiere `requests` y la aplicación en `localhost:5000`.
  Usa el usuario de prueba `consultor1@ejemplo.com`.

## Limitaciones

Es una medición **preliminar**: local, sin red real, sin escrituras y con pocos datos. La prueba formal (con Locust,
sobre el entorno desplegado) queda para el Sprint 10.
