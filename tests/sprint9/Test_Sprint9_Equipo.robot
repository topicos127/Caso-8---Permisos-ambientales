*** Settings ***
Documentation     Sprint 9 - Calidad y seguridad (Louis): HU-16 equipo de consultores y HU-12 celular.
...               Complementa los casos 20 a 26 de tests/sprint9/Test_Sprint9.robot (Helio), que
...               cubren el ciclo feliz: alta, cambio de clave, baja, sesion cerrada, reasignacion y
...               reactivacion. Aqui van la matriz de permisos completa, las validaciones, lo que
...               queda despues de la baja y la reasignacion, y lo que se puede revisar del celular
...               sin un navegador (lo visual va en CASOS_MANUALES_HU12.md).
...               Codigo probado: rama sprint-9-dev (commits de Ismael 04df472 y 6f670ba).
...               Los casos con la etiqueta "hallazgo" describen el comportamiento esperado y hoy
...               fallan. Llevan tambien la etiqueta reservada robot:skip-on-failure: si fallan
...               quedan en SKIP (con el motivo en el reporte) y no ponen el CI en rojo; el dia
...               que se corrija, pasan solos.
Library           RequestsLibrary
Library           Collections
Resource          ../recursos/sesion.resource
Suite Setup       Preparar Suite

*** Variables ***
${JEFE_EMAIL}            jefe1@ejemplo.com
${JEFE_PASSWORD}         Jefe2026*
${CONSULTOR2_EMAIL}      consultor2@ejemplo.com
${CONSULTOR2_PASSWORD}   Clave2026
${CLAVE_INICIAL}         Inicial2026x
${CLAVE_PROPIA}          Equipo2026x
${ID_INEXISTENTE}        999999

*** Test Cases ***
# ---------------- HU-16: permisos (matriz completa) ----------------

01 - HU-16 Consultor Y Promotor Reciben 403 En Todas Las Acciones Del Equipo
    [Documentation]    El caso 20 de Helio solo prueba GET /consultores. Aqui, las cuatro escrituras.
    [Tags]    HU-16    seguridad
    ${alta}=    Create Dictionary    nombre=Intruso    email=intruso_${SUFIJO}@ejemplo.com
    ${reasig}=    Create Dictionary    destino_id=${C2_ID}
    Iniciar Sesion Como Consultor
    Iniciar Sesion Como Promotor
    FOR    ${alias}    IN    consultor    promotor
        POST On Session    ${alias}    /consultores    json=${alta}    expected_status=403
        POST On Session    ${alias}    /consultores/${A_ID}/desactivar    expected_status=403
        POST On Session    ${alias}    /consultores/${A_ID}/activar    expected_status=403
        POST On Session    ${alias}    /consultores/${A_ID}/reasignar    json=${reasig}    expected_status=403
    END
    Iniciar Sesion Como Jefe
    ${fila}=    Fila Del Consultor    intruso_${SUFIJO}@ejemplo.com
    Should Be Equal    ${fila}    ${None}
    ${fila}=    Fila Del Consultor    ${A_EMAIL}
    Should Be True    ${fila['activo']}

02 - HU-16 Sin Sesion Las Acciones Del Equipo Responden 401
    [Tags]    HU-16    seguridad
    Create Session    anonimo    ${BASE_URL}    headers=${CABECERA}
    ${alta}=    Create Dictionary    nombre=Intruso    email=anonimo_${SUFIJO}@ejemplo.com
    ${reasig}=    Create Dictionary    destino_id=${C2_ID}
    POST On Session    anonimo    /consultores    json=${alta}    expected_status=401
    POST On Session    anonimo    /consultores/${A_ID}/desactivar    expected_status=401
    POST On Session    anonimo    /consultores/${A_ID}/activar    expected_status=401
    POST On Session    anonimo    /consultores/${A_ID}/reasignar    json=${reasig}    expected_status=401

