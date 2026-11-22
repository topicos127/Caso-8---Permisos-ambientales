*** Settings ***
Documentation    Sprint 2-3. Casos de prueba para el servicio de Login (HU-11) del Sistema de
...              Permisos Ambientales. Valida que el servicio conceda acceso solo
...              con credenciales correctas, y que rechace credenciales invalidas,
...              inexistentes o incompletas.
Library          RequestsLibrary
Library          Collections
Suite Setup      Create Session    api    http://localhost:5000

*** Variables ***
${EMAIL_CONSULTOR}         consultor1@ejemplo.com
${PASSWORD_CONSULTOR}      Clave123
${EMAIL_PROMOTOR}          promotor1@ejemplo.com
${PASSWORD_PROMOTOR}       Clave456
${EMAIL_INVALIDO}          usuario_no_existe@ejemplo.com
${PASSWORD_INCORRECTA}     claveIncorrecta

*** Test Cases ***
El Servicio Esta Activo
    [Documentation]    Verifica que el endpoint raiz confirme que el servicio esta activo.
    ${response}=    GET On Session    api    /
    Should Be Equal As Strings    ${response.status_code}    200
    Should Be Equal    ${response.json()}[estado]    activo

El Endpoint De Salud Responde Correctamente
    [Documentation]    Verifica que /health confirme que el servicio esta operativo.
    ${response}=    GET On Session    api    /health
    Should Be Equal As Strings    ${response.status_code}    200
    Should Be Equal    ${response.json()}[status]    ok

Login Exitoso Con Credenciales De Consultor
    [Documentation]    HU-11: un consultor con credenciales correctas debe obtener acceso.
    ${body}=    Create Dictionary    email=${EMAIL_CONSULTOR}    password=${PASSWORD_CONSULTOR}
    ${response}=    POST On Session    api    /login    json=${body}
    Should Be Equal As Strings    ${response.status_code}    200
    Should Be True    ${response.json()}[acceso]

Login Exitoso Con Credenciales De Promotor
    [Documentation]    HU-11: un promotor con credenciales correctas debe obtener acceso.
    ${body}=    Create Dictionary    email=${EMAIL_PROMOTOR}    password=${PASSWORD_PROMOTOR}
    ${response}=    POST On Session    api    /login    json=${body}
    Should Be Equal As Strings    ${response.status_code}    200
    Should Be True    ${response.json()}[acceso]

Login Fallido Por Contrasena Incorrecta
    [Documentation]    HU-11: si la contrasena no coincide, el sistema debe negar el acceso.
    ${body}=    Create Dictionary    email=${EMAIL_CONSULTOR}    password=${PASSWORD_INCORRECTA}
    ${response}=    POST On Session    api    /login    json=${body}    expected_status=401
    Should Be Equal As Strings    ${response.status_code}    401
    Should Not Be True    ${response.json()}[acceso]

Login Fallido Por Email No Registrado
    [Documentation]    HU-11: un correo que no existe en el sistema no debe obtener acceso.
    ${body}=    Create Dictionary    email=${EMAIL_INVALIDO}    password=${PASSWORD_CONSULTOR}
    ${response}=    POST On Session    api    /login    json=${body}    expected_status=401
    Should Be Equal As Strings    ${response.status_code}    401
    Should Not Be True    ${response.json()}[acceso]

Login Fallido Por Campos Vacios
    [Documentation]    HU-11: una solicitud sin email ni contrasena debe ser rechazada
    ...    de forma controlada (401), no provocar un error interno del servidor.
    ${body}=    Create Dictionary
    ${response}=    POST On Session    api    /login    json=${body}    expected_status=401
    Should Be Equal As Strings    ${response.status_code}    401
    Should Not Be True    ${response.json()}[acceso]
