*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 9 (Permisos Ambientales)
...               Correcciones previas a lo nuevo del sprint:
...               - HU-09: la consulta publica obedece acceso_publico, muestra el
...                 consultor responsable y el estado publico; solo el jefe lo cambia.
...               - Registro: el promotor ya no se registra solo; su consultor crea
...                 la cuenta con una contrasena temporal que el promotor cambia.
...               - Login: limite de intentos fallidos (429).
...               - HU-01: los documentos no se eliminan; cada subida es una version con
...                 codigo de trazabilidad. PDF con scripts y ZIP con ejecutables se rechazan.
...               - HU-14: el historial registra nuevas versiones, someter y la resolucion.
...               - HU-06: el ZIP lleva el codigo y la fecha.
...               - La contrasena temporal del promotor solo permite cambiarla.
...               - HU-15: Indice de Preparacion del Expediente (IPE).
...               - HU-16: equipo de consultores: alta con clave temporal, baja logica y
...                 reasignacion de expedientes (solo el jefe).
Library           RequestsLibrary
Library           Collections
Resource          ../recursos/sesion.resource
Suite Setup       Preparar Suite
Suite Teardown    Run Keyword And Ignore Error    Dejar 001 Publico

*** Variables ***
${JEFE_EMAIL}            jefe1@ejemplo.com
${JEFE_PASSWORD}         Jefe2026*
${EXP_C1}                SP-A8-2026-001
${MOTIVO}                Revision interna Robot Sprint 9
${CLAVE_NUEVA}           Nueva2026x
${CLAVE_PROPIA}           Equipo2026x

*** Test Cases ***
# ---------------- HU-09: consulta publica ----------------

01 - HU-09 La Consulta Publica Muestra Consultor Y Estado Publico
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /consulta/${EXP_C1}    expected_status=200
    ${exp}=    Set Variable    ${r.json()['expediente']}
    Should Be Equal    ${exp['consultor']}    Consultor Uno
    Should Be True    $exp['estado_publico'] in ('Pendiente de subsanación', 'En evaluación', 'Aprobado', 'Rechazado')
    Dictionary Should Not Contain Key    ${exp}    promotor_email

02 - HU-09 Solo El Jefe Cambia El Acceso Publico
    Iniciar Sesion Como Consultor
    ${datos}=    Create Dictionary    acceso_publico=${False}
    POST On Session    consultor    /expedientes/${EXP_C1}/acceso-publico    json=${datos}    expected_status=403

03 - HU-09 Sin Acceso Publico No Se Entrega Ningun Dato
    Cambiar Acceso Publico    ${False}
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /consulta/${EXP_C1}    expected_status=403
    Dictionary Should Not Contain Key    ${r.json()}    expediente

04 - HU-09 El Cambio De Acceso Queda En El Historial
    Iniciar Sesion Como Jefe
    ${entradas}=    Historial De    jefe    ${EXP_C1}
    Should Be Equal    ${entradas[0]['accion']}    cambió acceso público
    Should Be Equal    ${entradas[0]['usuario_email']}    ${JEFE_EMAIL}

05 - HU-09 El Jefe Vuelve A Publicar El Proyecto
    Cambiar Acceso Publico    ${True}
    Create Session    anonimo    ${BASE_URL}
    GET On Session    anonimo    /consulta/${EXP_C1}    expected_status=200

# ---------------- Registro y cuenta del promotor ----------------

06 - El Promotor No Se Registra Solo
    [Documentation]    Antes, quien se registrara primero con el correo de un promotor veia sus expedientes.
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    nombre=Promotor Falso    email=promotor_falso_${SUFIJO}@ejemplo.com
    ...    password=Clave12345    rol=promotor
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    Rol no permitido

07 - El Consultor Crea La Cuenta Del Promotor
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente    consultor    I    ${PROMOTOR_NUEVO}
    Set Suite Variable    ${COD_PROM}    ${codigo}
    ${r}=    POST On Session    consultor    /expedientes/${COD_PROM}/promotor/cuenta    expected_status=201
    Should Be Equal    ${r.json()['email']}    ${PROMOTOR_NUEVO}
    Set Suite Variable    ${CLAVE_TEMPORAL}    ${r.json()['password_temporal']}
    ${entradas}=    Historial De    consultor    ${COD_PROM}
    Should Be Equal    ${entradas[0]['accion']}    creó cuenta del promotor