03 - HU-16 El Jefe Solo Da De Baja A Consultores
    [Documentation]    Los ids que no son de un consultor (el jefe, los promotores) responden 404:
    ...                el jefe no se puede desactivar a si mismo ni desactivar a un promotor.
    [Tags]    HU-16    seguridad
    Iniciar Sesion Como Jefe
    ${r}=    GET On Session    jefe    /consultores    expected_status=200
    ${ids}=    Evaluate    [c['id'] for c in $r.json()['consultores']]
    ${ajenos}=    Evaluate    sorted(set(range(1, max($ids) + 4)) - set($ids))
    Should Not Be Empty    ${ajenos}
    Set Suite Variable    ${AJENO_ID}    ${ajenos[0]}
    FOR    ${id}    IN    @{ajenos}
        POST On Session    jefe    /consultores/${id}/desactivar    expected_status=404
        POST On Session    jefe    /consultores/${id}/activar    expected_status=404
    END
    Iniciar Sesion Como Jefe    jefe_otra_vez
    Iniciar Sesion Como Promotor

# ---------------- HU-16: alta ----------------

04 - HU-16 El Alta Ignora El Rol Pedido Y No Devuelve La Clave Propia
    [Documentation]    Mandar rol=jefe no sube privilegios: la cuenta nace consultor y debe cambiar la clave.
    [Tags]    HU-16    seguridad
    Iniciar Sesion Como Jefe
    ${email}=    Set Variable    rol_${SUFIJO}@ejemplo.com
    ${datos}=    Create Dictionary    nombre=Rol Robot    email=${email}    password=${CLAVE_PROPIA}    rol=jefe
    ${r}=    POST On Session    jefe    /consultores    json=${datos}    expected_status=201
    Dictionary Should Not Contain Key    ${r.json()}    password_temporal
    Iniciar Sesion    rol    ${email}    ${CLAVE_PROPIA}
    ${r}=    GET On Session    rol    /sesion    expected_status=200
    Should Be Equal    ${r.json()['rol']}    consultor
    Should Be True    ${r.json()['debe_cambiar_clave']}

05 - HU-16 No Se Da De Alta Un Correo Que Ya Existe Aunque Cambien Las Mayusculas
    [Documentation]    Ni el de otro consultor, ni el de un promotor, ni el del jefe: asi no se pisa una cuenta.
    [Tags]    HU-16    seguridad
    Iniciar Sesion Como Jefe
    ${mayus}=    Evaluate    $CONSULTOR_EMAIL.upper()
    FOR    ${email}    IN    ${mayus}    ${PROMOTOR_EMAIL}    ${JEFE_EMAIL}
        ${datos}=    Create Dictionary    nombre=Duplicado    email=${email}
        POST On Session    jefe    /consultores    json=${datos}    expected_status=409
    END
    Iniciar Sesion Como Promotor

06 - HU-16 El Alta Valida Nombre Y Correo
    [Tags]    HU-16
    Iniciar Sesion Como Jefe
    ${sin_nombre}=    Create Dictionary    email=sin_nombre_${SUFIJO}@ejemplo.com
    ${blanco}=    Create Dictionary    nombre=${SPACE * 3}    email=blanco_${SUFIJO}@ejemplo.com
    ${malo}=    Create Dictionary    nombre=Correo Malo    email=no-es-un-correo
    ${no_texto}=    Create Dictionary    nombre=${123}    email=numero_${SUFIJO}@ejemplo.com
    ${vacio}=    Create Dictionary
    FOR    ${datos}    IN    ${sin_nombre}    ${blanco}    ${malo}    ${no_texto}    ${vacio}
        POST On Session    jefe    /consultores    json=${datos}    expected_status=400
    END
    FOR    ${prefijo}    IN    sin_nombre    blanco    numero
        ${fila}=    Fila Del Consultor    ${prefijo}_${SUFIJO}@ejemplo.com
        Should Be Equal    ${fila}    ${None}    msg=Una alta invalida quedo guardada (${prefijo})
    END

# ---------------- HU-16: baja logica ----------------

