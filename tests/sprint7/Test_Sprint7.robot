*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 7 (Permisos Ambientales)
...               Seguridad (sesion real y permisos por expediente) y HU-07
...               (semaforo de plazos legales).
Library           RequestsLibrary
Library           Collections
Resource          ../recursos/sesion.resource

*** Variables ***
${EXP_PENDIENTE}    SP-A8-2026-001
${EXP_APROBADO}     SP-A8-2026-003
@{SEMAFORO_EN_TRAMITE}    en_plazo    por_vencer    vencido
@{ESTADOS_RESUELTOS}      aprobado    rechazado

*** Test Cases ***
01 - La Cabecera X-Usuario-Email Ya No Da Acceso
    [Documentation]    Antes bastaba con mandar el correo de otro usuario en la cabecera.
    ${headers}=    Create Dictionary    X-Usuario-Email=${CONSULTOR_EMAIL}
    Create Session    anonimo    ${BASE_URL}    headers=${headers}
    ${r}=    GET On Session    anonimo    /expedientes    expected_status=401
    ${r}=    GET On Session    anonimo    /expedientes/${EXP_PENDIENTE}    expected_status=401

02 - El ZIP, El PDF Y Las Alertas Piden Sesion
    [Documentation]    Eran publicos: cualquiera bajaba los documentos de un expediente.
    Create Session    anonimo    ${BASE_URL}
    GET On Session    anonimo    /expedientes/${EXP_PENDIENTE}/descargar-todo    expected_status=401
    GET On Session    anonimo    /expedientes/${EXP_PENDIENTE}/pdf    expected_status=401
    GET On Session    anonimo    /expedientes/${EXP_PENDIENTE}/alertas    expected_status=401

03 - Un Promotor No Ve Expedientes Ajenos
    [Documentation]    El expediente 003 no tiene a promotor1 como promotor.
    Iniciar Sesion Como Promotor
    GET On Session    promotor    /expedientes/${EXP_APROBADO}    expected_status=403
    GET On Session    promotor    /expedientes/${EXP_APROBADO}/descargar-todo    expected_status=403

04 - Un Promotor No Puede Aprobar
    Iniciar Sesion Como Promotor
    ${datos}=    Create Dictionary    motivo=Intento del promotor
    POST On Session    promotor    /expedientes/${EXP_PENDIENTE}/aprobar    json=${datos}    expected_status=403

05 - El Registro No Acepta Roles Inventados
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    nombre=Intruso    email=intruso_robot@ejemplo.com
    ...    password=Clave12345    rol=admin
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    Rol no permitido

06 - Un Codigo Inexistente Da 404 Y No 500
    Iniciar Sesion Como Consultor
    ${datos}=    Create Dictionary    motivo=Prueba
    POST On Session    consultor    /expedientes/NO-EXISTE/aprobar    json=${datos}    expected_status=404
    POST On Session    consultor    /expedientes/NO-EXISTE/someter    expected_status=404
    GET On Session    consultor    /expedientes/NO-EXISTE/alertas    expected_status=404

07 - Parametros Invalidos Dan 400 Y No 500
    Iniciar Sesion Como Consultor
    GET On Session    consultor    url=/expedientes?page=abc    expected_status=400
    GET On Session    consultor    url=/expedientes?per_page=1000    expected_status=400
    ${datos}=    Create Dictionary    proyecto=Proyecto Robot    promotor=Promotor Robot    categoria=IV
    POST On Session    consultor    /expedientes    json=${datos}    expected_status=400

08 - Un POST Con Sesion Sin X-Requested-With Se Rechaza
    [Documentation]    Proteccion contra CSRF: un formulario de otro sitio no puede mandar esa cabecera.
    Iniciar Sesion Como Consultor
    ${sin_cabecera}=    Create Dictionary    X-Requested-With=${EMPTY}
    ${datos}=    Create Dictionary    motivo=Prueba
    ${r}=    POST On Session    consultor    /expedientes/${EXP_PENDIENTE}/aprobar    json=${datos}
    ...    headers=${sin_cabecera}    expected_status=403
    Should Contain    ${r.json()['mensaje']}    X-Requested-With