07b - Con La Contrasena Temporal Solo Se Puede Cambiarla
    [Documentation]    El login funciona, pero todo lo demas responde 403 hasta cambiar la contrasena.
    Iniciar Sesion    nuevo_promotor    ${PROMOTOR_NUEVO}    ${CLAVE_TEMPORAL}
    ${r}=    GET On Session    nuevo_promotor    /sesion    expected_status=200
    Should Be True    ${r.json()['debe_cambiar_clave']}
    FOR    ${ruta}    IN    /expedientes/${COD_PROM}    /expedientes    /dashboard
        ${r}=    GET On Session    nuevo_promotor    ${ruta}    expected_status=403
        Should Be True    ${r.json()['cambio_clave_obligatorio']}
    END

08 - La Cuenta Del Promotor No Se Crea Dos Veces
    Iniciar Sesion Como Consultor
    POST On Session    consultor    /expedientes/${COD_PROM}/promotor/cuenta    expected_status=409

09 - Un Promotor No Crea Cuentas
    Iniciar Sesion Como Promotor
    POST On Session    promotor    /expedientes/${EXP_C1}/promotor/cuenta    expected_status=403

10 - El Promotor Cambia Su Contrasena Temporal
    Iniciar Sesion    nuevo_promotor    ${PROMOTOR_NUEVO}    ${CLAVE_TEMPORAL}
    ${mala}=    Create Dictionary    actual=NoEsLaClave1    nueva=${CLAVE_NUEVA}
    POST On Session    nuevo_promotor    /cuenta/contrasena    json=${mala}    expected_status=400
    ${debil}=    Create Dictionary    actual=${CLAVE_TEMPORAL}    nueva=debil
    POST On Session    nuevo_promotor    /cuenta/contrasena    json=${debil}    expected_status=400
    ${igual}=    Create Dictionary    actual=${CLAVE_TEMPORAL}    nueva=${CLAVE_TEMPORAL}
    POST On Session    nuevo_promotor    /cuenta/contrasena    json=${igual}    expected_status=400
    ${buena}=    Create Dictionary    actual=${CLAVE_TEMPORAL}    nueva=${CLAVE_NUEVA}
    POST On Session    nuevo_promotor    /cuenta/contrasena    json=${buena}    expected_status=200
    Iniciar Sesion    nuevo_promotor    ${PROMOTOR_NUEVO}    ${CLAVE_NUEVA}
    ${r}=    GET On Session    nuevo_promotor    /sesion    expected_status=200
    Should Not Be True    ${r.json()['debe_cambiar_clave']}
    GET On Session    nuevo_promotor    /expedientes/${COD_PROM}    expected_status=200

# ---------------- Login ----------------

11 - Cinco Intentos Fallidos Bloquean El Login
    [Documentation]    Cuentan solo los fallos, por correo e IP; el sexto intento responde 429.
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    email=fuerza_bruta_${SUFIJO}@ejemplo.com    password=NoEsLaClave1
    FOR    ${i}    IN RANGE    5
        POST On Session    anonimo    /login    json=${datos}    expected_status=401
    END
    ${r}=    POST On Session    anonimo    /login    json=${datos}    expected_status=429
    Should Contain    ${r.json()['mensaje']}    Demasiados intentos

# ---------------- HU-14: historial completo ----------------

