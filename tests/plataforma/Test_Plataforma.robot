*** Settings ***
Documentation     Plataforma multiempresa: aislamiento entre consultoras, invitaciones, seguridad de la
...               cuenta (dos pasos, recuperacion, sesiones), marca propia, colaboracion, reportes y
...               operacion (estado, errores, respaldos). Necesita la semilla con las dos empresas.
Library           RequestsLibrary
Library           Collections
Library           ayudas.py
Resource          ../recursos/sesion.resource
Suite Setup       Preparar La Suite

*** Variables ***
${BASE_URL}       http://localhost:5000
${CODIGO_A}       SP-A8-2026-001
${CODIGO_B}       SP-A8-2026-201
${CLAVE}          Clave12345
${SUFIJO}         ${EMPTY}
${CABECERA}       ${EMPTY}

*** Test Cases ***
# ---------------------------------------------------------------- Aislamiento entre empresas
01 - Cada empresa lista solo sus expedientes
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe2    url=/expedientes?per_page=100
    ${codigos}=    Evaluate    [e['codigo'] for e in $r.json()['expedientes']]
    Should Contain    ${codigos}    ${CODIGO_B}
    Should Not Contain    ${codigos}    ${CODIGO_A}
    Iniciar Sesion Como Jefe    jefe
    ${r}=    GET On Session    jefe    url=/expedientes?per_page=100
    ${codigos}=    Evaluate    [e['codigo'] for e in $r.json()['expedientes']]
    Should Contain    ${codigos}    ${CODIGO_A}
    Should Not Contain    ${codigos}    ${CODIGO_B}

02 - El expediente de otra empresa responde 404 (ni siquiera se confirma que existe)
    Iniciar Sesion Como Jefe    jefe
    ${r}=    GET On Session    jefe    /expedientes/${CODIGO_B}    expected_status=any
    Status Should Be    404    ${r}
    Iniciar Sesion Como Consultor De La Otra Empresa    consultor3
    ${r}=    GET On Session    consultor3    /expedientes/${CODIGO_A}    expected_status=any
    Status Should Be    404    ${r}

03 - No se puede operar sobre un expediente de otra empresa
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${vacio}=    Create Dictionary    motivo=intento entre empresas
    ${r}=    POST On Session    jefe2    /expedientes/${CODIGO_A}/aprobar    json=${vacio}    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    POST On Session    jefe2    /expedientes/${CODIGO_A}/someter    json=${vacio}    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    GET On Session    jefe2    /expedientes/${CODIGO_A}/historial    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    GET On Session    jefe2    /expedientes/${CODIGO_A}/pdf    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    GET On Session    jefe2    /expedientes/${CODIGO_A}/plazos.ics    expected_status=any
    Status Should Be    404    ${r}

04 - El historial, el equipo y la busqueda tampoco cruzan empresas
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe2    url=/historial?per_page=200
    ${codigos}=    Evaluate    {h['codigo'] for h in $r.json()['historial']}
    Should Not Contain    ${codigos}    ${CODIGO_A}
    ${r}=    GET On Session    jefe2    /consultores
    ${correos}=    Evaluate    [c['email'] for c in $r.json()['consultores']]
    Should Contain    ${correos}    consultor3@ejemplo.com
    Should Not Contain    ${correos}    consultor1@ejemplo.com
    ${r}=    GET On Session    jefe2    url=/buscar?q=SP-A8-2026
    ${encontrados}=    Evaluate    [e['codigo'] for e in $r.json()['expedientes']]
    Should Contain    ${encontrados}    ${CODIGO_B}
    Should Not Contain    ${encontrados}    ${CODIGO_A}

05 - Un jefe no puede actuar sobre el equipo de otra empresa
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${id}=    Id De Usuario    consultor1@ejemplo.com
    ${vacio}=    Create Dictionary
    ${r}=    POST On Session    jefe2    /consultores/${id}/desactivar    json=${vacio}    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    POST On Session    jefe2    /consultores/${id}/restablecer-clave    json=${vacio}    expected_status=any
    Status Should Be    404    ${r}
    ${datos}=    Create Dictionary    usuario_id=${id}
    ${r}=    POST On Session    jefe2    /expedientes/${CODIGO_B}/responsable    json=${datos}    expected_status=any
    Status Should Be    404    ${r}

06 - El administrador de la plataforma no ve expedientes
    Iniciar Sesion Como Administrador    admin
    ${r}=    GET On Session    admin    /expedientes
    Should Be Empty    ${r.json()['expedientes']}
    ${r}=    GET On Session    admin    /expedientes/${CODIGO_A}    expected_status=any
    Status Should Be    403    ${r}
    ${r}=    GET On Session    admin    /historial    expected_status=any
    Status Should Be    403    ${r}

07 - El reporte de cartera solo trae la empresa del usuario
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe2    /exportar/cartera.xlsx
    Should Contain    ${r.headers['Content-Type']}    spreadsheetml
    ${texto}=    Textos De Xlsx    ${r.content}
    Should Contain    ${texto}    ${CODIGO_B}
    Should Not Contain    ${texto}    ${CODIGO_A}
    ${r}=    GET On Session    jefe2    /exportar/historial.csv
    Should Contain    ${r.headers['Content-Type']}    text/csv
    Should Not Contain    ${r.text}    ${CODIGO_A}

# ---------------------------------------------------------------- Invitaciones
08 - El jefe invita, la persona se registra y queda en su empresa
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    nuevo.${sufijo}@ejemplo.com
    ${token}=    Invitar Como Jefe    ${correo}
    ${r}=    Registrar Con Invitacion    ${correo}    ${token}
    Status Should Be    201    ${r}
    Iniciar Sesion    nuevo    ${correo}    ${CLAVE}
    ${s}=    GET On Session    nuevo    /sesion
    Should Be Equal    ${s.json()['empresa']['nombre']}    Consultora Demo
    Should Be Equal    ${s.json()['rol']}    consultor
    ${r}=    GET On Session    nuevo    /expedientes
    Should Be Empty    ${r.json()['expedientes']}

