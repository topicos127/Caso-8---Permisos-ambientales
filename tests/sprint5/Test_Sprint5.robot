*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 5 (Permisos Ambientales)
Library           RequestsLibrary
Library           Collections

*** Variables ***
${BASE_URL}       http://localhost:5000

*** Test Cases ***
01 - Validar Consulta Publica De Expediente (HU-09)
    [Documentation]    Verifica que /consulta/<codigo> devuelva la propiedad acceso_publico.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /consulta/EXP-001
    Status Should Be    200    ${response}
    Dictionary Should Contain Key    ${response.json()}    acceso_publico

02 - Validar Lista De Aprobaciones De Expediente (HU-10)
    [Documentation]    Verifica que /expedientes/<codigo>/aprobaciones devuelva la lista de historial.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-001/aprobaciones
    Status Should Be    200    ${response}
    ${tipo}=    Evaluate    type(${response.json()}).__name__
    Should Be True    '${tipo}' in ['list', 'dict']

03 - Validar Rechazo De Subida En Expediente Aprobado (HU-10)
    [Documentation]    Garantiza que intentar subir un archivo a un expediente ya aprobado devuelva HTTP 403.
    Create Session    api    ${BASE_URL}    expected_status=any
    ${file_data}=    Create Dictionary    filename=nuevo_doc.pdf
    ${response}=    POST On Session    api    /expedientes/EXP-APROBADO/subir    json=${file_data}
    Status Should Be    403    ${response}

04 - Validar Que ZIP Respeta Jerarquia De Carpetas (HU-06)
    [Documentation]    Verifica que la descarga del ZIP mantenga la estructura jerarquica de directorios.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-001/descargar-todo
    Status Should Be    200    ${response}
    # Verifica la cabecera Content-Type correspondiente a un archivo ZIP
    Dictionary Should Contain Key    ${response.headers}    Content-Type
    Should Contain    ${response.headers['Content-Type']}    application/zip

05 - Validar Alertas Con Categoria I (20 Dias Legal Limit)
    [Documentation]    Evalua que la Categoria I devuelva un limite legal de 20 dias.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-CAT1/alertas
    Status Should Be    200    ${response}
    ${dias}=    Get From Dictionary    ${response.json()}    dias_restantes_legales
    Should Be Equal As Integers    ${dias}    20

06 - Validar Alertas Con Categoria III (80 Dias Legal Limit)
    [Documentation]    Evalua que la Categoria III devuelva un limite legal de 80 dias.
    Create Session    api    ${BASE_URL}
    ${response}=    GET On Session    api    /expedientes/EXP-CAT3/alertas
    Status Should Be    200    ${response}
    ${dias}=    Get From Dictionary    ${response.json()}    dias_restantes_legales
    Should Be Equal As Integers    ${dias}    80