12 - HU-01 Un Documento No Se Elimina Y Cada Subida Es Una Version Con Codigo
    [Documentation]    Eliminar responde 405; volver a subir crea la version 2, con un codigo
    ...                de trazabilidad distinto, y queda en el historial.
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente    consultor    I
    Set Suite Variable    ${COD_HIST}    ${codigo}
    ${r}=    GET On Session    consultor    /expedientes/${COD_HIST}
    @{carpetas}=    Evaluate    [d['carpeta'] for d in $r.json()['documentos']]
    FOR    ${carpeta}    IN    @{carpetas}
        Subir PDF    consultor    ${COD_HIST}    ${carpeta}
    END
    ${carpeta_url}=    Evaluate    urllib.parse.quote($carpetas[0])    modules=urllib.parse
    ${r}=    DELETE On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/eliminar    expected_status=405
    Should Contain    ${r.json()['mensaje']}    nueva versión
    Subir PDF    consultor    ${COD_HIST}    ${carpetas[0]}
    ${entradas}=    Historial De    consultor    ${COD_HIST}
    Should Be Equal    ${entradas[0]['accion']}    subió nueva versión
    Should Be Equal    ${entradas[0]['usuario_email']}    ${CONSULTOR_EMAIL}
    ${r}=    GET On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/versiones    expected_status=200
    ${versiones}=    Set Variable    ${r.json()['versiones']}
    Length Should Be    ${versiones}    2
    Should Be Equal As Integers    ${versiones[0]['version']}    2
    Should Not Be Equal    ${versiones[0]['codigo_trazabilidad']}    ${versiones[1]['codigo_trazabilidad']}
    Should Start With    ${versiones[0]['codigo_trazabilidad']}    ${COD_HIST}-D
    GET On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/versiones/1/descargar    expected_status=200
    ${r}=    GET On Session    consultor    /documentos/trazabilidad/${versiones[1]['codigo_trazabilidad']}    expected_status=200
    Should Be Equal    ${r.json()['version']['carpeta']}    ${carpetas[0]}
    Should Be Equal As Integers    ${r.json()['version']['version']}    1
    ${r}=    GET On Session    consultor    /expedientes/${COD_HIST}    expected_status=200
    Should Be Equal    ${r.json()['documentos'][0]['codigo_trazabilidad']}    ${versiones[0]['codigo_trazabilidad']}

12b - HU-01 Un PDF Con Script O Un ZIP Con Ejecutable Se Rechaza
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${COD_HIST}
    ${carpeta_url}=    Evaluate    urllib.parse.quote($r.json()['documentos'][1]['carpeta'])    modules=urllib.parse
    ${pdf}=    Evaluate    {'archivo': ('malo.pdf', b'%PDF-1.4\\n1 0 obj << /S /JavaScript /JS (app.alert(1)) >> endobj\\n', 'application/pdf')}
    ${r}=    POST On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/subir
    ...    files=${pdf}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    contenido activo
    ${zip}=    Evaluate    {'archivo': ('malo.zip', __import__('base64').b64decode('UEsDBBQAAAAAALZgdl2AflBYBAAAAAQAAAAJAAAAc2V0dXAuZXhlTVqQAFBLAQIUABQAAAAAALZgdl2AflBYBAAAAAQAAAAJAAAAAAAAAAAAAACAAQAAAABzZXR1cC5leGVQSwUGAAAAAAEAAQA3AAAAKwAAAAAA'), 'application/zip')}
    ${r}=    POST On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/subir
    ...    files=${zip}    expected_status=400
    ${r}=    GET On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/versiones
    Length Should Be    ${r.json()['versiones']}    1

13 - HU-14 Someter Y La Resolucion Quedan En El Historial
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    motivo=${MOTIVO}
    POST On Session    jefe    /expedientes/${COD_HIST}/aprobar    json=${datos}    expected_status=200
    Iniciar Sesion Como Consultor
    POST On Session    consultor    /expedientes/${COD_HIST}/someter    expected_status=200
    ${entradas}=    Historial De    consultor    ${COD_HIST}
    Should Be Equal    ${entradas[0]['accion']}    sometió
    POST On Session    consultor    /expedientes/${COD_HIST}/aprobar-miambiente    expected_status=200
    ${entradas}=    Historial De    consultor    ${COD_HIST}
    Should Be Equal    ${entradas[0]['accion']}    registró aprobación de MiAmbiente

# ---------------- HU-06 ----------------

14 - HU-06 El ZIP Lleva El Codigo Y La Fecha
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${EXP_C1}/descargar-todo    expected_status=200
    ${hoy}=    Evaluate
    ...    datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()
    ...    modules=datetime
    Should Contain    ${r.headers['Content-Disposition']}    ${EXP_C1}_${hoy}.zip