07 - HU-16 La Sesion De Un Consultor Desactivado No Sirve Para Escribir
    [Documentation]    El caso 24 de Helio prueba GET /sesion; aqui, con la cookie vieja,
    ...                crear expedientes y cambiar la clave tambien responden 401.
    [Tags]    HU-16    seguridad
    Iniciar Sesion    a    ${A_EMAIL}    ${CLAVE_PROPIA}
    Iniciar Sesion Como Jefe
    POST On Session    jefe    /consultores/${A_ID}/desactivar    expected_status=200
    ${exp}=    Create Dictionary    proyecto=No Debe Crearse    promotor=Nadie    categoria=I
    POST On Session    a    /expedientes    json=${exp}    expected_status=401
    ${clave}=    Create Dictionary    actual=${CLAVE_PROPIA}    nueva=Otra2026xx
    POST On Session    a    /cuenta/contrasena    json=${clave}    expected_status=401
    GET On Session    a    /expedientes/${COD_A}    expected_status=401
    ${fila}=    Fila Del Consultor    ${A_EMAIL}
    Should Be Equal As Integers    ${fila['expedientes']}    1

08 - HU-16 La Baja No Borra Los Expedientes Ni El Historial
    [Tags]    HU-16
    Iniciar Sesion Como Jefe
    ${fila}=    Fila Del Consultor    ${A_EMAIL}
    Should Not Be True    ${fila['activo']}
    ${r}=    GET On Session    jefe    /expedientes/${COD_A}    expected_status=200
    ${r}=    GET On Session    jefe    /expedientes/${COD_A}/historial    expected_status=200
    ${primera}=    Set Variable    ${r.json()['historial'][-1]}
    Should Be Equal    ${primera['accion']}    creó
    Should Be Equal    ${primera['usuario_email']}    ${A_EMAIL}

09 - HU-16 Un Consultor Desactivado No Recupera Su Cuenta Registrandose De Nuevo
    [Tags]    HU-16    seguridad
    Create Session    anonimo    ${BASE_URL}    headers=${CABECERA}
    ${datos}=    Create Dictionary    nombre=Vuelvo    email=${A_EMAIL}    password=Vuelvo2026x    rol=consultor
    POST On Session    anonimo    /registro    json=${datos}    expected_status=409
    ${login}=    Create Dictionary    email=${A_EMAIL}    password=${CLAVE_PROPIA}
    POST On Session    anonimo    /login    json=${login}    expected_status=403

# ---------------- HU-16: reasignacion ----------------

10 - HU-16 Reasignar Valida Origen Y Destino Sin Mover Nada
    [Tags]    HU-16
    Iniciar Sesion Como Jefe
    ${inexistente}=    Create Dictionary    destino_id=${ID_INEXISTENTE}
    ${texto}=    Create Dictionary    destino_id=abc
    ${no_consultor}=    Create Dictionary    destino_id=${AJENO_ID}
    ${desactivado}=    Create Dictionary    destino_id=${D_ID}
    ${vacio}=    Create Dictionary
    FOR    ${datos}    IN    ${inexistente}    ${texto}    ${no_consultor}    ${desactivado}    ${vacio}
        POST On Session    jefe    /consultores/${A_ID}/reasignar    json=${datos}    expected_status=400
    END
    ${bueno}=    Create Dictionary    destino_id=${C2_ID}
    POST On Session    jefe    /consultores/${ID_INEXISTENTE}/reasignar    json=${bueno}    expected_status=404
    ${fila}=    Fila Del Consultor    ${A_EMAIL}
    Should Be Equal As Integers    ${fila['expedientes']}    1

11 - HU-16 Tras Reasignar La Consulta Publica Muestra Al Nuevo Consultor
    [Documentation]    HU-09 muestra el consultor responsable: despues de reasignar debe ser el nuevo.
    [Tags]    HU-16    HU-09
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    destino_id=${C2_ID}
    ${r}=    POST On Session    jefe    /consultores/${A_ID}/reasignar    json=${datos}    expected_status=200
    Should Be Equal As Integers    ${r.json()['reasignados']}    1
    ${acceso}=    Create Dictionary    acceso_publico=${True}
    POST On Session    jefe    /expedientes/${COD_A}/acceso-publico    json=${acceso}    expected_status=200
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /consulta/${COD_A}    expected_status=200
    Should Be Equal    ${r.json()['expediente']['consultor']}    Consultor Dos