09 - Cerrar Sesion Corta El Acceso
    Iniciar Sesion Como Consultor
    GET On Session    consultor    /expedientes    expected_status=200
    POST On Session    consultor    /logout    expected_status=200
    GET On Session    consultor    /expedientes    expected_status=401

10 - HU-07 Un Expediente Resuelto Deja De Contar
    [Documentation]    El 003 esta aprobado: antes salia "Vencido" para siempre.
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${EXP_APROBADO}/alertas
    Should Be Equal    ${r.json()['estado_semaforo']}    resuelto
    Should Be Equal    ${r.json()['dias_restantes_legales']}    ${None}

11 - HU-07 El Limite Y El Umbral Vienen De La Categoria
    [Documentation]    001 es categoria II: 40 dias, "por vencer" desde 10.
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${EXP_PENDIENTE}/alertas
    ${json}=    Set Variable    ${r.json()}
    Should Be Equal As Integers    ${json['limite_dias']}    40
    Should Be Equal As Integers    ${json['umbral_por_vencer']}    10
    Should Be True    '${json['estado_semaforo']}' in ['en_plazo', 'por_vencer', 'vencido']
    ${suma}=    Evaluate    ${json['dias_transcurridos']} + ${json['dias_restantes_legales']}
    Should Be Equal As Integers    ${suma}    40

12 - HU-07 Un Expediente Nuevo Empieza En Plazo
    Iniciar Sesion Como Consultor
    ${datos}=    Create Dictionary    proyecto=Expediente Robot HU-07    promotor=Promotor Robot    categoria=I
    ${r}=    POST On Session    consultor    /expedientes    json=${datos}    expected_status=201
    ${codigo}=    Set Variable    ${r.json()['codigo']}
    ${r}=    GET On Session    consultor    /expedientes/${codigo}/alertas
    Should Be Equal    ${r.json()['estado_semaforo']}    en_plazo
    Should Be Equal As Integers    ${r.json()['dias_transcurridos']}    0
    Should Be Equal As Integers    ${r.json()['dias_restantes_legales']}    20

13 - HU-07 Todo Expediente Muestra Un Estado De Semaforo Valido
    [Documentation]    Recorre todos los expedientes del consultor (todas las paginas).
    ...                En tramite: en_plazo, por_vencer o vencido.
    ...                Aprobado o rechazado: resuelto (el plazo ya no corre).
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    url=/expedientes?page=1&per_page=100
    ${paginacion}=    Set Variable    ${r.json()['paginacion']}
    Should Be True    ${paginacion['total']} > 0    msg=El consultor no tiene expedientes para revisar
    FOR    ${pagina}    IN RANGE    1    ${paginacion['pages']} + 1
        ${r}=    GET On Session    consultor    url=/expedientes?page=${pagina}&per_page=100
        FOR    ${exp}    IN    @{r.json()['expedientes']}
            Run Keyword And Continue On Failure    Validar Semaforo De Expediente    ${exp}
        END
    END
    Log    Expedientes revisados: ${paginacion['total']}

*** Keywords ***
Validar Semaforo De Expediente
    [Documentation]    Compara estado_semaforo de /alertas con el estado del expediente.
    [Arguments]    ${exp}
    ${r}=    GET On Session    consultor    /expedientes/${exp['codigo']}/alertas
    ${semaforo}=    Set Variable    ${r.json()['estado_semaforo']}
    ${detalle}=    Set Variable    ${exp['codigo']} (estado ${exp['estado']}): estado_semaforo=${semaforo}
    IF    $exp['estado'] in $ESTADOS_RESUELTOS
        Should Be Equal    ${semaforo}    resuelto    msg=${detalle}
    ELSE
        Should Contain    ${SEMAFORO_EN_TRAMITE}    ${semaforo}    msg=${detalle}
    END
