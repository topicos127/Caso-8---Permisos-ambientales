*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 4 (Permisos Ambientales API)
Library           RequestsLibrary
Library           Collections
Library           OperatingSystem
Resource          ../recursos/sesion.resource

*** Variables ***
${BASE_URL}          http://127.0.0.1:5000
${EXPEDIENTE_TEST}    SP-A8-2026-001

*** Test Cases ***
01 - Validar Estado Del Servicio (Health Check)
    [Documentation]    Verifica que la API del servicio de permisos ambientales responda correctamente.
    Create Session    api_session    ${BASE_URL}
    ${response}=    GET On Session    api_session    /health
    Should Be Equal As Integers    ${response.status_code}    200
    ${json}=    Set Variable    ${response.json()}
    Should Be Equal As Strings    ${json['status']}    ok

02 - Validar Descarga De Expediente ZIP Con Indice
    [Documentation]    HU-06: Verifica que la descarga completa de un expediente devuelva un archivo ZIP válido.
    Iniciar Sesion Como Consultor    api_session
    ${response}=    GET On Session    api_session    /expedientes/${EXPEDIENTE_TEST}/descargar-todo
    Should Be Equal As Integers    ${response.status_code}    200
    Should Contain    ${response.headers['Content-Type']}    application/zip
    ${len}=    Get Length    ${response.content}
    Should Be True    ${len} > 0

03 - Validar Calculo De Alertas Y Plazos Legales
    [Documentation]    HU-05 / HU-08: Verifica la consulta de plazos legales y cálculo de días restantes.
    Iniciar Sesion Como Consultor    api_session
    ${response}=    GET On Session    api_session    /expedientes/${EXPEDIENTE_TEST}/alertas
    Should Be Equal As Integers    ${response.status_code}    200
    ${json}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${json}    dias_transcurridos
    Dictionary Should Contain Key    ${json}    dias_restantes_legales
    Dictionary Should Contain Key    ${json}    alerta_vencimiento

04 - Validar Rechazo De Subida Sin Autenticacion
    [Documentation]    HU-01: Verifica que se rechace la subida de un documento si no hay credenciales enviadas.
    Create Session    api_session    ${BASE_URL}
    ${response}=    POST On Session    api_session    /expedientes/${EXPEDIENTE_TEST}/documentos/Linea Base/subir    expected_status=401
    Should Be Equal As Integers    ${response.status_code}    401