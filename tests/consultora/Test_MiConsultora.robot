*** Settings ***
Documentation     Mi consultora: datos de la empresa, politica de seguridad (dos pasos obligatorios, sesiones),
...               uso, exportacion completa, registro de accesos y titularidad. Usa empresas nuevas para no
...               tocar las cuentas de la semilla.
Library           RequestsLibrary
Library           Collections
Library           ../plataforma/ayudas.py
Resource          ../recursos/sesion.resource

*** Variables ***
${BASE_URL}       http://localhost:5000
${CODIGO_A}       SP-A8-2026-001
${CODIGO_B}       SP-A8-2026-201
${CLAVE}          Clave12345

*** Test Cases ***
01 - Datos de la empresa: solo el director los edita y se validan
    Iniciar Sesion Como Jefe    jefe
    ${datos}=    Create Dictionary    razon_social=Consultora Demo, S.A.    ruc=155-123-45678    telefono=+507 300-0000
    ...    direccion=Calle 50, Ciudad de Panamá    email_contacto=contacto@demo.com    pie_documento=Documento generado por Consultora Demo
    ${r}=    POST On Session    jefe    /organizacion/datos    json=${datos}
    Status Should Be    200    ${r}
    ${r}=    GET On Session    jefe    /organizacion/datos
    Should Be Equal    ${r.json()['datos']['ruc']}    155-123-45678
    ${malo}=    Create Dictionary    email_contacto=no-es-un-correo
    ${r}=    POST On Session    jefe    /organizacion/datos    json=${malo}    expected_status=any
    Status Should Be    400    ${r}
    Iniciar Sesion Como Consultor    consultor
    ${r}=    GET On Session    consultor    /organizacion/datos    expected_status=any
    Status Should Be    403    ${r}
    ${r}=    POST On Session    consultor    /organizacion/datos    json=${datos}    expected_status=any
    Status Should Be    403    ${r}
    # El resumen PDF se sigue generando con los datos nuevos
    ${r}=    GET On Session    jefe    /expedientes/${CODIGO_A}/pdf
    Should Contain    ${r.headers['Content-Type']}    pdf

02 - El contacto que la consultora elige se ve en la consulta publica
    Iniciar Sesion Como Jefe    jefe
    Create Session    publico    ${BASE_URL}
    ${r}=    GET On Session    publico    /consulta/${CODIGO_A}
    Should Be Equal    ${r.json()['empresa']['telefono']}    +507 300-0000
    Should Be Equal    ${r.json()['empresa']['email']}    contacto@demo.com
    # El RUC y la direccion no salen al publico
    Should Not Contain    ${r.text}    155-123-45678
    Should Not Contain    ${r.text}    Calle 50
    ${vacio}=    Create Dictionary    telefono=${EMPTY}    email_contacto=${EMPTY}
    POST On Session    jefe    /organizacion/datos    json=${vacio}
    ${r}=    GET On Session    publico    /consulta/${CODIGO_A}
    Should Be Equal    ${r.json()['empresa']['telefono']}    ${None}

03 - Politica: valores validos, aviso para todo el equipo y dos pasos solo con los propios activos
    Iniciar Sesion Como Jefe    jefe
    ${mal}=    Create Dictionary    sesion_minutos=${45}
    ${r}=    POST On Session    jefe    /organizacion/politica    json=${mal}    expected_status=any
    Status Should Be    400    ${r}
    ${mal}=    Create Dictionary    aviso_defecto=${10}
    ${r}=    POST On Session    jefe    /organizacion/politica    json=${mal}    expected_status=any
    Status Should Be    400    ${r}
    ${exigir}=    Create Dictionary    exigir_2fa=${True}
    ${r}=    POST On Session    jefe    /organizacion/politica    json=${exigir}    expected_status=any
    Status Should Be    409    ${r}
    ${ok}=    Create Dictionary    sesion_minutos=${60}    aviso_defecto=${15}    aplicar_aviso=${True}
    ${r}=    POST On Session    jefe    /organizacion/politica    json=${ok}
    Should Be True    ${r.json()['aplicados']} >= 2
    ${r}=    GET On Session    jefe    /organizacion/politica
    Should Be Equal As Integers    ${r.json()['sesion_minutos']}    60
    Iniciar Sesion Como Consultor    consultor
    ${r}=    GET On Session    consultor    /perfil
    Should Be Equal As Integers    ${r.json()['aviso_vencimiento_dias']}    15
    # se devuelve a lo de siempre
    ${limpio}=    Create Dictionary    sesion_minutos=${None}    aviso_defecto=${30}    aplicar_aviso=${True}
    POST On Session    jefe    /organizacion/politica    json=${limpio}

