*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 10 (Permisos Ambientales)
...               Lo que paso del Sprint 9 al Sprint 10:
...               - HU-08: al someter se guarda la fecha y desde ella corre el plazo de
...                 MiAmbiente en dias habiles; el panel avisa los plazos por vencer.
...               - HU-05: fecha de vencimiento real al subir un documento y aviso de 15,
...                 30 o 45 dias que elige cada usuario.
...               - HU-01: la cartografia es un ZIP con el shapefile (.shp, .shx, .dbf).
...               - Resolucion de MiAmbiente: aprobado o rechazado, con numero y fecha.
...               - Devolver con observaciones: el jefe regresa el expediente al consultor.
Library           RequestsLibrary
Library           Collections
Resource          ../recursos/sesion.resource
Library           archivos.py
Suite Teardown    Run Keyword And Ignore Error    Restaurar Aviso

*** Variables ***
${JEFE_EMAIL}            jefe1@ejemplo.com
${JEFE_PASSWORD}         Jefe2026*
${MOTIVO}                Revision interna Robot Sprint 10

*** Test Cases ***
# ---------------- HU-08: plazo desde el sometimiento ----------------

01 - HU-08 Antes De Someter El Plazo Se Mide Desde El Ingreso
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente Completo    I
    Set Suite Variable    ${COD_FLUJO}    ${codigo}
    ${r}=    GET On Session    consultor    /expedientes/${COD_FLUJO}/alertas    expected_status=200
    Should Be Equal    ${r.json()['base_plazo']}    ingreso
    Should Be Equal    ${r.json()['tipo_dias']}    calendario

02 - HU-08 Al Someter Corre El Plazo De MiAmbiente En Dias Habiles
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    motivo=${MOTIVO}
    POST On Session    jefe    /expedientes/${COD_FLUJO}/aprobar    json=${datos}    expected_status=200
    Iniciar Sesion Como Consultor
    ${r}=    POST On Session    consultor    /expedientes/${COD_FLUJO}/someter    expected_status=200
    ${hoy}=    Hoy En Panama
    Should Be Equal    ${r.json()['fecha_sometimiento']}    ${hoy}
    ${r}=    GET On Session    consultor    /expedientes/${COD_FLUJO}/alertas    expected_status=200
    ${s}=    Set Variable    ${r.json()}
    Should Be Equal    ${s['base_plazo']}    sometimiento
    Should Be Equal    ${s['tipo_dias']}    habiles
    Should Be Equal    ${s['fecha_inicio']}    ${hoy}
    Should Be Equal As Integers    ${s['dias_transcurridos']}    0
    Should Be Equal As Integers    ${s['dias_restantes_legales']}    20
    Should Be Equal    ${s['estado_semaforo']}    en_plazo
    ${r}=    GET On Session    consultor    /expedientes/${COD_FLUJO}    expected_status=200
    Should Not Be Empty    ${r.json()['expediente']['fecha_sometimiento']}

03 - HU-08 El Panel Trae Los Avisos De Plazo Tambien Para El Promotor
    Iniciar Sesion Como Promotor
    ${r}=    GET On Session    promotor    /dashboard    expected_status=200
    Dictionary Should Contain Key    ${r.json()}    avisos_plazo
    Should Be Empty    ${r.json()['prioridades']}
    FOR    ${a}    IN    @{r.json()['avisos_plazo']}
        Should Contain    ${{['por_vencer', 'vencido']}}    ${a['estado_semaforo']}
    END

# ---------------- Resolucion de MiAmbiente ----------------

04 - Resolucion Exige Resultado Numero Y Fecha Validos
    Iniciar Sesion Como Consultor
    ${malo}=    Create Dictionary    resultado=talvez    numero=DEIA-1    fecha=2026-01-01
    POST On Session    consultor    /expedientes/${COD_FLUJO}/resolucion    json=${malo}    expected_status=400
    ${sin_numero}=    Create Dictionary    resultado=aprobado    fecha=2026-01-01
    POST On Session    consultor    /expedientes/${COD_FLUJO}/resolucion    json=${sin_numero}    expected_status=400
    ${futura}=    Evaluate    (__import__('datetime').date.today() + __import__('datetime').timedelta(days=5)).isoformat()
    ${datos}=    Create Dictionary    resultado=aprobado    numero=DEIA-1    fecha=${futura}
    POST On Session    consultor    /expedientes/${COD_FLUJO}/resolucion    json=${datos}    expected_status=400