09 - La invitacion se usa una sola vez
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    una.vez.${sufijo}@ejemplo.com
    ${token}=    Invitar Como Jefe    ${correo}
    ${r}=    Registrar Con Invitacion    ${correo}    ${token}
    Status Should Be    201    ${r}
    ${r}=    Registrar Con Invitacion    otra.${sufijo}@ejemplo.com    ${token}
    Status Should Be    400    ${r}

10 - Una invitacion hecha para un correo no sirve para otro
    ${sufijo}=    Sufijo Unico
    ${token}=    Invitar Como Jefe    previsto.${sufijo}@ejemplo.com
    ${r}=    Registrar Con Invitacion    intruso.${sufijo}@ejemplo.com    ${token}
    Status Should Be    400    ${r}
    ${r}=    Registrar Con Invitacion    previsto.${sufijo}@ejemplo.com    ${token}
    Status Should Be    201    ${r}

11 - Registro sin aceptar los terminos o con invitacion inventada se rechaza
    ${sufijo}=    Sufijo Unico
    ${token}=    Invitar Como Jefe    terminos.${sufijo}@ejemplo.com
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    nombre=Sin Terminos    email=terminos.${sufijo}@ejemplo.com
    ...    password=${CLAVE}    invitacion=${token}
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=any
    Status Should Be    400    ${r}
    ${r}=    Registrar Con Invitacion    falsa.${sufijo}@ejemplo.com    token-inventado-que-no-existe
    Status Should Be    400    ${r}

12 - Un consultor no puede invitar y un jefe no revoca invitaciones ajenas
    Iniciar Sesion Como Consultor    consultor
    ${datos}=    Create Dictionary
    ${r}=    POST On Session    consultor    /invitaciones    json=${datos}    expected_status=any
    Status Should Be    403    ${r}
    Iniciar Sesion Como Jefe    jefe
    ${r}=    POST On Session    jefe    /invitaciones    json=${datos}
    Status Should Be    201    ${r}
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe    /invitaciones
    ${id}=    Set Variable    ${r.json()['invitaciones'][0]['id']}
    ${r}=    DELETE On Session    jefe2    /invitaciones/${id}    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    DELETE On Session    jefe    /invitaciones/${id}
    Status Should Be    200    ${r}

13 - La pantalla de registro consulta a que empresa se une la persona
    ${token}=    Invitar Como Jefe
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /invitaciones/validar    params=token=${token}
    Should Be Equal    ${r.json()['empresa']}    Consultora Demo
    Should Be Equal    ${r.json()['rol']}    consultor

14 - El administrador crea una empresa nueva y su jefe entra sin ver nada de las demas
    ${sufijo}=    Sufijo Unico
    Iniciar Sesion Como Administrador    admin
    ${datos}=    Create Dictionary    nombre=Empresa Robot ${sufijo}    email_jefe=jefe.${sufijo}@ejemplo.com
    ${r}=    POST On Session    admin    /plataforma/empresas    json=${datos}
    Status Should Be    201    ${r}
    ${token}=    Evaluate    $r.json()['enlace'].split('invitacion=')[1]
    ${r}=    Registrar Con Invitacion    jefe.${sufijo}@ejemplo.com    ${token}
    Status Should Be    201    ${r}
    Iniciar Sesion    jefenuevo    jefe.${sufijo}@ejemplo.com    ${CLAVE}
    ${s}=    GET On Session    jefenuevo    /sesion
    Should Be Equal    ${s.json()['rol']}    jefe
    Should Be Equal    ${s.json()['empresa']['nombre']}    Empresa Robot ${sufijo}
    ${r}=    GET On Session    jefenuevo    /expedientes
    Should Be Empty    ${r.json()['expedientes']}
    ${r}=    GET On Session    jefenuevo    /consultores
    Should Be Empty    ${r.json()['consultores']}

15 - Una empresa desactivada no puede entrar y al reactivarla vuelve
    ${sufijo}=    Sufijo Unico
    Iniciar Sesion Como Administrador    admin
    ${datos}=    Create Dictionary    nombre=Pausa Robot ${sufijo}    email_jefe=pausa.${sufijo}@ejemplo.com
    ${r}=    POST On Session    admin    /plataforma/empresas    json=${datos}
    ${id}=    Set Variable    ${r.json()['id']}
    ${token}=    Evaluate    $r.json()['enlace'].split('invitacion=')[1]
    Registrar Con Invitacion    pausa.${sufijo}@ejemplo.com    ${token}
    Iniciar Sesion    pausa    pausa.${sufijo}@ejemplo.com    ${CLAVE}
    ${apagar}=    Create Dictionary    activa=${False}
    POST On Session    admin    /plataforma/empresas/${id}/activa    json=${apagar}
    ${r}=    GET On Session    pausa    /sesion    expected_status=any
    Status Should Be    401    ${r}
    Create Session    anonimo    ${BASE_URL}
    ${login}=    Create Dictionary    email=pausa.${sufijo}@ejemplo.com    password=${CLAVE}
    ${r}=    POST On Session    anonimo    /login    json=${login}    expected_status=any
    Status Should Be    403    ${r}
    ${encender}=    Create Dictionary    activa=${True}
    POST On Session    admin    /plataforma/empresas/${id}/activa    json=${encender}
    ${r}=    POST On Session    anonimo    /login    json=${login}
    Status Should Be    200    ${r}