04 - Si la empresa exige dos pasos, quien no los tiene solo puede activarlos
    ${s}=    Sufijo Unico
    Crear Empresa Con Jefe    ${s}
    Iniciar Sesion    pjefe    jefe.pol.${s}@ejemplo.com    ${CLAVE}
    Activar Dos Pasos    pjefe
    ${exigir}=    Create Dictionary    exigir_2fa=${True}
    ${r}=    POST On Session    pjefe    /organizacion/politica    json=${exigir}
    Status Should Be    200    ${r}
    ${token}=    Invitar Como    pjefe    cons.pol.${s}@ejemplo.com
    Registrar Con Invitacion    cons.pol.${s}@ejemplo.com    ${token}
    Create Session    anonimo    ${BASE_URL}
    ${login}=    Create Dictionary    email=cons.pol.${s}@ejemplo.com    password=${CLAVE}
    ${r}=    POST On Session    anonimo    /login    json=${login}
    Should Be True    ${r.json()['debe_activar_2fa']}
    Iniciar Sesion    pcons    cons.pol.${s}@ejemplo.com    ${CLAVE}
    ${r}=    GET On Session    pcons    /expedientes    expected_status=any
    Status Should Be    403    ${r}
    Should Be True    ${r.json()['activar_2fa_obligatorio']}
    ${r}=    GET On Session    pcons    /cuenta/seguridad
    Status Should Be    200    ${r}
    Activar Dos Pasos    pcons
    ${r}=    GET On Session    pcons    /expedientes
    Status Should Be    200    ${r}

05 - El director cierra las sesiones de todo el equipo menos la suya
    ${s}=    Sufijo Unico
    Crear Empresa Con Jefe    ${s}
    Iniciar Sesion    sjefe    jefe.pol.${s}@ejemplo.com    ${CLAVE}
    ${token}=    Invitar Como    sjefe    cons.pol.${s}@ejemplo.com
    Registrar Con Invitacion    cons.pol.${s}@ejemplo.com    ${token}
    Iniciar Sesion    scons    cons.pol.${s}@ejemplo.com    ${CLAVE}
    ${mala}=    Create Dictionary    password=incorrecta
    ${r}=    POST On Session    sjefe    /organizacion/cerrar-sesiones    json=${mala}    expected_status=any
    Status Should Be    400    ${r}
    ${buena}=    Create Dictionary    password=${CLAVE}
    ${r}=    POST On Session    sjefe    /organizacion/cerrar-sesiones    json=${buena}
    Should Be Equal As Integers    ${r.json()['cuentas']}    1
    ${r}=    GET On Session    scons    /sesion    expected_status=any
    Status Should Be    401    ${r}
    ${r}=    GET On Session    sjefe    /sesion
    Status Should Be    200    ${r}

06 - Uso de la cuenta y seguridad del equipo
    Iniciar Sesion Como Jefe    jefe
    ${r}=    GET On Session    jefe    /organizacion/uso
    Should Be True    ${r.json()['personas']['jefe']['total']} >= 1
    Should Be True    ${r.json()['expedientes']['total']} >= 1
    Dictionary Should Contain Key    ${r.json()['documentos']}    bytes
    ${r}=    GET On Session    jefe    /organizacion/equipo
    ${correos}=    Evaluate    [p['email'] for p in $r.json()['equipo']]
    Should Contain    ${correos}    consultor1@ejemplo.com
    Should Not Contain    ${correos}    consultor3@ejemplo.com
    Iniciar Sesion Como Consultor    consultor
    ${r}=    GET On Session    consultor    /organizacion/uso    expected_status=any
    Status Should Be    403    ${r}

07 - Exportar todo trae solo los datos de la empresa y se limita a una cada dos minutos
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe2    /organizacion/exportar
    ${dentro}=    Nombres En Zip    ${r.content}
    Should Contain    ${dentro}    cartera.xlsx
    Should Contain    ${dentro}    historial.csv
    Should Contain    ${dentro}    indice_documentos.csv
    Should Contain    ${dentro}    LEEME.txt
    ${texto}=    Texto Del Zip    ${r.content}    cartera.xlsx
    Should Contain    ${texto}    ${CODIGO_B}
    Should Not Contain    ${texto}    ${CODIGO_A}
    ${r}=    GET On Session    jefe2    /organizacion/exportar    expected_status=any
    Status Should Be    429    ${r}
    Iniciar Sesion Como Consultor De La Otra Empresa    consultor3
    ${r}=    GET On Session    consultor3    /organizacion/exportar    expected_status=any
    Status Should Be    403    ${r}