05 - Resolucion Solo La Registra El Consultor Duenio O El Jefe
    Iniciar Sesion    consultor2    consultor2@ejemplo.com    Clave2026
    ${hoy}=    Hoy En Panama
    ${datos}=    Create Dictionary    resultado=aprobado    numero=DEIA-1    fecha=${hoy}
    POST On Session    consultor2    /expedientes/${COD_FLUJO}/resolucion    json=${datos}    expected_status=403

06 - Resolucion Rechazada Queda Con Numero Fecha E Historial
    Iniciar Sesion Como Consultor
    ${hoy}=    Hoy En Panama
    ${datos}=    Create Dictionary    resultado=rechazado    numero=DEIA-IA-777-2026    fecha=${hoy}
    ${r}=    POST On Session    consultor    /expedientes/${COD_FLUJO}/resolucion    json=${datos}    expected_status=200
    Should Be Equal    ${r.json()['estado']}    rechazado
    ${r}=    GET On Session    consultor    /expedientes/${COD_FLUJO}    expected_status=200
    Should Be Equal    ${r.json()['expediente']['estado']}    rechazado
    Should Be Equal    ${r.json()['resolucion']['resultado']}    rechazado
    Should Be Equal    ${r.json()['resolucion']['numero']}    DEIA-IA-777-2026
    ${entradas}=    Historial De    consultor    ${COD_FLUJO}
    Should Be Equal    ${entradas[0]['accion']}    registró rechazo de MiAmbiente
    ${r}=    GET On Session    consultor    /expedientes/${COD_FLUJO}/alertas    expected_status=200
    Should Be Equal    ${r.json()['estado_semaforo']}    resuelto
    POST On Session    consultor    /expedientes/${COD_FLUJO}/resolucion    json=${datos}    expected_status=400

# ---------------- Devolver con observaciones ----------------

07 - Devolver Solo Lo Hace El Jefe
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente Completo    I
    Set Suite Variable    ${COD_DEVOLVER}    ${codigo}
    ${datos}=    Create Dictionary    observaciones=Falta la firma del promotor
    POST On Session    consultor    /expedientes/${COD_DEVOLVER}/devolver    json=${datos}    expected_status=403

08 - El Jefe Devuelve Un Expediente Aprobado Internamente
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    motivo=${MOTIVO}
    POST On Session    jefe    /expedientes/${COD_DEVOLVER}/aprobar    json=${datos}    expected_status=200
    ${vacio}=    Create Dictionary    observaciones=${SPACE}
    POST On Session    jefe    /expedientes/${COD_DEVOLVER}/devolver    json=${vacio}    expected_status=400
    ${obs}=    Create Dictionary    observaciones=Falta la firma del promotor en los Anexos Legales
    ${r}=    POST On Session    jefe    /expedientes/${COD_DEVOLVER}/devolver    json=${obs}    expected_status=200
    Should Be Equal    ${r.json()['estado']}    pendiente
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${COD_DEVOLVER}    expected_status=200
    Should Be Equal    ${r.json()['expediente']['estado']}    pendiente
    Should Be Equal    ${r.json()['observaciones'][0]['texto']}    Falta la firma del promotor en los Anexos Legales
    ${entradas}=    Historial De    consultor    ${COD_DEVOLVER}
    Should Be Equal    ${entradas[0]['accion']}    devolvió con observaciones

09 - Lo Ya Sometido No Se Devuelve
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    motivo=${MOTIVO}
    POST On Session    jefe    /expedientes/${COD_DEVOLVER}/aprobar    json=${datos}    expected_status=200
    POST On Session    jefe    /expedientes/${COD_DEVOLVER}/someter    expected_status=200
    ${obs}=    Create Dictionary    observaciones=Ya no aplica
    POST On Session    jefe    /expedientes/${COD_DEVOLVER}/devolver    json=${obs}    expected_status=400

