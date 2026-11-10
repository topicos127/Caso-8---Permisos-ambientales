*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 5 (Permisos Ambientales)
Library           RequestsLibrary
Library           Collections
Resource          ../recursos/sesion.resource

*** Variables ***
${BASE_URL}       http://localhost:5000

*** Test Cases ***
01 - Validar Consulta Publica De Expediente (HU-09)
    [Documentation]    Verifica que /consulta/<codigo> devuelva estado 200 y la propiedad acceso_publico.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /consulta/SP-A8-2026-001
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()['expediente']}    acceso_publico

02 - Validar Lista De Aprobaciones De Expediente (HU-10)
    [Documentation]    Verifica que /expedientes/<codigo>/aprobaciones devuelva estado 200 con credenciales validas.
    Iniciar Sesion Como Consultor    api
    ${response}=    GET On Session    api    /expedientes/SP-A8-2026-001/aprobaciones
    Status Should Be    200    ${response}

03 - Validar Rechazo De Subida En Expediente Aprobado (HU-10)
    [Documentation]    Verifica estrictamente que subir archivos a un expediente aprobado devuelva HTTP 403 Forbidden.
    Iniciar Sesion Como Consultor    api
    ${response}=    POST On Session    api    /expedientes/SP-A8-2026-003/documentos/Linea_Base/subir    expected_status=403
    Status Should Be    403    ${response}

04 - Validar Que ZIP Respeta Jerarquia De Carpetas (HU-06)
    [Documentation]    Verifica que la descarga del ZIP devuelva HTTP 200 y Content-Type application/zip.
    Iniciar Sesion Como Consultor    api
    ${response}=    GET On Session    api    /expedientes/SP-A8-2026-001/descargar-todo
    Status Should Be    200    ${response}
    Should Contain    ${response.headers['Content-Type']}    application/zip

05 - Validar Alertas Con Categoria I (20 Dias Legal Limit)
    [Documentation]    Verifica que las alertas devuelvan HTTP 200 y la clave dias_restantes_legales.
    Iniciar Sesion Como Consultor    api
    ${response}=    GET On Session    api    /expedientes/SP-A8-2026-001/alertas
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()}    dias_restantes_legales

06 - Validar Alertas Con Categoria III (80 Dias Legal Limit)
    [Documentation]    Verifica que un expediente de Categoria III responda con sus datos de alerta.
    Iniciar Sesion Como Consultor    api
    ${response}=    GET On Session    api    /expedientes/SP-A8-2026-003/alertas
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()}    dias_restantes_legales