16 - Solo el administrador usa las funciones de la plataforma
    Iniciar Sesion Como Jefe    jefe
    FOR    ${ruta}    IN    /plataforma/empresas    /plataforma/estado    /plataforma/errores    /plataforma/respaldos
        ${r}=    GET On Session    jefe    ${ruta}    expected_status=any
        Status Should Be    403    ${r}
    END
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /plataforma/estado    expected_status=any
    Status Should Be    401    ${r}

16b - La administracion tiene su propia puerta (/admin) y no entra por el login normal
    Create Session    anonimo    ${BASE_URL}
    ${admin}=    Create Dictionary    email=${ADMIN_EMAIL}    password=${ADMIN_PASSWORD}
    ${r}=    POST On Session    anonimo    /login    json=${admin}    expected_status=any
    Status Should Be    401    ${r}
    Should Not Be True    ${r.json()['acceso']}
    ${jefe}=    Create Dictionary    email=${JEFE_EMAIL}    password=${JEFE_PASSWORD}
    ${r}=    POST On Session    anonimo    /admin/login    json=${jefe}    expected_status=any
    Status Should Be    401    ${r}
    ${r}=    POST On Session    anonimo    /admin/login    json=${admin}
    Status Should Be    200    ${r}
    Should Be Equal    ${r.json()['rol']}    admin
    Create Session    publico    ${BASE_URL}
    ${r}=    GET On Session    publico    /admin
    Should Contain    ${r.headers['X-Robots-Tag']}    noindex
    ${r}=    GET On Session    publico    /admin/panel
    Status Should Be    200    ${r}
    # Los archivos del panel no se sirven por su nombre ni se enlazan desde la pagina publica.
    ${r}=    GET On Session    publico    /plataforma.html    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    GET On Session    publico    /admin.html    expected_status=any
    Status Should Be    404    ${r}
    ${portada}=    GET On Session    publico    /
    Should Not Contain    ${portada.text}    /admin
    Should Not Contain    ${portada.text}    plataforma.html

# ---------------------------------------------------------------- Seguridad de la cuenta
17 - Dos pasos: se activa, se exige al entrar y un codigo no se reutiliza
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    dospasos.${sufijo}@ejemplo.com
    Crear Cuenta Nueva    ${correo}
    Iniciar Sesion    u2fa    ${correo}    ${CLAVE}
    ${confirma}=    Create Dictionary    password=${CLAVE}
    ${r}=    POST On Session    u2fa    /cuenta/2fa/preparar    json=${confirma}
    ${secreto}=    Set Variable    ${r.json()['secreto']}
    Should Contain    ${r.json()['qr']}    <svg
    ${mal}=    Create Dictionary    codigo=000000
    ${r}=    POST On Session    u2fa    /cuenta/2fa/activar    json=${mal}    expected_status=any
    Status Should Be    400    ${r}
    ${codigo}=    Codigo Totp    ${secreto}
    ${bueno}=    Create Dictionary    codigo=${codigo}
    ${r}=    POST On Session    u2fa    /cuenta/2fa/activar    json=${bueno}
    Length Should Be    ${r.json()['codigos']}    8
    Create Session    anonimo    ${BASE_URL}
    ${login}=    Create Dictionary    email=${correo}    password=${CLAVE}
    ${r}=    POST On Session    anonimo    /login    json=${login}    expected_status=any
    Status Should Be    401    ${r}
    Should Be True    ${r.json()['requiere_2fa']}
    ${siguiente}=    Codigo Totp    ${secreto}    1
    ${login}=    Create Dictionary    email=${correo}    password=${CLAVE}    codigo=${siguiente}
    ${r}=    POST On Session    anonimo    /login    json=${login}
    Status Should Be    200    ${r}
    ${r}=    POST On Session    anonimo    /login    json=${login}    expected_status=any
    Status Should Be    401    ${r}

18 - Un codigo de recuperacion sustituye al telefono una sola vez
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    recupera.${sufijo}@ejemplo.com
    Crear Cuenta Nueva    ${correo}
    Iniciar Sesion    ur    ${correo}    ${CLAVE}
    ${confirma}=    Create Dictionary    password=${CLAVE}
    ${r}=    POST On Session    ur    /cuenta/2fa/preparar    json=${confirma}
    ${codigo}=    Codigo Totp    ${r.json()['secreto']}
    ${bueno}=    Create Dictionary    codigo=${codigo}
    ${r}=    POST On Session    ur    /cuenta/2fa/activar    json=${bueno}
    ${recuperacion}=    Set Variable    ${r.json()['codigos'][0]}
    Create Session    anonimo    ${BASE_URL}
    ${login}=    Create Dictionary    email=${correo}    password=${CLAVE}    codigo=${recuperacion}
    ${r}=    POST On Session    anonimo    /login    json=${login}
    Status Should Be    200    ${r}
    ${r}=    POST On Session    anonimo    /login    json=${login}    expected_status=any
    Status Should Be    401    ${r}

19 - Recuperar la contrasena con un codigo (sin correo) y cerrar las demas sesiones
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    olvido.${sufijo}@ejemplo.com
    Crear Cuenta Nueva    ${correo}
    Iniciar Sesion    olvido    ${correo}    ${CLAVE}
    ${confirma}=    Create Dictionary    password=${CLAVE}
    ${r}=    POST On Session    olvido    /cuenta/codigos-recuperacion    json=${confirma}
    ${recuperacion}=    Set Variable    ${r.json()['codigos'][0]}
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    email=${correo}    codigo=${recuperacion}    password=Nueva12345
    ${r}=    POST On Session    anonimo    /recuperar    json=${datos}
    Status Should Be    200    ${r}
    ${r}=    GET On Session    olvido    /sesion    expected_status=any
    Status Should Be    401    ${r}
    ${r}=    POST On Session    anonimo    /recuperar    json=${datos}    expected_status=any
    Status Should Be    400    ${r}
    Iniciar Sesion    olvido    ${correo}    Nueva12345