08 - El registro de accesos recuerda cambios y entradas, y no cruza empresas
    Iniciar Sesion Como Jefe    jefe
    ${datos}=    Create Dictionary    pie_documento=Pie de auditoria
    POST On Session    jefe    /organizacion/datos    json=${datos}
    ${r}=    GET On Session    jefe    /organizacion/auditoria
    ${tipos}=    Evaluate    {e['tipo'] for e in $r.json()['eventos']}
    Should Contain    ${tipos}    datos
    Should Contain    ${tipos}    acceso
    ${r}=    GET On Session    jefe    url=/organizacion/auditoria?tipo=datos
    ${tipos}=    Evaluate    {e['tipo'] for e in $r.json()['eventos']}
    Should Be Equal    ${tipos}    ${{ {'datos'} }}
    ${r}=    GET On Session    jefe    url=/organizacion/auditoria?tipo=inventado    expected_status=any
    Status Should Be    400    ${r}
    ${r}=    GET On Session    jefe    /organizacion/auditoria.csv
    Should Contain    ${r.headers['Content-Type']}    text/csv
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe2    /organizacion/auditoria
    ${quienes}=    Evaluate    {e['quien'] for e in $r.json()['eventos']}
    Should Not Contain    ${quienes}    Mariela Quintero
    Iniciar Sesion Como Consultor    consultor
    ${r}=    GET On Session    consultor    /organizacion/auditoria    expected_status=any
    Status Should Be    403    ${r}
    ${limpio}=    Create Dictionary    pie_documento=${EMPTY}
    POST On Session    jefe    /organizacion/datos    json=${limpio}

09 - Titularidad: el titular invita y asciende; transferirla le quita esos permisos
    ${s}=    Sufijo Unico
    Crear Empresa Con Jefe    ${s}
    Iniciar Sesion    tjefe    jefe.pol.${s}@ejemplo.com    ${CLAVE}
    ${r}=    GET On Session    tjefe    /organizacion/directores
    Should Be True    ${r.json()['soy_titular']}
    # un segundo director entra por invitacion del titular
    ${invitar}=    Create Dictionary    rol=jefe    email=dir2.${s}@ejemplo.com
    ${r}=    POST On Session    tjefe    /invitaciones    json=${invitar}
    Registrar Con Invitacion    dir2.${s}@ejemplo.com    ${r.json()['token']}
    Iniciar Sesion    tdir2    dir2.${s}@ejemplo.com    ${CLAVE}
    ${r}=    GET On Session    tdir2    /sesion
    Should Be Equal    ${r.json()['rol']}    jefe
    ${r}=    GET On Session    tdir2    /organizacion/directores
    Should Not Be True    ${r.json()['soy_titular']}
    # el segundo director NO puede invitar a otro director ni cambiar roles
    ${r}=    POST On Session    tdir2    /invitaciones    json=${invitar}    expected_status=any
    Status Should Be    403    ${r}
    ${token}=    Invitar Como    tjefe    cons.pol.${s}@ejemplo.com
    Registrar Con Invitacion    cons.pol.${s}@ejemplo.com    ${token}
    ${id}=    Id De Persona    tjefe    cons.pol.${s}@ejemplo.com
    ${rol}=    Create Dictionary    rol=jefe
    ${r}=    POST On Session    tdir2    /organizacion/directores/${id}/rol    json=${rol}    expected_status=any
    Status Should Be    403    ${r}
    # el titular asciende al consultor, y no puede degradarse a si mismo
    ${r}=    POST On Session    tjefe    /organizacion/directores/${id}/rol    json=${rol}
    Status Should Be    200    ${r}
    ${yo}=    Id De Persona    tjefe    jefe.pol.${s}@ejemplo.com
    ${baja}=    Create Dictionary    rol=consultor
    ${r}=    POST On Session    tjefe    /organizacion/directores/${yo}/rol    json=${baja}    expected_status=any
    Status Should Be    409    ${r}
    # transferencia: pide la contrasena y despues el antiguo titular ya no puede
    ${nuevo}=    Id De Persona    tjefe    dir2.${s}@ejemplo.com
    ${mala}=    Create Dictionary    usuario_id=${nuevo}    password=incorrecta
    ${r}=    POST On Session    tjefe    /organizacion/titular    json=${mala}    expected_status=any
    Status Should Be    400    ${r}
    ${buena}=    Create Dictionary    usuario_id=${nuevo}    password=${CLAVE}
    ${r}=    POST On Session    tjefe    /organizacion/titular    json=${buena}
    Status Should Be    200    ${r}
    ${r}=    POST On Session    tjefe    /invitaciones    json=${invitar}    expected_status=any
    Status Should Be    403    ${r}
    ${r}=    GET On Session    tdir2    /organizacion/directores
    Should Be True    ${r.json()['soy_titular']}

