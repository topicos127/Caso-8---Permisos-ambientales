*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 6 (Permisos Ambientales)
Library           RequestsLibrary
Library           Collections
Resource          ../recursos/sesion.resource

*** Variables ***
${BASE_URL}       http://localhost:5000

*** Test Cases ***
01 - Validar Registro Por Invitacion (POST /registro)
    [Documentation]    El registro es solo por invitacion: el jefe genera un enlace de un solo uso y la persona
    ...                crea su cuenta con el. Si la cuenta ya existe (corrida anterior), la invitacion responde 409.
    Iniciar Sesion Como Jefe    jefe
    ${invitar}=    Create Dictionary    email=robot_test@ejemplo.com
    ${inv}=    POST On Session    jefe    /invitaciones    json=${invitar}    expected_status=any
    ${status}=    Convert To Integer    ${inv.status_code}
    Should Be True    ${status} in [201, 409]    La invitacion fallo con un codigo inesperado: ${status}
    IF    ${status} == 201
        Create Session    anonimo    ${BASE_URL}
        ${data}=    Create Dictionary
        ...    nombre=Usuario Robot
        ...    email=robot_test@ejemplo.com
        ...    password=Clave12345
        ...    rol=consultor
        ...    invitacion=${inv.json()['token']}
        ...    acepto_terminos=${True}
        ${response}=    POST On Session    anonimo    /registro    json=${data}    expected_status=any
        Status Should Be    201    ${response}
    END

02 - Validar Login Con Usuario Registrado
    [Documentation]    Verifica que el usuario creado en el paso anterior pueda iniciar sesión.
    Create Session    api    ${BASE_URL}
    ${data}=    Create Dictionary    
    ...    email=robot_test@ejemplo.com
    ...    password=Clave12345
    
    ${response}=    POST On Session    api    /login    json=${data}
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()}    acceso
    Should Be True    ${response.json()['acceso']}

03 - Validar Rechazo De Registro Con Contrasena Debil (Seguridad Sprint 6)
    [Documentation]    Verifica que un registro con clave sin mayuscula sea rechazado estrictamente con HTTP 400.
    Create Session    api    ${BASE_URL}
    ${data}=    Create Dictionary    
    ...    nombre=Usuario Debil
    ...    email=debil_test@ejemplo.com
    ...    password=clave12345
    ...    rol=consultor
    
    ${response}=    POST On Session    api    /registro    json=${data}    expected_status=400
    Status Should Be    400    ${response}

04 - Validar Que El Dashboard Devuelve Alertas (HU-05)
    [Documentation]    Verifica que el endpoint del dashboard devuelva la estructura de alertas reales.
    Iniciar Sesion Como Consultor    api
    
    ${response}=    GET On Session    api    /dashboard
    Status Should Be    200    ${response}
    
    ${json}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${json}    alertas
    Dictionary Should Contain Key    ${json}    metricas
    Dictionary Should Contain Key    ${json['metricas']}    alertas

05 - Validar Que El Dashboard Requiere Autenticacion
    [Documentation]    Verifica que el endpoint del dashboard devuelva 401 si no hay credenciales.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /dashboard    expected_status=401
    Status Should Be    401    ${response}

06 - Validar Paginacion Y Busqueda En Expedientes (Sprint 6)
    [Documentation]    Verifica que /expedientes soporte parametros q, page y per_page retornando el objeto paginacion.
    Iniciar Sesion Como Consultor    api
    ${response}=    GET On Session    api    url=/expedientes?q=SP&page=1&per_page=5
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()}    paginacion

07 - Validar Generacion De PDF De Expediente (Sprint 6)
    [Documentation]    Verifica que el endpoint /expedientes/<codigo>/pdf devuelva un documento application/pdf.
    Iniciar Sesion Como Consultor    api
    ${response}=    GET On Session    api    url=/expedientes/SP-A8-2026-001/pdf
    Status Should Be    200    ${response}
    Should Contain    ${response.headers['Content-Type']}    application/pdf

08 - Validar Que El Registro Abierto Esta Cerrado (sin invitacion)
    [Documentation]    Sin invitacion nadie crea una cuenta: el servidor responde 403, aunque los datos sean validos.
    Create Session    api    ${BASE_URL}
    ${data}=    Create Dictionary
    ...    nombre=Intruso Abierto
    ...    email=intruso_abierto@ejemplo.com
    ...    password=Clave12345
    ...    rol=consultor
    ${response}=    POST On Session    api    /registro    json=${data}    expected_status=403
    Status Should Be    403    ${response}