20 - Cerrar sesiones deja abierta solo la actual y cambiar la contrasena cierra las otras
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    sesiones.${sufijo}@ejemplo.com
    Crear Cuenta Nueva    ${correo}
    Iniciar Sesion    telefono    ${correo}    ${CLAVE}
    Iniciar Sesion    portatil    ${correo}    ${CLAVE}
    ${confirma}=    Create Dictionary    password=${CLAVE}
    POST On Session    portatil    /cuenta/cerrar-sesiones    json=${confirma}
    ${r}=    GET On Session    telefono    /sesion    expected_status=any
    Status Should Be    401    ${r}
    ${r}=    GET On Session    portatil    /sesion
    Status Should Be    200    ${r}
    Iniciar Sesion    otro    ${correo}    ${CLAVE}
    ${cambio}=    Create Dictionary    actual=${CLAVE}    nueva=Cambiada12345
    POST On Session    portatil    /cuenta/contrasena    json=${cambio}
    ${r}=    GET On Session    otro    /sesion    expected_status=any
    Status Should Be    401    ${r}
    ${r}=    GET On Session    portatil    /sesion
    Status Should Be    200    ${r}

21 - El jefe restablece la contrasena de su consultor y las sesiones de este se cierran
    ${sufijo}=    Sufijo Unico
    ${correo}=    Set Variable    reset.${sufijo}@ejemplo.com
    Crear Cuenta Nueva    ${correo}
    Iniciar Sesion    consulta    ${correo}    ${CLAVE}
    ${id}=    Id De Usuario    ${correo}
    Iniciar Sesion Como Jefe    jefe
    ${vacio}=    Create Dictionary
    ${r}=    POST On Session    jefe    /consultores/${id}/restablecer-clave    json=${vacio}
    ${temporal}=    Set Variable    ${r.json()['password_temporal']}
    ${r}=    GET On Session    consulta    /sesion    expected_status=any
    Status Should Be    401    ${r}
    Create Session    anonimo    ${BASE_URL}
    ${login}=    Create Dictionary    email=${correo}    password=${temporal}
    ${r}=    POST On Session    anonimo    /login    json=${login}
    Should Be True    ${r.json()['debe_cambiar_clave']}

22 - El administrador restablece el acceso de un jefe pero no de un consultor
    Iniciar Sesion Como Administrador    admin
    ${id}=    Id De Usuario    consultor1@ejemplo.com
    ${vacio}=    Create Dictionary
    ${r}=    POST On Session    admin    /plataforma/jefes/${id}/restablecer    json=${vacio}    expected_status=any
    Status Should Be    404    ${r}

23 - Recuperar contrasena tiene limite de intentos
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    email=nadie@ejemplo.com    codigo=ABCDE-FGHJK    password=Nueva12345
    ${bloqueado}=    Set Variable    ${False}
    FOR    ${i}    IN RANGE    8
        ${r}=    POST On Session    anonimo    /recuperar    json=${datos}    expected_status=any
        IF    ${r.status_code} == 429
            ${bloqueado}=    Set Variable    ${True}
            BREAK
        END
        Status Should Be    400    ${r}
    END
    Should Be True    ${bloqueado}    Tras varios intentos fallidos el servidor debia responder 429.

# ---------------------------------------------------------------- Marca, equipo y reportes
24 - El jefe cambia el color y el logo de su empresa; el consultor no
    Iniciar Sesion Como Jefe    jefe
    ${invalido}=    Create Dictionary    color=#123456
    ${r}=    POST On Session    jefe    /organizacion    json=${invalido}    expected_status=any
    Status Should Be    400    ${r}
    ${valido}=    Create Dictionary    color=#2563a8
    ${r}=    POST On Session    jefe    /organizacion    json=${valido}
    Should Be Equal    ${r.json()['empresa']['color']}    \#2563a8
    ${png}=    Png Minimo
    ${archivo}=    Create List    logo.png    ${png}    image/png
    ${files}=    Create Dictionary    logo=${archivo}
    ${r}=    POST On Session    jefe    /organizacion/logo    files=${files}
    ${url}=    Set Variable    ${r.json()['empresa']['logo']}
    Should Start With    ${url}    /organizacion/logo/
    Create Session    anonimo    ${BASE_URL}
    ${img}=    GET On Session    anonimo    ${url}
    Should Be Equal    ${img.headers['Content-Type']}    image/png
    ${falso}=    Create List    logo.png    no soy una imagen    image/png
    ${files}=    Create Dictionary    logo=${falso}
    ${r}=    POST On Session    jefe    /organizacion/logo    files=${files}    expected_status=any
    Status Should Be    400    ${r}
    Iniciar Sesion Como Consultor    consultor
    ${files}=    Create Dictionary    logo=${archivo}
    ${r}=    POST On Session    consultor    /organizacion/logo    files=${files}    expected_status=any
    Status Should Be    403    ${r}
    ${restaurar}=    Create Dictionary    color=#17805a
    POST On Session    jefe    /organizacion    json=${restaurar}

25 - La consulta publica muestra la marca de la empresa
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /consulta/${CODIGO_A}
    Should Be Equal    ${r.json()['empresa']['nombre']}    Consultora Demo
    Dictionary Should Not Contain Key    ${r.json()['empresa']}    id