# ---------------- HU-05: vencimiento real y aviso configurable ----------------

10 - HU-05 La Fecha De Vencimiento Debe Ser Futura
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente    consultor    I
    Set Suite Variable    ${COD_VENCE}    ${codigo}
    ${archivos}=    PDF De Prueba
    ${pasada}=    Create Dictionary    fecha_vencimiento=2020-01-01
    ${r}=    POST On Session    consultor    /expedientes/${COD_VENCE}/documentos/Anexos%20Legales/subir
    ...    files=${archivos}    data=${pasada}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    posterior a hoy

11 - HU-05 El Documento Guarda Su Vencimiento Real
    Iniciar Sesion Como Consultor
    ${vence}=    Evaluate    (__import__('datetime').date.today() + __import__('datetime').timedelta(days=40)).isoformat()
    ${archivos}=    PDF De Prueba
    ${datos}=    Create Dictionary    fecha_vencimiento=${vence}
    ${r}=    POST On Session    consultor    /expedientes/${COD_VENCE}/documentos/Anexos%20Legales/subir
    ...    files=${archivos}    data=${datos}    expected_status=200
    Should Be Equal    ${r.json()['fecha_vencimiento']}    ${vence}
    ${r}=    GET On Session    consultor    /expedientes/${COD_VENCE}    expected_status=200
    ${doc}=    Evaluate    [d for d in $r.json()['documentos'] if d['carpeta'] == 'Anexos Legales'][0]
    Should Be True    ${doc['vencimiento_real']}
    Should Be True    38 <= ${doc['dias_para_vencer']} <= 41

12 - HU-05 El Aviso Es De 15, 30 O 45 Dias
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /perfil    expected_status=200
    Should Be Equal As Integers    ${r.json()['aviso_vencimiento_dias']}    30
    ${malo}=    Create Dictionary    aviso_vencimiento_dias=${10}
    POST On Session    consultor    /perfil    json=${malo}    expected_status=400
    ${r}=    GET On Session    consultor    /dashboard    expected_status=200
    ${codigos}=    Evaluate    [a['codigo'] for a in $r.json()['alertas']]
    Should Not Contain    ${codigos}    ${COD_VENCE}

13 - HU-05 Con 45 Dias El Panel Avisa El Documento Que Vence En 40
    Iniciar Sesion Como Consultor
    ${datos}=    Create Dictionary    aviso_vencimiento_dias=${45}
    POST On Session    consultor    /perfil    json=${datos}    expected_status=200
    ${r}=    GET On Session    consultor    /dashboard    expected_status=200
    Should Be Equal As Integers    ${r.json()['aviso_vencimiento_dias']}    45
    ${alertas}=    Evaluate    [a for a in $r.json()['alertas'] if a['codigo'] == '${COD_VENCE}']
    Length Should Be    ${alertas}    1
    Should Be True    ${alertas[0]['vencimiento_real']}

# ---------------- HU-01: cartografia con shapefile ----------------

14 - HU-01 La Cartografia No Acepta Un PDF
    Iniciar Sesion Como Consultor
    ${codigo}=    Crear Expediente    consultor    II
    Set Suite Variable    ${COD_CARTO}    ${codigo}
    ${archivos}=    PDF De Prueba
    ${r}=    POST On Session    consultor    /expedientes/${COD_CARTO}/documentos/Cartograf%C3%ADa/subir
    ...    files=${archivos}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    shapefile

15 - HU-01 Un Shapefile Incompleto Se Rechaza
    Iniciar Sesion Como Consultor
    ${archivos}=    ZIP Con    area.shp    area.dbf
    ${r}=    POST On Session    consultor    /expedientes/${COD_CARTO}/documentos/Cartograf%C3%ADa/subir
    ...    files=${archivos}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    .shx

