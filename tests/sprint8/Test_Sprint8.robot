*** Settings ***
Documentation     Suite de Pruebas Automatizadas - Sprint 8 (Permisos Ambientales)
...               HU-13: rol de jefe. Un caso de 403 por cada "No" de la matriz de permisos.
...               HU-14: historial del expediente (usuario, fecha y solo lectura).
...
...               Matriz usada (README, seccion "Rol de jefe e historial"):
...               | Endpoint                              | Jefe | Consultor          | Promotor | Sin sesion |
...               | GET /historial y /historial?codigo=X  | todo | solo los suyos     | 403      | 401        |
...               | GET /expedientes/<codigo>/historial   | 200  | 200 si es suyo, 403| 403      | 401        |
...               | POST /expedientes/<codigo>/aprobar    | 200  | 403                | 403      | 401        |
Library           RequestsLibrary
Library           Collections
Library           String
Resource          ../recursos/sesion.resource

*** Variables ***
${JEFE_EMAIL}            jefe1@ejemplo.com
${JEFE_PASSWORD}         Jefe2026*
${CONSULTOR2_EMAIL}      consultor2@ejemplo.com
${CONSULTOR2_PASSWORD}   Clave2026
# 001 es de consultor1 y su promotor es promotor1.
${EXP_C1}                SP-A8-2026-001
${MOTIVO}                Revision interna Robot Sprint 8
# Margen entre la hora del historial y la hora de Panama al correr la prueba.
${MARGEN_SEGUNDOS}       120

*** Test Cases ***
# ---------------- HU-13: matriz de permisos (cada "No" = 403) ----------------

01 - Un Consultor No Aprueba Internamente Ni Su Propio Expediente
    [Documentation]    Matriz: aprobar / Consultor = No. 001 es de consultor1.
    Iniciar Sesion Como Consultor
    ${r}=    Aprobar    consultor    ${EXP_C1}    expected_status=403
    Should Contain    ${r.json()['mensaje']}    director de proyectos

02 - Un Consultor No Aprueba Un Expediente Ajeno
    [Documentation]    Matriz: aprobar / Consultor = No (consultor2 sobre el 001 de consultor1).
    Iniciar Sesion Como Consultor 2
    Aprobar    consultor2    ${EXP_C1}    expected_status=403

03 - Un Promotor No Aprueba Ni Su Propio Expediente
    [Documentation]    Matriz: aprobar / Promotor = No. promotor1 es el promotor del 001.
    Iniciar Sesion Como Promotor
    Aprobar    promotor    ${EXP_C1}    expected_status=403

04 - Un Promotor No Ve El Historial General
    [Documentation]    Matriz: GET /historial / Promotor = No.
    Iniciar Sesion Como Promotor
    GET On Session    promotor    /historial    expected_status=403

05 - Un Promotor No Ve El Historial Filtrado Por Codigo
    [Documentation]    Matriz: GET /historial?codigo=X / Promotor = No (aunque sea su expediente).
    Iniciar Sesion Como Promotor
    GET On Session    promotor    url=/historial?codigo=${EXP_C1}    expected_status=403

06 - Un Promotor No Ve El Historial De Su Expediente
    [Documentation]    Matriz: GET /expedientes/<codigo>/historial / Promotor = No.
    Iniciar Sesion Como Promotor
    GET On Session    promotor    /expedientes/${EXP_C1}/historial    expected_status=403

07 - Un Consultor No Ve El Historial De Un Expediente Ajeno
    [Documentation]    Matriz: GET /expedientes/<codigo>/historial / Consultor ajeno = No.
    Iniciar Sesion Como Consultor 2
    GET On Session    consultor2    /expedientes/${EXP_C1}/historial    expected_status=403

08 - Un Consultor No Filtra El Historial Por Un Expediente Ajeno
    [Documentation]    Matriz: GET /historial?codigo=X / Consultor = solo los suyos.
    Iniciar Sesion Como Consultor 2
    GET On Session    consultor2    url=/historial?codigo=${EXP_C1}    expected_status=403

09 - Un Consultor No Ve El Detalle De Un Expediente Ajeno
    [Documentation]    Con dos consultores, cada uno ve solo lo suyo (el jefe ve todo).
    Iniciar Sesion Como Consultor 2
    GET On Session    consultor2    /expedientes/${EXP_C1}    expected_status=403

10 - Sin Sesion Todo Da 401
    [Documentation]    Matriz: columna "Sin sesion".
    Create Session    anonimo    ${BASE_URL}
    GET On Session    anonimo    /historial    expected_status=401
    GET On Session    anonimo    /expedientes/${EXP_C1}/historial    expected_status=401
    ${datos}=    Create Dictionary    motivo=${MOTIVO}
    POST On Session    anonimo    /expedientes/${EXP_C1}/aprobar    json=${datos}    expected_status=401