26 - El jefe cambia al responsable y queda en el historial
    Iniciar Sesion Como Jefe    jefe
    ${id2}=    Id De Usuario    consultor2@ejemplo.com
    ${datos}=    Create Dictionary    usuario_id=${id2}
    ${r}=    POST On Session    jefe    /expedientes/${CODIGO_A}/responsable    json=${datos}
    Should Be Equal    ${r.json()['responsable']['nombre']}    Ana Ríos
    ${r}=    POST On Session    jefe    /expedientes/${CODIGO_A}/responsable    json=${datos}    expected_status=any
    Status Should Be    409    ${r}
    ${r}=    GET On Session    jefe    /expedientes/${CODIGO_A}
    Should Be Equal    ${r.json()['responsable']['nombre']}    Ana Ríos
    ${r}=    GET On Session    jefe    /expedientes/${CODIGO_A}/historial
    ${acciones}=    Evaluate    [h['accion'] for h in $r.json()['historial']]
    ${hay}=    Evaluate    any(a.startswith('cambió el responsable') for a in $acciones)
    Should Be True    ${hay}
    Iniciar Sesion Como Consultor    consultor
    ${id1}=    Id De Usuario    consultor1@ejemplo.com
    ${vuelve}=    Create Dictionary    usuario_id=${id1}
    ${r}=    POST On Session    consultor    /expedientes/${CODIGO_A}/responsable    json=${vuelve}    expected_status=any
    Status Should Be    403    ${r}
    POST On Session    jefe    /expedientes/${CODIGO_A}/responsable    json=${vuelve}

27 - Los comentarios internos los ve la consultora y no el promotor ni otra empresa
    Iniciar Sesion Como Consultor    consultor
    ${datos}=    Create Dictionary    texto=Falta el paz y salvo del municipio.
    ${r}=    POST On Session    consultor    /expedientes/${CODIGO_A}/comentarios    json=${datos}
    Status Should Be    201    ${r}
    Iniciar Sesion Como Jefe    jefe
    ${r}=    GET On Session    jefe    /expedientes/${CODIGO_A}/comentarios
    ${textos}=    Evaluate    [c['texto'] for c in $r.json()['comentarios']]
    Should Contain    ${textos}    Falta el paz y salvo del municipio.
    Iniciar Sesion Como Promotor    promotor
    ${r}=    GET On Session    promotor    /expedientes/${CODIGO_A}/comentarios    expected_status=any
    Status Should Be    403    ${r}
    Iniciar Sesion Como Jefe De La Otra Empresa    jefe2
    ${r}=    GET On Session    jefe2    /expedientes/${CODIGO_A}/comentarios    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    POST On Session    jefe2    /expedientes/${CODIGO_A}/comentarios    json=${datos}    expected_status=any
    Status Should Be    404    ${r}

28 - Las vistas guardadas son de cada usuario y solo admiten filtros conocidos
    Iniciar Sesion Como Consultor    consultor
    ${filtros}=    Create Dictionary    estado=pendiente    q=solar
    ${datos}=    Create Dictionary    nombre=Pendientes solares    filtros=${filtros}
    ${r}=    POST On Session    consultor    /vistas    json=${datos}
    ${id}=    Set Variable    ${r.json()['id']}
    ${r}=    GET On Session    consultor    /vistas
    ${nombres}=    Evaluate    [v['nombre'] for v in $r.json()['vistas']]
    Should Contain    ${nombres}    Pendientes solares
    ${raro}=    Create Dictionary    sql=1 OR 1=1
    ${datos}=    Create Dictionary    nombre=Raro    filtros=${raro}
    ${r}=    POST On Session    consultor    /vistas    json=${datos}    expected_status=any
    Status Should Be    400    ${r}
    Iniciar Sesion Como Jefe    jefe
    ${r}=    DELETE On Session    jefe    /vistas/${id}    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    DELETE On Session    consultor    /vistas/${id}
    Status Should Be    200    ${r}

28b - El listado trae lo que necesitan el tablero, el cronograma y el calendario
    Iniciar Sesion Como Consultor    consultor
    ${r}=    GET On Session    consultor    url=/expedientes?per_page=100
    ${e}=    Set Variable    ${r.json()['expedientes'][0]}
    Dictionary Should Contain Key    ${e['plazo']}    fecha_limite
    Dictionary Should Contain Key    ${e['plazo']}    fecha_inicio
    Dictionary Should Contain Key    ${e}    documentos
    Dictionary Should Contain Key    ${e['documentos']}    recibidos
    Dictionary Should Contain Key    ${e['documentos']}    total
    Dictionary Should Contain Key    ${e}    comentarios
    # El cliente (promotor) no recibe datos internos: ni IPE, ni documentos, ni comentarios.
    Iniciar Sesion Como Promotor    promotor
    ${r}=    GET On Session    promotor    url=/expedientes?per_page=100
    ${p}=    Set Variable    ${r.json()['expedientes'][0]}
    Dictionary Should Not Contain Key    ${p}    ipe
    Dictionary Should Not Contain Key    ${p}    documentos
    Dictionary Should Not Contain Key    ${p}    comentarios
    # Una vista guardada recuerda la pestana y la agrupacion
    ${filtros}=    Create Dictionary    vista=tablero    grupo=responsable    estado=pendiente
    ${datos}=    Create Dictionary    nombre=Tablero pendientes    filtros=${filtros}
    ${r}=    POST On Session    consultor    /vistas    json=${datos}
    ${id}=    Set Variable    ${r.json()['id']}
    ${r}=    GET On Session    consultor    /vistas
    ${guardada}=    Evaluate    [v for v in $r.json()['vistas'] if v['id'] == ${id}][0]
    Should Be Equal    ${guardada['filtros']['vista']}    tablero
    DELETE On Session    consultor    /vistas/${id}

29 - Las exportaciones no ejecutan formulas
    Iniciar Sesion Como Consultor    consultor
    ${datos}=    Create Dictionary    proyecto==HYPERLINK("http://x","clic")    promotor=Promotor Prueba    categoria=I
    ${r}=    POST On Session    consultor    /expedientes    json=${datos}
    ${codigo}=    Set Variable    ${r.json()['codigo']}
    ${r}=    GET On Session    consultor    /exportar/cartera.xlsx
    ${texto}=    Textos De Xlsx    ${r.content}
    Should Contain    ${texto}    '=HYPERLINK
    ${r}=    GET On Session    consultor    /exportar/historial.csv
    Should Start With    ${r.text}    ﻿Fecha