12 - HU-16 El Consultor Reactivado Ya No Ve Lo Que Se Reasigno
    [Tags]    HU-16    seguridad
    Iniciar Sesion Como Jefe
    POST On Session    jefe    /consultores/${A_ID}/activar    expected_status=200
    Iniciar Sesion    a    ${A_EMAIL}    ${CLAVE_PROPIA}
    ${r}=    GET On Session    a    /expedientes/${COD_A}    expected_status=any
    Should Be True    ${r.status_code} in (403, 404)    msg=El consultor original sigue viendo el expediente (${r.status_code})
    ${r}=    GET On Session    a    /expedientes    expected_status=200
    Should Not Contain    ${r.text}    ${COD_A}
    Iniciar Sesion    c2    ${CONSULTOR2_EMAIL}    ${CONSULTOR2_PASSWORD}
    GET On Session    c2    /expedientes/${COD_A}    expected_status=200

13 - HU-16 Reasignar A Un Consultor Sin Expedientes Responde Cero
    [Tags]    HU-16
    Iniciar Sesion Como Jefe
    POST On Session    jefe    /consultores/${A_ID}/desactivar    expected_status=200
    ${datos}=    Create Dictionary    destino_id=${C2_ID}
    ${r}=    POST On Session    jefe    /consultores/${A_ID}/reasignar    json=${datos}    expected_status=200
    Should Be Equal As Integers    ${r.json()['reasignados']}    0

14 - HU-16 Hallazgo El Registro Publico Crea Consultores Sin Pasar Por El Jefe
    [Documentation]    Con HU-16 el jefe da de alta a los consultores, pero /registro sigue aceptando
    ...                rol=consultor (ROLES_REGISTRO = {"consultor"}). Cualquiera crea una cuenta de
    ...                consultor sin el jefe, y un consultor dado de baja vuelve con otro correo.
    ...                Esperado: 400 o 403, como ya pasa con promotor y jefe. Hoy responde 201.
    [Tags]    HU-16    seguridad    hallazgo    robot:skip-on-failure
    Create Session    anonimo    ${BASE_URL}    headers=${CABECERA}
    ${datos}=    Create Dictionary    nombre=Sin Jefe    email=sin_jefe_${SUFIJO}@ejemplo.com
    ...    password=SinJefe2026x    rol=consultor
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=any
    Should Be True    ${r.status_code} in (400, 403)
    ...    msg=/registro creo un consultor sin el jefe (HTTP ${r.status_code})

# ---------------- HU-12: celular (lo que se ve sin navegador) ----------------

15 - HU-12 Las Pantallas Internas Traen Viewport, Menu Lateral Y El Script Del Menu
    [Tags]    HU-12
    Create Session    web    ${BASE_URL}
    FOR    ${pagina}    IN    dashboard    expedientes    expediente-detalle    expediente-nuevo
    ...    historial    equipo    cuenta    consulta-publica
        ${r}=    GET On Session    web    /${pagina}.html    expected_status=200
        Should Contain    ${r.text}    name="viewport"    msg=${pagina}.html sin viewport
        Should Contain    ${r.text}    class="rail"    msg=${pagina}.html sin menu lateral
        Should Contain    ${r.text}    js/api.js    msg=${pagina}.html no carga el menu del celular
    END
    ${r}=    GET On Session    web    /js/api.js    expected_status=200
    Should Contain    ${r.text}    function iniciarMenuMovil
    Should Contain    ${r.text}    aria-expanded
    Should Contain    ${r.text}    Escape