11 - Nadie Se Registra Como Jefe
    [Documentation]    El jefe no se puede crear desde /registro.
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    nombre=Jefe Falso    email=jefe_falso_robot@ejemplo.com
    ...    password=Clave12345    rol=jefe
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=400
    Should Contain    ${r.json()['mensaje']}    Rol no permitido

# ---------------- HU-13: lo que si puede el jefe ----------------

12 - El Jefe Existe Y Tiene Rol Jefe
    [Documentation]    La app crea el usuario jefe al arrancar si no existe.
    Iniciar Sesion Como Jefe
    ${r}=    GET On Session    jefe    /sesion
    Should Be Equal    ${r.json()['rol']}    jefe

13 - El Jefe Ve Los Expedientes De Todos Los Consultores
    [Documentation]    Una sola consultora: el jefe ve lo de consultor1 y consultor2, con consultor y plazo.
    Iniciar Sesion Como Jefe
    Iniciar Sesion Como Consultor
    Iniciar Sesion Como Consultor 2
    ${total_jefe}=    Total De Expedientes    jefe
    ${total_c1}=    Total De Expedientes    consultor
    ${total_c2}=    Total De Expedientes    consultor2
    Should Be True    ${total_jefe} >= ${total_c1} + ${total_c2}
    ${r}=    GET On Session    jefe    url=/expedientes?q=${EXP_C1}
    ${exp}=    Set Variable    ${r.json()['expedientes'][0]}
    Should Be Equal    ${exp['codigo']}    ${EXP_C1}
    Dictionary Should Contain Key    ${exp}    consultor
    Dictionary Should Contain Key    ${exp}    plazo

14 - Un Consultor No Ve Expedientes Ajenos En Su Lista
    Iniciar Sesion Como Consultor 2
    ${r}=    GET On Session    consultor2    url=/expedientes?q=${EXP_C1}
    Should Be Equal As Integers    ${r.json()['paginacion']['total']}    0

# ---------------- HU-14: historial ----------------

15 - HU-14 Crear Un Expediente Queda En El Historial Con Usuario Y Fecha
    Iniciar Sesion Como Consultor
    ${datos}=    Create Dictionary    proyecto=Expediente Robot HU-14    promotor=Promotor Robot    categoria=I
    ${r}=    POST On Session    consultor    /expedientes    json=${datos}    expected_status=201
    ${codigo}=    Set Variable    ${r.json()['codigo']}
    Set Suite Variable    ${CODIGO}    ${codigo}
    ${entradas}=    Historial De    consultor    ${CODIGO}
    Length Should Be    ${entradas}    1
    Entrada Debe Ser    ${entradas[0]}    creó    ${CONSULTOR_EMAIL}    consultor

16 - HU-14 Subir Documentos Queda En El Historial
    [Documentation]    Categoria I = 3 carpetas; cada subida es una entrada.
    Iniciar Sesion Como Consultor
    ${r}=    GET On Session    consultor    /expedientes/${CODIGO}
    FOR    ${doc}    IN    @{r.json()['documentos']}
        Subir PDF    consultor    ${CODIGO}    ${doc['carpeta']}
    END
    ${entradas}=    Historial De    consultor    ${CODIGO}
    Length Should Be    ${entradas}    4
    FOR    ${i}    IN RANGE    3
        Entrada Debe Ser    ${entradas[${i}]}    subió documento    ${CONSULTOR_EMAIL}    consultor
    END

17 - HU-14 Una Aprobacion Rechazada No Deja Rastro
    [Documentation]    El consultor intenta aprobar (403): no debe aparecer un "aprobó" a su nombre.
    Iniciar Sesion Como Consultor
    Aprobar    consultor    ${CODIGO}    expected_status=403
    ${entradas}=    Historial De    consultor    ${CODIGO}
    Length Should Be    ${entradas}    4

18 - HU-14 La Aprobacion Del Jefe Queda A Nombre Del Jefe
    Iniciar Sesion Como Jefe
    Aprobar    jefe    ${CODIGO}    expected_status=200
    ${entradas}=    Historial De    jefe    ${CODIGO}
    Length Should Be    ${entradas}    5
    Entrada Debe Ser    ${entradas[0]}    aprobó    ${JEFE_EMAIL}    jefe
    # HU-10 sigue igual: la aprobacion tambien queda en la tabla aprobaciones.
    ${r}=    GET On Session    jefe    /expedientes/${CODIGO}/aprobaciones
    Should Be Equal    ${r.json()['estado']}    aprobado_interno
    Length Should Be    ${r.json()['aprobaciones']}    1