# ---------------------------------------------------------------- Operacion
30 - El estado del servicio es publico y las cabeceras de seguridad estan puestas
    Create Session    anonimo    ${BASE_URL}
    ${r}=    GET On Session    anonimo    /estado
    Should Be Equal    ${r.json()['servicio']}    operativo
    Should Be True    ${r.json()['base_de_datos']}
    Should Be True    ${r.json()['archivos']}
    ${csp}=    Set Variable    ${r.headers['Content-Security-Policy']}
    Should Contain    ${csp}    default-src 'self'
    Should Contain    ${csp}    frame-ancestors 'none'
    Should Contain    ${csp}    object-src 'none'
    Should Not Contain    ${csp}    script-src 'self' 'unsafe-inline'
    Should Be Equal    ${r.headers['X-Frame-Options']}    DENY
    Should Be Equal    ${r.headers['X-Content-Type-Options']}    nosniff
    Dictionary Should Contain Key    ${r.headers}    X-Request-Id

31 - El administrador ve el estado detallado y el registro de errores
    Iniciar Sesion Como Administrador    admin
    ${r}=    GET On Session    admin    /plataforma/estado
    Should Be Equal    ${r.json()['almacenamiento']}    local
    Dictionary Should Contain Key    ${r.json()}    ultimo_respaldo
    ${r}=    GET On Session    admin    /plataforma/errores
    Dictionary Should Contain Key    ${r.json()}    errores

31b - El resumen del administrador trae cifras agregadas y nunca contenido de expedientes
    Iniciar Sesion Como Administrador    admin
    ${r}=    GET On Session    admin    /plataforma/resumen
    ${d}=    Set Variable    ${r.json()}
    Should Be True    ${d['empresas']['total']} >= 2
    Should Be True    ${d['empresas']['activas']} <= ${d['empresas']['total']}
    Should Be True    ${d['expedientes']['total']} >= 1
    Should Be True    ${d['usuarios']['por_rol']['jefe']['total']} >= 2
    Length Should Be    ${d['actividad']}    14
    ${nombres}=    Evaluate    [e['nombre'] for e in $d['ranking']]
    Should Contain    ${nombres}    Consultora Demo
    Should Contain    ${nombres}    Ambiental del Pacífico
    # Solo agregados: ni el texto de un expediente ni de un comentario puede aparecer en la respuesta.
    Should Not Contain    ${r.text}    SP-A8-2026
    Should Not Contain    ${r.text}    paz y salvo
    Iniciar Sesion Como Jefe    jefe
    ${r}=    GET On Session    jefe    /plataforma/resumen    expected_status=any
    Status Should Be    403    ${r}

32 - Respaldo: se crea, se verifica y restaurarlo devuelve los datos de ese momento
    Iniciar Sesion Como Administrador    admin
    ${vacio}=    Create Dictionary
    ${r}=    POST On Session    admin    /plataforma/respaldos    json=${vacio}
    ${nombre}=    Set Variable    ${r.json()['respaldo']['nombre']}
    Should Be True    ${r.json()['respaldo']['tablas']} >= 10
    ${r}=    POST On Session    admin    /plataforma/respaldos/${nombre}/verificar    json=${vacio}
    Should Be Equal As Integers    ${r.status_code}    200
    ${r}=    GET On Session    admin    /plataforma/respaldos/${nombre}
    ${es}=    Es Zip    ${r.content}
    Should Be True    ${es}
    ${dentro}=    Nombres En Zip    ${r.content}
    Should Contain    ${dentro}    manifiesto.json
    Should Contain    ${dentro}    base_de_datos.sql
    # Despues del respaldo se agrega una empresa; al restaurar debe desaparecer.
    ${sufijo}=    Sufijo Unico
    ${nueva}=    Create Dictionary    nombre=Posterior ${sufijo}
    ${r}=    POST On Session    admin    /plataforma/empresas    json=${nueva}
    ${r}=    GET On Session    admin    /plataforma/empresas
    ${nombres}=    Evaluate    [e['nombre'] for e in $r.json()['empresas']]
    Should Contain    ${nombres}    Posterior ${sufijo}
    ${sin}=    Create Dictionary    confirmar=si
    ${r}=    POST On Session    admin    /plataforma/respaldos/${nombre}/restaurar    json=${sin}    expected_status=any
    Status Should Be    400    ${r}
    ${con}=    Create Dictionary    confirmar=RESTAURAR
    ${r}=    POST On Session    admin    /plataforma/respaldos/${nombre}/restaurar    json=${con}
    Should Not Be Empty    ${r.json()['respaldo_previo']}
    ${r}=    GET On Session    admin    /plataforma/empresas
    ${nombres}=    Evaluate    [e['nombre'] for e in $r.json()['empresas']]
    Should Not Contain    ${nombres}    Posterior ${sufijo}
    Should Contain    ${nombres}    Consultora Demo

33 - Un nombre de respaldo con rutas no sirve para leer archivos del servidor
    Iniciar Sesion Como Administrador    admin
    ${r}=    GET On Session    admin    /plataforma/respaldos/..%2F..%2Fetc%2Fpasswd    expected_status=any
    Status Should Be    404    ${r}
    ${r}=    GET On Session    admin    /plataforma/respaldos/respaldo-1-2.zip    expected_status=any
    Status Should Be    404    ${r}

