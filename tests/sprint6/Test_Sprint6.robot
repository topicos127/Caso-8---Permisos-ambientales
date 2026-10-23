*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 6 (Permisos Ambientales)
Library           RequestsLibrary
Library           Collections

*** Variables ***
${BASE_URL}       http://localhost:5000
${AUTH_HEADER}    consultor1@ejemplo.com

*** Test Cases ***
01 - Validar Registro De Nuevo Usuario (POST /registro)
    [Documentation]    Verifica que se pueda registrar un usuario nuevo y devuelva 201.
    Create Session    api    ${BASE_URL}
    ${data}=    Create Dictionary    
    ...    nombre=Usuario Robot
    ...    email=robot_test@ejemplo.com
    ...    password=clave12345
    ...    rol=consultor
    
    # Usamos expected_status=any para que la prueba no falle si el usuario ya existe
    ${response}=    POST On Session    api    /registro    json=${data}    expected_status=any
    
    # Si es la primera vez, devuelve 201. Si ya existe, devuelve 409. Ambas son válidas.
    ${status}=    Convert To Integer    ${response.status_code}
    Should Be True    ${status} in [201, 409]    El registro falló con un código inesperado: ${status}

02 - Validar Login Con Usuario Registrado
    [Documentation]    Verifica que el usuario creado en el paso anterior pueda iniciar sesión.
    Create Session    api    ${BASE_URL}
    ${data}=    Create Dictionary    
    ...    email=robot_test@ejemplo.com
    ...    password=clave12345
    
    ${response}=    POST On Session    api    /login    json=${data}
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()}    acceso
    Should Be True    ${response.json()['acceso']}

03 - Validar Que El Dashboard Devuelve Alertas (HU-05)
    [Documentation]    Verifica que el endpoint del dashboard devuelva la estructura de alertas reales.
    ${headers}=    Create Dictionary    X-Usuario-Email=${AUTH_HEADER}
    Create Session    api    ${BASE_URL}    headers=${headers}
    
    ${response}=    GET On Session    api    /dashboard
    Status Should Be    200    ${response}
    
    ${json}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${json}    alertas
    Dictionary Should Contain Key    ${json}    metricas
    Dictionary Should Contain Key    ${json['metricas']}    alertas

04 - Validar Que El Dashboard Requiere Autenticacion
    [Documentation]    Verifica que el endpoint del dashboard devuelva 401 si no hay credenciales.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /dashboard    expected_status=401
    Status Should Be    401    ${response}