16 - HU-01 Un Shapefile Completo Se Acepta
    Iniciar Sesion Como Consultor
    ${archivos}=    ZIP Con    mapa/area.shp    mapa/area.shx    mapa/area.dbf    mapa/area.prj
    POST On Session    consultor    /expedientes/${COD_CARTO}/documentos/Cartograf%C3%ADa/subir
    ...    files=${archivos}    expected_status=200

# ---------------- Innovacion: calendario de plazos (.ics) ----------------

17 - Calendario Descarga El Limite Legal Y Los Vencimientos
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${COD_VENCE}/plazos.ics    expected_status=200
    Should Start With    ${r.headers['Content-Type']}    text/calendar
    Should Contain    ${r.headers['Content-Disposition']}    ${COD_VENCE}_plazos.ics
    ${texto}=    Evaluate    $r.content.decode('utf-8').replace('\\r\\n ', '')
    Should Start With    ${texto}    BEGIN:VCALENDAR
    Should Contain    ${texto}    UID:${COD_VENCE}-plazo@permisos-ambientales
    Should Contain    ${texto}    UID:${COD_VENCE}-doc-anexos-legales@permisos-ambientales
    Should Contain    ${texto}    BEGIN:VALARM

18 - Calendario Solo Con Permiso Sobre El Expediente
    Iniciar Sesion Como Promotor
    GET On Session    promotor    /expedientes/${COD_VENCE}/plazos.ics    expected_status=403
    Create Session    anonimo    ${BASE_URL}
    GET On Session    anonimo    /expedientes/${COD_VENCE}/plazos.ics    expected_status=401

19 - Calendario De Un Expediente Resuelto No Trae El Limite Legal
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${COD_FLUJO}/plazos.ics    expected_status=200
    Should Not Contain    ${r.text}    ${COD_FLUJO}-plazo@

*** Keywords ***
Iniciar Sesion Como Jefe
    [Arguments]    ${alias}=jefe
    Iniciar Sesion    ${alias}    ${JEFE_EMAIL}    ${JEFE_PASSWORD}

Hoy En Panama
    ${hoy}=    Evaluate
    ...    datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()
    ...    modules=datetime
    RETURN    ${hoy}

Crear Expediente
    [Arguments]    ${alias}    ${categoria}
    ${datos}=    Create Dictionary    proyecto=Expediente Robot Sprint 10    promotor=Promotor Robot S10
    ...    categoria=${categoria}
    ${r}=    POST On Session    ${alias}    /expedientes    json=${datos}    expected_status=201
    RETURN    ${r.json()['codigo']}

Crear Expediente Completo
    [Documentation]    Expediente del consultor con todos sus documentos (categoria I: tres PDF).
    [Arguments]    ${categoria}
    ${codigo}=    Crear Expediente    consultor    ${categoria}
    ${r}=    GET On Session    consultor    /expedientes/${codigo}
    @{carpetas}=    Evaluate    [d['carpeta'] for d in $r.json()['documentos']]
    FOR    ${carpeta}    IN    @{carpetas}
        ${carpeta_url}=    Evaluate    urllib.parse.quote($carpeta)    modules=urllib.parse
        ${archivos}=    PDF De Prueba
        POST On Session    consultor    /expedientes/${codigo}/documentos/${carpeta_url}/subir
        ...    files=${archivos}    expected_status=200
    END
    RETURN    ${codigo}

PDF De Prueba
    ${archivos}=    Evaluate    {'archivo': ('robot_s10.pdf', b'%PDF-1.4\\n% prueba Robot Sprint 10\\n', 'application/pdf')}
    RETURN    ${archivos}

ZIP Con
    [Arguments]    @{nombres}
    ${archivos}=    Zip Con Nombres    @{nombres}
    RETURN    ${archivos}

Historial De
    [Arguments]    ${alias}    ${codigo}
    ${r}=    GET On Session    ${alias}    /expedientes/${codigo}/historial
    RETURN    ${r.json()['historial']}

Restaurar Aviso
    Iniciar Sesion Como Consultor
    ${datos}=    Create Dictionary    aviso_vencimiento_dias=${30}
    POST On Session    consultor    /perfil    json=${datos}    expected_status=200