# ---------------------------------------------------------------- Administradores de la plataforma
34 - Un administrador invita a otro, que se une por el enlace y entra por /admin
    ${correo}=    Set Variable    admin.nuevo.${SUFIJO}@ejemplo.com
    ${token}=    Invitar Administrador    ${correo}
    # La pantalla de registro pregunta a que se une la persona: a la administracion, no a una empresa.
    Create Session    anonimo    ${BASE_URL}
    ${v}=    GET On Session    anonimo    /invitaciones/validar    params=token=${token}
    Should Be Equal    ${v.json()['rol']}    admin
    Should Contain    ${v.json()['empresa']}    administración
    ${r}=    Registrar Con Invitacion    ${correo}    ${token}
    Status Should Be    201    ${r}
    Should Be True    ${r.json()['administrador']}
    Iniciar Sesion De Administrador    admin_nuevo    ${correo}    ${CLAVE}
    ${s}=    GET On Session    admin_nuevo    /sesion
    Should Be Equal    ${s.json()['rol']}    admin
    # Y por la puerta de las consultoras no entra.
    ${datos}=    Create Dictionary    email=${correo}    password=${CLAVE}
    ${r}=    POST On Session    anonimo    /login    json=${datos}    expected_status=any
    Should Not Be Equal As Integers    ${r.status_code}    200

35 - La invitacion de administrador se usa una sola vez y se puede revocar
    ${correo}=    Set Variable    admin.una.vez.${SUFIJO}@ejemplo.com
    ${token}=    Invitar Administrador    ${correo}
    ${r}=    Registrar Con Invitacion    ${correo}    ${token}
    Status Should Be    201    ${r}
    ${r}=    Registrar Con Invitacion    otro.${correo}    ${token}
    Status Should Be    400    ${r}
    # Una revocada tampoco sirve
    Iniciar Sesion Como Administrador    admin
    ${otro}=    Set Variable    admin.revocada.${SUFIJO}@ejemplo.com
    ${datos}=    Create Dictionary    email=${otro}
    ${i}=    POST On Session    admin    /plataforma/administradores/invitaciones    json=${datos}
    ${lista}=    GET On Session    admin    /plataforma/administradores
    ${id}=    Evaluate    [x['id'] for x in $lista.json()['invitaciones'] if x['email'] == '${otro}'][0]
    ${r}=    DELETE On Session    admin    /plataforma/administradores/invitaciones/${id}
    Status Should Be    200    ${r}
    ${r}=    Registrar Con Invitacion    ${otro}    ${i.json()['token']}
    Status Should Be    400    ${r}

36 - Un director o un consultor no ven ni gestionan administradores
    Iniciar Sesion Como Jefe    jefe
    ${vacio}=    Create Dictionary
    ${r}=    GET On Session    jefe    /plataforma/administradores    expected_status=any
    Status Should Be    403    ${r}
    ${r}=    POST On Session    jefe    /plataforma/administradores/invitaciones    json=${vacio}    expected_status=any
    Status Should Be    403    ${r}
    Iniciar Sesion Como Consultor    consultor
    ${r}=    GET On Session    consultor    /plataforma/administradores    expected_status=any
    Status Should Be    403    ${r}
    ${r}=    POST On Session    consultor    /plataforma/administradores/1/restablecer    json=${vacio}    expected_status=any
    Status Should Be    403    ${r}
    # Y el director no puede usar la invitacion de administrador para crear uno por la puerta de su empresa.
    ${r}=    GET On Session    jefe    /invitaciones
    ${roles}=    Evaluate    {i['rol'] for i in $r.json()['invitaciones']}
    Should Not Contain    ${roles}    admin

37 - Nadie se desactiva a si mismo ni se restablece su propio acceso
    Iniciar Sesion Como Administrador    admin
    ${yo}=    Id Del Administrador    admin    ${ADMIN_EMAIL}
    ${apagar}=    Create Dictionary    activo=${False}
    ${r}=    POST On Session    admin    /plataforma/administradores/${yo}/activo    json=${apagar}    expected_status=any
    Status Should Be    409    ${r}
    ${vacio}=    Create Dictionary
    ${r}=    POST On Session    admin    /plataforma/administradores/${yo}/restablecer    json=${vacio}    expected_status=any
    Status Should Be    409    ${r}
    # Sigue pudiendo entrar
    ${s}=    GET On Session    admin    /sesion
    Should Be Equal    ${s.json()['rol']}    admin

38 - Un administrador desactivado no entra, su sesion se cierra y al reactivarlo vuelve
    ${correo}=    Set Variable    admin.baja.${SUFIJO}@ejemplo.com
    ${token}=    Invitar Administrador    ${correo}
    Registrar Con Invitacion    ${correo}    ${token}
    Iniciar Sesion De Administrador    admin_baja    ${correo}    ${CLAVE}
    Iniciar Sesion Como Administrador    admin
    ${id}=    Id Del Administrador    admin    ${correo}
    ${apagar}=    Create Dictionary    activo=${False}
    ${r}=    POST On Session    admin    /plataforma/administradores/${id}/activo    json=${apagar}
    Status Should Be    200    ${r}
    # Su sesion abierta deja de valer
    ${s}=    GET On Session    admin_baja    /sesion    expected_status=any
    Status Should Be    401    ${s}
    # Y no puede volver a entrar
    Create Session    puerta    ${BASE_URL}    headers=${CABECERA}
    ${datos}=    Create Dictionary    email=${correo}    password=${CLAVE}
    ${r}=    POST On Session    puerta    /admin/login    json=${datos}    expected_status=any
    Status Should Be    403    ${r}
    Should Contain    ${r.json()['mensaje']}    desactivada
    ${encender}=    Create Dictionary    activo=${True}
    ${r}=    POST On Session    admin    /plataforma/administradores/${id}/activo    json=${encender}
    Status Should Be    200    ${r}
    Iniciar Sesion De Administrador    admin_baja2    ${correo}    ${CLAVE}

