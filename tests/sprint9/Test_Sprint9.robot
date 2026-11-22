*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 9 (Permisos Ambientales)
...               Correcciones previas a lo nuevo del sprint:
...               - HU-09: la consulta publica obedece acceso_publico, muestra el
...                 consultor responsable y el estado publico; solo el jefe lo cambia.
...               - Registro: el promotor ya no se registra solo; su consultor crea
...                 la cuenta con una contrasena temporal que el promotor cambia.
...               - Login: limite de intentos fallidos (429).
...               - HU-14: el historial registra eliminar, someter y la resolucion.
...               - HU-06: el ZIP lleva el codigo y la fecha.
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
    Iniciar Sesion    nuevo_promotor    ${PROMOTOR_NUEVO}    ${CLAVE_TEMPORAL}
    GET On Session    nuevo_promotor    /expedientes/${COD_PROM}    expected_status=200
    ${entradas}=    Historial De    consultor    ${COD_PROM}
    Should Be Equal    ${entradas[0]['accion']}    creó cuenta del promotor

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
    ${buena}=    Create Dictionary    actual=${CLAVE_TEMPORAL}    nueva=${CLAVE_NUEVA}
    POST On Session    nuevo_promotor    /cuenta/contrasena    json=${buena}    expected_status=200
    Iniciar Sesion    nuevo_promotor    ${PROMOTOR_NUEVO}    ${CLAVE_NUEVA}

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

12 - HU-14 Eliminar Un Documento Queda En El Historial
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente    consultor    I
    Set Suite Variable    ${COD_HIST}    ${codigo}
    ${r}=    GET On Session    consultor    /expedientes/${COD_HIST}
    @{carpetas}=    Evaluate    [d['carpeta'] for d in $r.json()['documentos']]
    FOR    ${carpeta}    IN    @{carpetas}
        Subir PDF    consultor    ${COD_HIST}    ${carpeta}
    END
    ${carpeta_url}=    Evaluate    urllib.parse.quote($carpetas[0])    modules=urllib.parse
    DELETE On Session    consultor    /expedientes/${COD_HIST}/documentos/${carpeta_url}/eliminar    expected_status=200
    ${entradas}=    Historial De    consultor    ${COD_HIST}
    Should Be Equal    ${entradas[0]['accion']}    eliminó documento
    Should Be Equal    ${entradas[0]['usuario_email']}    ${CONSULTOR_EMAIL}
    Subir PDF    consultor    ${COD_HIST}    ${carpetas[0]}

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

*** Keywords ***
Preparar Suite
    ${sufijo}=    Evaluate    int(time.time())    modules=time
    Set Suite Variable    ${SUFIJO}    ${sufijo}
    Set Suite Variable    ${PROMOTOR_NUEVO}    promotor_s9_${sufijo}@ejemplo.com

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