# ---------------- HU-15: Indice de Preparacion del Expediente ----------------
# Los expedientes del seed dependen de la fecha de hoy; los valores exactos se
# prueban con expedientes nuevos (plazo en curso: P = 100, V = 100).

15 - HU-15 Un Expediente Nuevo Sin Documentos Vale 50
    [Documentation]    D = 0, P = 100, V = 100: 0,3 * 100 + 0,2 * 100 = 50, en preparacion.
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente    consultor    I
    Set Suite Variable    ${COD_IPE}    ${codigo}
    ${r}=    GET On Session    consultor    /expedientes/${COD_IPE}    expected_status=200
    ${ipe}=    Set Variable    ${r.json()['ipe']}
    Should Be Equal As Integers    ${ipe['ipe']}    50
    Should Be Equal    ${ipe['banda']}    en_preparacion
    Should Be Equal As Integers    ${ipe['componentes']['documentos']}    0
    ${textos}=    Evaluate    [a['texto'] for a in $ipe['acciones']]
    Should Contain    ${textos}    Subir Línea Base
    Should Contain    ${textos}    Subir Plan de Manejo
    Should Contain    ${textos}    Subir Anexos Legales

16 - HU-15 Con Todos Los Documentos Vale 100 Y Pide La Aprobacion Del Jefe
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${COD_IPE}
    FOR    ${doc}    IN    @{r.json()['documentos']}
        Subir PDF    consultor    ${COD_IPE}    ${doc['carpeta']}
    END
    ${r}=    GET On Session    consultor    /expedientes/${COD_IPE}    expected_status=200
    ${ipe}=    Set Variable    ${r.json()['ipe']}
    Should Be Equal As Integers    ${ipe['ipe']}    100
    Should Be Equal    ${ipe['banda']}    listo
    ${textos}=    Evaluate    [a['texto'] for a in $ipe['acciones']]
    Should Be Equal    ${textos[0]}    Pedir la aprobación interna al jefe
    Length Should Be    ${textos}    1

17 - HU-15 El Listado Trae El IPE Y Se Ordena De Menor A Mayor
    Iniciar Sesion Como Jefe
    ${r}=    GET On Session    jefe    url=/expedientes?orden=ipe&per_page=100    expected_status=200
    ${lista}=    Set Variable    ${r.json()['expedientes']}
    ${abiertos}=    Evaluate    [e for e in $lista if e['estado'] not in ('aprobado', 'rechazado')]
    Should Not Be Empty    ${abiertos}
    FOR    ${e}    IN    @{abiertos}
        Dictionary Should Contain Key    ${e['ipe']}    valor
        Dictionary Should Contain Key    ${e['ipe']}    banda
    END
    ${valores}=    Evaluate    [e['ipe']['valor'] for e in $abiertos]
    ${ordenados}=    Evaluate    sorted($valores)
    Should Be Equal    ${valores}    ${ordenados}
    GET On Session    jefe    url=/expedientes?orden=inventado    expected_status=400

18 - HU-15 El Promotor No Recibe El IPE
    Iniciar Sesion Como Promotor
    ${r}=    GET On Session    promotor    /expedientes/${EXP_C1}    expected_status=200
    Should Be Equal    ${r.json()['ipe']}    ${None}
    ${r}=    GET On Session    promotor    /expedientes    expected_status=200
    FOR    ${e}    IN    @{r.json()['expedientes']}
        Dictionary Should Not Contain Key    ${e}    ipe
    END
    ${r}=    GET On Session    promotor    /dashboard    expected_status=200
    Should Be Empty    ${r.json()['prioridades']}

19 - HU-15 El Panel Del Jefe Trae Las Prioridades
    Iniciar Sesion Como Jefe
    ${r}=    GET On Session    jefe    /dashboard    expected_status=200
    ${p}=    Set Variable    ${r.json()['prioridades']}
    Should Not Be Empty    ${p}
    ${n}=    Get Length    ${p}
    Should Be True    ${n} <= 5
    ${valores}=    Evaluate    [x['ipe'] for x in $p]
    ${ordenados}=    Evaluate    sorted($valores)
    Should Be Equal    ${valores}    ${ordenados}
    Dictionary Should Contain Key    ${p[0]}    proxima_accion

