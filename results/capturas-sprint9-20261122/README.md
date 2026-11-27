# Capturas de la aplicación – Sprint 9 (22/11/2026)

Evidencia visual de lo trabajado en el Sprint 9, tomada sobre el código de `sprint-9-dev` con los datos de
demostración (`seed_usuarios.py --demo`: 7 expedientes con todos los estados, categorías y plazos).

## Cómo se tomaron

- Aplicación y MySQL 8 en contenedores nuevos, con el esquema de `schema.sql` y la semilla de demostración.
- Microsoft Edge controlado con Playwright, a 1440 × 900 (escritorio) y 390 × 844 (celular).
- Cuatro roles: jefe, consultor, promotor y consulta pública. Las capturas con un archivo subido o rechazado
  salen de subidas reales hechas por el navegador.
- Los usuarios y contraseñas que aparecen son de prueba. Las contraseñas temporales de las capturas 10 y 18
  pertenecen a ese entorno desechable y ya no existen.

## Índice

| # | Archivo | Qué demuestra | Historia | Rol |
|---|---|---|---|---|
| 01 | [01_login](01_login.png) | Pantalla de acceso | HU-11 | — |
| 02 | [02_publico_consulta…](02_publico_consulta_con_consultor_y_estado.png) | La consulta pública muestra proyecto, **consultor responsable** y **estado público** | HU-09, HU-07 | Promotor |
| 03 | [03_publico_sin_acceso…](03_publico_sin_acceso_no_se_entrega_ningun_dato.png) | Un proyecto sin acceso público no entrega **ningún dato** (el servidor responde 403) | HU-09 | Promotor |
| 04 | [04_consultor_lista…](04_consultor_lista_con_ipe_ordenada_de_menor_a_mayor.png) | Lista con la columna **IPE** ordenada de menor a mayor | HU-15 | Consultor |
| 05 | [05_consultor_detalle…](05_consultor_detalle_con_ipe_y_proximas_acciones.png) | Panel del **Índice de Preparación**: componentes (documentos, plazo, vigencia) y próximas acciones | HU-15 | Consultor |
| 06 | [06_hu01_nueva_version…](06_hu01_nueva_version_con_codigo_de_trazabilidad.png) | Una subida crea la **versión 2** con su **código de trazabilidad** único | HU-01 | Consultor |
| 07 | [07_hu01_versiones…](07_hu01_versiones_del_documento_vigente_y_anteriores.png) | Historial de versiones: la vigente (v2) y la anterior (v1) se **conservan** | HU-01 | Consultor |
| 08 | [08_hu01_pdf_con_javascript…](08_hu01_pdf_con_javascript_rechazado.png) | Un **PDF con JavaScript** se rechaza con un mensaje claro | HU-01 | Consultor |
| 09 | [09_hu01_zip_con_ejecutable…](09_hu01_zip_con_ejecutable_rechazado.png) | Un **ZIP con un ejecutable** se rechaza | HU-01 | Consultor |
| 10 | [10_acceso_del_promotor…](10_acceso_del_promotor_con_contrasena_temporal_unica.png) | El consultor crea la cuenta del promotor; la **contraseña temporal** se muestra **una sola vez** | Cuentas | Consultor |
| 11 | [11_promotor_nuevo…](11_promotor_nuevo_debe_cambiar_la_contrasena_temporal.png) | El promotor nuevo **debe cambiar** su contraseña temporal antes de usar el sistema | Cuentas | Promotor |
| 12 | [12_promotor_lista…](12_promotor_lista_con_estados_publicos_y_sin_ipe.png) | El promotor ve los tres estados del criterio y **no ve el IPE** | HU-07, HU-15 | Promotor |
| 13 | [13_promotor_detalle…](13_promotor_detalle_sin_ipe_ni_correo.png) | Detalle sin IPE y sin el correo del promotor | HU-15 | Promotor |
| 14 | [14_jefe_panel…](14_jefe_panel_con_prioridades_por_ipe.png) | Panel del jefe con las **prioridades por IPE** | HU-15 | Jefe |
| 15 | [15_jefe_lista…](15_jefe_lista_con_consultor_ipe_y_estados_hu07.png) | Lista del jefe: consultor de cada expediente, IPE y estados | HU-13, HU-07 | Jefe |
| 16 | [16_jefe_interruptor…](16_jefe_interruptor_de_acceso_publico_hu09.png) | Interruptor de **acceso público** (solo el jefe) | HU-09 | Jefe |
| 17 | [17_jefe_equipo…](17_jefe_equipo_de_consultores_hu16.png) | **Equipo de consultores**: lista con estado y cantidad de expedientes | HU-16 | Jefe |
| 18 | [18_jefe_alta…](18_jefe_alta_de_consultor_con_clave_temporal_unica.png) | **Alta de un consultor** con contraseña temporal de un solo uso | HU-16 | Jefe |
| 19 | [19_jefe_baja_logica…](19_jefe_baja_logica_del_consultor_sin_borrarlo.png) | **Baja lógica**: el consultor queda desactivado, no se borra | HU-16 | Jefe |
| 20 | [20_jefe_historial…](20_jefe_historial_con_nuevas_versiones_y_acciones.png) | Historial con las acciones nuevas (*subió nueva versión*, *creó cuenta del promotor*) | HU-14 | Jefe |
| 21 | [21_celular_lista…](21_celular_lista_de_expedientes_hu12.png) | Lista de expedientes en celular | HU-12 | Consultor |
| 22 | [22_celular_detalle…](22_celular_detalle_con_ipe_hu12.png) | Detalle con IPE y documentos en celular (las acciones pasan a otra línea) | HU-12 | Consultor |
| 23 | [23_robot_reporte…](23_robot_reporte_del_sprint_9_28_de_28.png) | Reporte de Robot Framework del Sprint 9: **28 de 28** casos en PASS | Calidad | — |

## Observación de calidad

Al tomar la captura 22 se detectó que los botones de cada documento (*Descargar*, *Nueva versión*, *Versiones*)
se salían del recuadro en pantallas de 390 px. Se corrigió en `static/expediente-detalle.html` (las acciones ahora
envuelven a otra línea) antes de tomar la captura definitiva.

## Pendiente

- Escaneo de **OpenVAS**: no se ejecutó en esta jornada (ver `results/sprint9-20261122/README.md`).
