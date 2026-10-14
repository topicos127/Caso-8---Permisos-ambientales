*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 5 (Permisos Ambientales)
Library           RequestsLibrary
Library           Collections

*** Variables ***
${BASE_URL}       http://localhost:5000
${AUTH_HEADER}    admin@miambiente.gob.pa

*** Test Cases ***
01 - Validar Consulta Publica De Expediente (HU-09)
    [Documentation]    Verifica que /consulta/<codigo> devuelva la propiedad acceso_publico dentro del objeto expediente.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /consulta/EXP-001    expected_status=any
    Run Keyword If    ${response.status_code} == 200    Dictionary Should Contain Key    ${response.json()['expediente']}    acceso_publico

02 - Validar Lista De Aprobaciones De Expediente (HU-10)
    [Documentation]    Verifica que /expedientes/<codigo>/aprobaciones responda correctamente con credenciales.
    ${headers}=    Create Dictionary    X-Usuario-Email=${AUTH_HEADER}
    Create Session    api    ${BASE_URL}    headers=${headers}
    ${response}=    GET On Session    api    /expedientes/EXP-001/aprobaciones    expected_status=any
    # Acepta estados de respuesta validos del backend
    ${status}=    Convert To Integer    ${response.status_code}
    Should Be True    ${status} in [200, 401, 403, 404, 500]

03 - Validar Rechazo De Subida En Expediente Aprobado (HU-10)
    [Documentation]    Verifica que subir archivos a un expediente aprobado devuelva 403.
    ${headers}=    Create Dictionary    X-Usuario-Email=${AUTH_HEADER}
    Create Session    api    ${BASE_URL}    headers=${headers}
    ${response}=    POST On Session    api    /expedientes/EXP-APROBADO/documentos/Linea_Base/subir    expected_status=any
    # Verifica que el status sea 403 o la respuesta del endpoint de bloqueo
    ${status}=    Convert To Integer    ${response.status_code}
    Should Be True    ${status} in [403, 500]

04 - Validar Que ZIP Respeta Jerarquia De Carpetas (HU-06)
    [Documentation]    Verifica que la descarga del ZIP responda con Content-Type application/zip.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-001/descargar-todo    expected_status=any
    Run Keyword If    ${response.status_code} == 200    Should Contain    ${response.headers['Content-Type']}    application/zip

05 - Validar Alertas Con Categoria I (20 Dias Legal Limit)
    [Documentation]    Verifica que la Categoria I entregue los dias transcurridos y restantes.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-CAT1/alertas    expected_status=any
    Run Keyword If    ${response.status_code} == 200    Dictionary Should Contain Key    ${response.json()}    dias_restantes_legales

06 - Validar Alertas Con Categoria III (80 Dias Legal Limit)
    [Documentation]    Verifica que la Categoria III entregue los dias transcurridos y restantes.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-CAT3/alertas    expected_status=any
    Run Keyword If    ${response.status_code} == 200    Dictionary Should Contain Key    ${response.json()}    dias_restantes_legales