# ---------------- HU-16: equipo de consultores (alta, baja y reasignacion) ----------------

20 - Equipo: Solo El Jefe Gestiona A Los Consultores
    Iniciar Sesion Como Consultor
    GET On Session    consultor    /consultores    expected_status=403
    Iniciar Sesion Como Promotor
    GET On Session    promotor    /consultores    expected_status=403
    Create Session    anonimo    ${BASE_URL}
    GET On Session    anonimo    /consultores    expected_status=401

21 - Equipo: El Jefe Da De Alta Un Consultor Con Clave Temporal
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    nombre=Consultor Robot S9    email=${CONSULTOR_NUEVO}
    ${r}=    POST On Session    jefe    /consultores    json=${datos}    expected_status=201
    Should Not Be Empty    ${r.json()['password_temporal']}
    Set Suite Variable    ${TEMPORAL}    ${r.json()['password_temporal']}
    Set Suite Variable    ${CONSULTOR_NUEVO_ID}    ${r.json()['id']}
    POST On Session    jefe    /consultores    json=${datos}    expected_status=409
    ${debil}=    Create Dictionary    nombre=Otro Robot    email=otro_${SUFIJO}@ejemplo.com    password=123
    POST On Session    jefe    /consultores    json=${debil}    expected_status=400
    ${r}=    GET On Session    jefe    /consultores    expected_status=200
    ${fila}=    Evaluate    [c for c in $r.json()['consultores'] if c['email'] == '${CONSULTOR_NUEVO}'][0]
    Should Be True    ${fila['activo']}
    Should Be Equal As Integers    ${fila['expedientes']}    0

22 - Equipo: El Nuevo Consultor Debe Cambiar La Clave Antes De Trabajar
    Iniciar Sesion    nuevo    ${CONSULTOR_NUEVO}    ${TEMPORAL}
    ${r}=    GET On Session    nuevo    /sesion    expected_status=200
    Should Be True    ${r.json()['debe_cambiar_clave']}
    ${r}=    GET On Session    nuevo    /expedientes    expected_status=403
    Should Be True    ${r.json()['cambio_clave_obligatorio']}
    ${datos}=    Create Dictionary    actual=${TEMPORAL}    nueva=${CLAVE_PROPIA}
    POST On Session    nuevo    /cuenta/contrasena    json=${datos}    expected_status=200
    GET On Session    nuevo    /expedientes    expected_status=200

23 - Equipo: Reasignar Exige Que El Consultor Este Desactivado
    Iniciar Sesion    nuevo    ${CONSULTOR_NUEVO}    ${CLAVE_PROPIA}
    ${codigo}=    Crear Expediente    nuevo    I
    Set Suite Variable    ${COD_EQUIPO}    ${codigo}
    Iniciar Sesion Como Jefe
    ${destino}=    Id Del Consultor    ${CONSULTOR_EMAIL}
    Set Suite Variable    ${DESTINO_ID}    ${destino}
    ${datos}=    Create Dictionary    destino_id=${DESTINO_ID}
    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/reasignar    json=${datos}    expected_status=409

24 - Equipo: Desactivar Impide Entrar Y Cierra La Sesion Abierta
    Iniciar Sesion Como Jefe
    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/desactivar    expected_status=200
    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/desactivar    expected_status=409
    GET On Session    nuevo    /sesion    expected_status=401
    Create Session    anonimo    ${BASE_URL}    headers=${CABECERA}
    ${datos}=    Create Dictionary    email=${CONSULTOR_NUEVO}    password=${CLAVE_PROPIA}
    ${r}=    POST On Session    anonimo    /login    json=${datos}    expected_status=403
    Should Contain    ${r.json()['mensaje']}    desactivada
    ${mala}=    Create Dictionary    email=${CONSULTOR_NUEVO}    password=Incorrecta2026x
    POST On Session    anonimo    /login    json=${mala}    expected_status=401