19 - HU-14 Cada Rol Ve Solo Lo Que Le Toca En El Historial General
    [Documentation]    Jefe: todo. Consultor: solo sus expedientes.
    Iniciar Sesion Como Jefe
    Iniciar Sesion Como Consultor 2
    ${r}=    GET On Session    jefe    url=/historial?per_page=200
    ${codigos_jefe}=    Codigos Del Historial    ${r.json()['historial']}
    List Should Contain Value    ${codigos_jefe}    ${CODIGO}
    ${r}=    GET On Session    consultor2    url=/historial?per_page=200
    ${codigos_c2}=    Codigos Del Historial    ${r.json()['historial']}
    List Should Not Contain Value    ${codigos_c2}    ${CODIGO}

20 - HU-14 El Historial No Se Puede Modificar Ni Borrar
    [Documentation]    Ni el jefe: POST, PUT, PATCH y DELETE responden 405 y el historial no cambia.
    Iniciar Sesion Como Jefe
    ${antes}=    Historial De    jefe    ${CODIGO}
    ${id}=    Set Variable    ${antes[0]['id']}
    ${datos}=    Create Dictionary    accion=borrado    usuario_id=1    fecha=2000-01-01 00:00:00
    FOR    ${ruta}    IN    /historial    /historial/${id}
    ...    /expedientes/${CODIGO}/historial    /expedientes/${CODIGO}/historial/${id}
        POST On Session      jefe    ${ruta}    json=${datos}    expected_status=405
        PUT On Session       jefe    ${ruta}    json=${datos}    expected_status=405
        PATCH On Session     jefe    ${ruta}    json=${datos}    expected_status=405
        DELETE On Session    jefe    ${ruta}    expected_status=405
    END
    ${despues}=    Historial De    jefe    ${CODIGO}
    Should Be Equal    ${antes}    ${despues}

*** Keywords ***
Iniciar Sesion Como Jefe
    [Arguments]    ${alias}=jefe
    Iniciar Sesion    ${alias}    ${JEFE_EMAIL}    ${JEFE_PASSWORD}

Iniciar Sesion Como Consultor 2
    [Arguments]    ${alias}=consultor2
    Iniciar Sesion    ${alias}    ${CONSULTOR2_EMAIL}    ${CONSULTOR2_PASSWORD}

Aprobar
    [Documentation]    Siempre con motivo: sin motivo la API responde 400 antes de revisar el rol.
    [Arguments]    ${alias}    ${codigo}    ${expected_status}
    ${datos}=    Create Dictionary    motivo=${MOTIVO}
    ${r}=    POST On Session    ${alias}    /expedientes/${codigo}/aprobar    json=${datos}
    ...    expected_status=${expected_status}
    RETURN    ${r}

Total De Expedientes
    [Arguments]    ${alias}
    ${r}=    GET On Session    ${alias}    /expedientes
    RETURN    ${r.json()['paginacion']['total']}

Historial De
    [Documentation]    Entradas del expediente, de la mas reciente a la mas antigua.
    [Arguments]    ${alias}    ${codigo}
    ${r}=    GET On Session    ${alias}    /expedientes/${codigo}/historial
    RETURN    ${r.json()['historial']}

Codigos Del Historial
    [Arguments]    ${entradas}
    ${codigos}=    Evaluate    [e['codigo'] for e in $entradas]
    RETURN    ${codigos}

Subir PDF
    [Arguments]    ${alias}    ${codigo}    ${carpeta}
    ${carpeta_url}=    Evaluate    urllib.parse.quote($carpeta)    modules=urllib.parse
    ${archivos}=    Evaluate    {'archivo': ('robot_hu14.pdf', b'%PDF-1.4\\n% prueba Robot HU-14\\n', 'application/pdf')}
    POST On Session    ${alias}    /expedientes/${codigo}/documentos/${carpeta_url}/subir
    ...    files=${archivos}    expected_status=200

Hora De Panama
    [Documentation]    Panama es UTC-5 todo el anio (sin horario de verano).
    ${ahora}=    Evaluate    datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).replace(tzinfo=None)
    ...    modules=datetime
    RETURN    ${ahora}

Entrada Debe Ser
    [Documentation]    Revisa accion, usuario de la sesion y que la fecha sea la hora de Panama de ahora.
    [Arguments]    ${entrada}    ${accion}    ${email}    ${rol}
    Should Be Equal    ${entrada['accion']}    ${accion}
    Should Be Equal    ${entrada['usuario_email']}    ${email}
    Should Be Equal    ${entrada['usuario_rol']}    ${rol}
    ${fecha}=    Evaluate    datetime.datetime.strptime($entrada['fecha'], '%Y-%m-%d %H:%M:%S')    modules=datetime
    ${ahora}=    Hora De Panama
    ${diferencia}=    Evaluate    abs(($ahora - $fecha).total_seconds())
    Should Be True    ${diferencia} <= ${MARGEN_SEGUNDOS}
    ...    La fecha ${entrada['fecha']} no es la hora de Panama de ahora (${ahora}); diferencia ${diferencia} s
