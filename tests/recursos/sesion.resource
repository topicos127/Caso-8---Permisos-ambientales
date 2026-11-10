*** Settings ***
Documentation     Keywords comunes (Sprint 7): la API ya no acepta la cabecera
...               X-Usuario-Email; hay que iniciar sesion y usar la cookie.
...               RequestsLibrary guarda la cookie dentro de la sesion creada.
Library           RequestsLibrary
Library           Collections

*** Variables ***
${BASE_URL}              http://localhost:5000
${CONSULTOR_EMAIL}       consultor1@ejemplo.com
${CONSULTOR_PASSWORD}    clave123
${PROMOTOR_EMAIL}        promotor1@ejemplo.com
${PROMOTOR_PASSWORD}     clave456

*** Keywords ***
Iniciar Sesion
    [Documentation]    Crea la sesion ${alias} e inicia sesion con ese usuario.
    ...                La cabecera X-Requested-With la exige el servidor en los POST.
    [Arguments]    ${alias}    ${email}=${CONSULTOR_EMAIL}    ${password}=${CONSULTOR_PASSWORD}
    ${headers}=    Create Dictionary    X-Requested-With=fetch
    Create Session    ${alias}    ${BASE_URL}    headers=${headers}
    ${datos}=    Create Dictionary    email=${email}    password=${password}
    ${resp}=    POST On Session    ${alias}    /login    json=${datos}
    Status Should Be    200    ${resp}
    Should Be True    ${resp.json()['acceso']}

Iniciar Sesion Como Consultor
    [Arguments]    ${alias}=consultor
    Iniciar Sesion    ${alias}    ${CONSULTOR_EMAIL}    ${CONSULTOR_PASSWORD}

Iniciar Sesion Como Promotor
    [Arguments]    ${alias}=promotor
    Iniciar Sesion    ${alias}    ${PROMOTOR_EMAIL}    ${PROMOTOR_PASSWORD}