16 - HU-12 Mis Expedientes, Historial Y Equipo Se Muestran Como Tarjetas
    [Tags]    HU-12
    Create Session    web    ${BASE_URL}
    FOR    ${pagina}    IN    expedientes    historial    equipo
        ${r}=    GET On Session    web    /${pagina}.html    expected_status=200
        Should Match Regexp    ${r.text}    class="ledger[^"]*tarjetas    msg=${pagina}.html sin tabla en tarjetas
        Should Contain    ${r.text}    data-label="    msg=${pagina}.html sin etiquetas por celda
    END
    ${r}=    GET On Session    web    /css/estilos.css    expected_status=200
    Should Contain    ${r.text}    @media (max-width: 820px)
    Should Contain    ${r.text}    @media (max-width: 640px)
    Should Contain    ${r.text}    body.menu-abierto .rail

17 - HU-12 HU-16 El Enlace Equipo Solo Se Oculta: La Proteccion Esta En La API
    [Documentation]    equipo.html es un archivo estatico (cualquiera lo descarga); lo que importa
    ...                es que los datos del equipo solo salen para el jefe.
    [Tags]    HU-12    HU-16    seguridad
    Create Session    web    ${BASE_URL}
    ${r}=    GET On Session    web    /dashboard.html    expected_status=200
    Should Contain    ${r.text}    id="nav-equipo" style="display:none;"
    Iniciar Sesion Como Consultor
    GET On Session    consultor    /equipo.html    expected_status=200
    ${r}=    GET On Session    consultor    /consultores    expected_status=403
    Should Not Contain    ${r.text}    @ejemplo.com

*** Keywords ***
Preparar Suite
    [Documentation]    Crea sus propios consultores para no tocar los del seed:
    ...                A (con clave propia y un expediente) y D (desactivado, destino invalido).
    ${sufijo}=    Evaluate    int(time.time())    modules=time
    Set Suite Variable    ${SUFIJO}    ${sufijo}
    ${cabecera}=    Create Dictionary    X-Requested-With=fetch
    Set Suite Variable    ${CABECERA}    ${cabecera}
    Set Suite Variable    ${A_EMAIL}    equipo_a_${sufijo}@ejemplo.com
    Iniciar Sesion Como Jefe
    ${datos}=    Create Dictionary    nombre=Equipo A ${sufijo}    email=${A_EMAIL}    password=${CLAVE_INICIAL}
    ${r}=    POST On Session    jefe    /consultores    json=${datos}    expected_status=201
    Set Suite Variable    ${A_ID}    ${r.json()['id']}
    ${datos}=    Create Dictionary    nombre=Equipo D ${sufijo}    email=equipo_d_${sufijo}@ejemplo.com
    ${r}=    POST On Session    jefe    /consultores    json=${datos}    expected_status=201
    Set Suite Variable    ${D_ID}    ${r.json()['id']}
    POST On Session    jefe    /consultores/${D_ID}/desactivar    expected_status=200
    ${c2}=    Fila Del Consultor    ${CONSULTOR2_EMAIL}
    Set Suite Variable    ${C2_ID}    ${c2['id']}
    Iniciar Sesion    a    ${A_EMAIL}    ${CLAVE_INICIAL}
    ${clave}=    Create Dictionary    actual=${CLAVE_INICIAL}    nueva=${CLAVE_PROPIA}
    POST On Session    a    /cuenta/contrasena    json=${clave}    expected_status=200
    ${exp}=    Create Dictionary    proyecto=Expediente Equipo A    promotor=Promotor Equipo    categoria=I
    ${r}=    POST On Session    a    /expedientes    json=${exp}    expected_status=201
    Set Suite Variable    ${COD_A}    ${r.json()['codigo']}

Iniciar Sesion Como Jefe
    [Arguments]    ${alias}=jefe
    Iniciar Sesion    ${alias}    ${JEFE_EMAIL}    ${JEFE_PASSWORD}

Fila Del Consultor
    [Documentation]    Fila de GET /consultores con ese correo, o None. Usa la sesion "jefe".
    ...                Sin variables dentro de la comprension (Python 3.11 del CI).
    [Arguments]    ${email}
    ${r}=    GET On Session    jefe    /consultores    expected_status=200
    ${fila}=    Evaluate    next((c for c in $r.json()['consultores'] if c['email'] == '${email}'), None)
    RETURN    ${fila}