10 - El recorrido de bienvenida se ofrece una sola vez por cuenta
    ${s}=    Sufijo Unico
    Crear Empresa Con Jefe    ${s}
    # primera vez: pendiente
    Iniciar Sesion    primera    jefe.pol.${s}@ejemplo.com    ${CLAVE}
    ${r}=    GET On Session    primera    /sesion
    Should Be True    ${r.json()['tour_pendiente']}
    # se anota como visto (y repetirlo no cambia nada)
    ${r}=    POST On Session    primera    /cuenta/tour    json=${EMPTY}
    Status Should Be    200    ${r}
    POST On Session    primera    /cuenta/tour    json=${EMPTY}
    ${r}=    GET On Session    primera    /sesion
    Should Not Be True    ${r.json()['tour_pendiente']}
    # otra sesion nueva (otro equipo): ya no sale
    Iniciar Sesion    segunda    jefe.pol.${s}@ejemplo.com    ${CLAVE}
    ${r}=    GET On Session    segunda    /sesion
    Should Not Be True    ${r.json()['tour_pendiente']}
    # una cuenta distinta de la misma empresa si lo ve en su primera vez
    ${token}=    Invitar Como    primera    nueva.${s}@ejemplo.com
    Registrar Con Invitacion    nueva.${s}@ejemplo.com    ${token}
    Iniciar Sesion    nueva    nueva.${s}@ejemplo.com    ${CLAVE}
    ${r}=    GET On Session    nueva    /sesion
    Should Be True    ${r.json()['tour_pendiente']}
    # sin sesion no se puede marcar
    Create Session    anonimo    ${BASE_URL}
    ${r}=    POST On Session    anonimo    /cuenta/tour    json=${EMPTY}    expected_status=any
    Status Should Be    401    ${r}

*** Keywords ***
Crear Empresa Con Jefe
    [Arguments]    ${s}
    Iniciar Sesion Como Administrador    adminc
    ${datos}=    Create Dictionary    nombre=Consultora Politica ${s}    email_jefe=jefe.pol.${s}@ejemplo.com
    ${r}=    POST On Session    adminc    /plataforma/empresas    json=${datos}
    ${token}=    Evaluate    $r.json()['enlace'].split('invitacion=')[1]
    ${r}=    Registrar Con Invitacion    jefe.pol.${s}@ejemplo.com    ${token}
    Status Should Be    201    ${r}

Invitar Como
    [Arguments]    ${alias}    ${correo}
    ${datos}=    Create Dictionary    email=${correo}
    ${r}=    POST On Session    ${alias}    /invitaciones    json=${datos}
    RETURN    ${r.json()['token']}

Registrar Con Invitacion
    [Arguments]    ${correo}    ${token}
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    nombre=Persona Prueba    email=${correo}    password=${CLAVE}
    ...    invitacion=${token}    acepto_terminos=${True}
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=any
    RETURN    ${r}

Activar Dos Pasos
    [Arguments]    ${alias}
    ${confirma}=    Create Dictionary    password=${CLAVE}
    ${r}=    POST On Session    ${alias}    /cuenta/2fa/preparar    json=${confirma}
    ${codigo}=    Codigo Totp    ${r.json()['secreto']}
    ${bueno}=    Create Dictionary    codigo=${codigo}
    ${r}=    POST On Session    ${alias}    /cuenta/2fa/activar    json=${bueno}
    Status Should Be    200    ${r}

Id De Persona
    [Arguments]    ${alias}    ${correo}
    ${r}=    GET On Session    ${alias}    /organizacion/directores
    FOR    ${p}    IN    @{r.json()['directores']}    @{r.json()['candidatos']}
        IF    '${p['email']}' == '${correo}'
            RETURN    ${p['id']}
        END
    END
    ${r}=    GET On Session    ${alias}    /organizacion/equipo
    FOR    ${p}    IN    @{r.json()['equipo']}
        IF    '${p['email']}' == '${correo}'
            RETURN    ${p['id']}
        END
    END
    Fail    No se encontro a ${correo}