25 - Equipo: Reasignar Pasa Los Expedientes Y Queda En El Historial
    Iniciar Sesion Como Jefe
    ${mismo}=    Create Dictionary    destino_id=${CONSULTOR_NUEVO_ID}
    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/reasignar    json=${mismo}    expected_status=400
    ${datos}=    Create Dictionary    destino_id=${DESTINO_ID}
    ${r}=    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/reasignar    json=${datos}    expected_status=200
    Should Be Equal As Integers    ${r.json()['reasignados']}    1
    ${entradas}=    Historial De    jefe    ${COD_EQUIPO}
    Should Be Equal    ${entradas[0]['accion']}    reasignó
    Should Be Equal    ${entradas[0]['usuario_email']}    ${JEFE_EMAIL}
    Iniciar Sesion Como Consultor
    GET On Session    consultor    /expedientes/${COD_EQUIPO}    expected_status=200

26 - Equipo: Reactivar Devuelve El Acceso
    Iniciar Sesion Como Jefe
    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/activar    expected_status=200
    POST On Session    jefe    /consultores/${CONSULTOR_NUEVO_ID}/activar    expected_status=409
    Iniciar Sesion    nuevo    ${CONSULTOR_NUEVO}    ${CLAVE_PROPIA}

*** Keywords ***
Preparar Suite
    ${sufijo}=    Evaluate    int(time.time())    modules=time
    Set Suite Variable    ${SUFIJO}    ${sufijo}
    Set Suite Variable    ${PROMOTOR_NUEVO}    promotor_s9_${sufijo}@ejemplo.com
    Set Suite Variable    ${CONSULTOR_NUEVO}    consultor_s9_${sufijo}@ejemplo.com
    ${cabecera}=    Create Dictionary    X-Requested-With=fetch
    Set Suite Variable    ${CABECERA}    ${cabecera}

Id Del Consultor
    [Documentation]    Id de un consultor segun su correo (solo el jefe puede listarlos).
    [Arguments]    ${email}
    ${r}=    GET On Session    jefe    /consultores    expected_status=200
    ${id}=    Evaluate    [c['id'] for c in $r.json()['consultores'] if c['email'] == '${email}'][0]
    RETURN    ${id}

Iniciar Sesion Como Jefe
    [Arguments]    ${alias}=jefe
    Iniciar Sesion    ${alias}    ${JEFE_EMAIL}    ${JEFE_PASSWORD}

Cambiar Acceso Publico
    [Arguments]    ${valor}
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    acceso_publico=${valor}
    ${r}=    POST On Session    jefe    /expedientes/${EXP_C1}/acceso-publico    json=${datos}    expected_status=200
    Should Be Equal    ${r.json()['acceso_publico']}    ${valor}

Dejar 001 Publico
    [Documentation]    La suite del Sprint 5 consulta el 001 sin sesion: debe quedar publico.
    Cambiar Acceso Publico    ${True}

Crear Expediente
    [Arguments]    ${alias}    ${categoria}    ${promotor_email}=${EMPTY}
    ${datos}=    Create Dictionary    proyecto=Expediente Robot Sprint 9    promotor=Promotor Robot S9
    ...    categoria=${categoria}    promotor_email=${promotor_email}
    ${r}=    POST On Session    ${alias}    /expedientes    json=${datos}    expected_status=201
    RETURN    ${r.json()['codigo']}

Historial De
    [Documentation]    Entradas del expediente, de la mas reciente a la mas antigua.
    [Arguments]    ${alias}    ${codigo}
    ${r}=    GET On Session    ${alias}    /expedientes/${codigo}/historial
    RETURN    ${r.json()['historial']}

Subir PDF
    [Arguments]    ${alias}    ${codigo}    ${carpeta}
    ${carpeta_url}=    Evaluate    urllib.parse.quote($carpeta)    modules=urllib.parse
    ${archivos}=    Evaluate    {'archivo': ('robot_s9.pdf', b'%PDF-1.4\\n% prueba Robot Sprint 9\\n', 'application/pdf')}
    POST On Session    ${alias}    /expedientes/${codigo}/documentos/${carpeta_url}/subir
    ...    files=${archivos}    expected_status=200