39 - El administrador restablece el acceso de otro: clave temporal, sesiones cerradas y la anterior deja de valer
    ${correo}=    Set Variable    admin.reset.${SUFIJO}@ejemplo.com
    ${token}=    Invitar Administrador    ${correo}
    Registrar Con Invitacion    ${correo}    ${token}
    Iniciar Sesion De Administrador    admin_reset    ${correo}    ${CLAVE}
    Iniciar Sesion Como Administrador    admin
    ${id}=    Id Del Administrador    admin    ${correo}
    ${vacio}=    Create Dictionary
    ${r}=    POST On Session    admin    /plataforma/administradores/${id}/restablecer    json=${vacio}
    ${temporal}=    Set Variable    ${r.json()['password_temporal']}
    ${s}=    GET On Session    admin_reset    /sesion    expected_status=any
    Status Should Be    401    ${s}
    Create Session    puerta    ${BASE_URL}    headers=${CABECERA}
    ${viejo}=    Create Dictionary    email=${correo}    password=${CLAVE}
    ${r}=    POST On Session    puerta    /admin/login    json=${viejo}    expected_status=any
    Status Should Be    401    ${r}
    ${nuevo}=    Create Dictionary    email=${correo}    password=${temporal}
    ${r}=    POST On Session    puerta    /admin/login    json=${nuevo}
    Should Be True    ${r.json()['debe_cambiar_clave']}
    # Solo funciona con administradores: un director de proyectos responde 404
    ${e}=    GET On Session    admin    /plataforma/empresas
    ${jefe}=    Evaluate    [x['jefe_id'] for x in $e.json()['empresas'] if x['jefe_email'] == 'jefe1@ejemplo.com'][0]
    ${r}=    POST On Session    admin    /plataforma/administradores/${jefe}/restablecer    json=${vacio}    expected_status=any
    Status Should Be    404    ${r}

40 - El alta, la invitacion y la baja de un administrador quedan en la actividad de la administracion
    Iniciar Sesion Como Administrador    admin
    ${r}=    GET On Session    admin    /plataforma/administradores
    ${tipos}=    Evaluate    {e['tipo'] for e in $r.json()['eventos']}
    Should Contain    ${tipos}    admin_invitacion_creada
    Should Contain    ${tipos}    admin_alta
    Should Contain    ${tipos}    admin_desactivado
    # Esa actividad no aparece en el registro de ninguna empresa
    Iniciar Sesion Como Jefe    jefe
    ${a}=    GET On Session    jefe    /organizacion/auditoria    expected_status=any
    ${tipos_empresa}=    Evaluate    {e['tipo'] for e in ($a.json().get('eventos') or [])}
    Should Not Contain    ${tipos_empresa}    admin_alta
    Should Not Contain    ${tipos_empresa}    admin_desactivado

*** Keywords ***
Id De Usuario
    [Documentation]    Id de un usuario, leido con la cuenta de administracion de la propia consulta del jefe.
    [Arguments]    ${correo}
    Iniciar Sesion Como Jefe    buscador_jefe
    ${r}=    GET On Session    buscador_jefe    /consultores
    FOR    ${c}    IN    @{r.json()['consultores']}
        IF    '${c['email']}' == '${correo}'
            RETURN    ${c['id']}
        END
    END
    Iniciar Sesion Como Jefe De La Otra Empresa    buscador_jefe2
    ${r}=    GET On Session    buscador_jefe2    /consultores
    FOR    ${c}    IN    @{r.json()['consultores']}
        IF    '${c['email']}' == '${correo}'
            RETURN    ${c['id']}
        END
    END
    Fail    No se encontro el usuario ${correo}

Invitar Como Jefe
    [Arguments]    ${correo}=${EMPTY}
    Iniciar Sesion Como Jefe    jefe_invita
    ${datos}=    Create Dictionary
    IF    '${correo}' != ''
        Set To Dictionary    ${datos}    email=${correo}
    END
    ${r}=    POST On Session    jefe_invita    /invitaciones    json=${datos}
    RETURN    ${r.json()['token']}

Registrar Con Invitacion
    [Arguments]    ${correo}    ${token}    ${clave}=${CLAVE}
    Create Session    anonimo    ${BASE_URL}
    ${datos}=    Create Dictionary    nombre=Persona Invitada    email=${correo}    password=${clave}
    ...    invitacion=${token}    acepto_terminos=${True}
    ${r}=    POST On Session    anonimo    /registro    json=${datos}    expected_status=any
    RETURN    ${r}

Crear Cuenta Nueva
    [Arguments]    ${correo}
    ${token}=    Invitar Como Jefe    ${correo}
    ${r}=    Registrar Con Invitacion    ${correo}    ${token}
    Status Should Be    201    ${r}

Invitar Administrador
    [Arguments]    ${correo}
    Iniciar Sesion Como Administrador    admin_invita
    ${datos}=    Create Dictionary    email=${correo}
    ${r}=    POST On Session    admin_invita    /plataforma/administradores/invitaciones    json=${datos}
    RETURN    ${r.json()['token']}

Iniciar Sesion De Administrador
    [Arguments]    ${alias}    ${correo}    ${clave}
    ${headers}=    Create Dictionary    X-Requested-With=fetch
    Create Session    ${alias}    ${BASE_URL}    headers=${headers}
    ${datos}=    Create Dictionary    email=${correo}    password=${clave}
    ${r}=    POST On Session    ${alias}    /admin/login    json=${datos}
    Status Should Be    200    ${r}
    Should Be True    ${r.json()['acceso']}

Id Del Administrador
    [Arguments]    ${alias}    ${correo}
    ${r}=    GET On Session    ${alias}    /plataforma/administradores
    ${id}=    Evaluate    [a['id'] for a in $r.json()['administradores'] if a['email'] == '${correo}'][0]
    RETURN    ${id}

Preparar La Suite
    ${s}=    Sufijo Unico
    Set Suite Variable    ${SUFIJO}    ${s}
    ${h}=    Create Dictionary    X-Requested-With=fetch
    Set Suite Variable    ${CABECERA}    ${h}
