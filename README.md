# Apto

Apto: plataforma web para que las consultoras ambientales gestionen sus expedientes de estudios de impacto ambiental. Flask + MySQL, con frontend en HTML y JS. Se corre localmente con Docker Compose.

## Requisitos

- Docker Desktop (con Docker Compose).
- Git.

## Cómo iniciar el proyecto

1. Clonar el repositorio:
   `git clone https://github.com/NathalyB-Mcklean/Caso-8---Permisos-ambientales.git`
2. Copiar `.env.example` como `.env` y poner los valores. El equipo comparte el `.env`
   por el grupo; no se sube a GitHub.
3. Abrir una terminal en la carpeta del proyecto y ejecutar `.\start.ps1`.
   Si Windows dice que la ejecución de scripts está deshabilitada, correr antes:
   `Set-ExecutionPolicy -Scope Process Bypass`
4. Abrir `http://localhost:5000`.

## Estructura del código (Sprint 9)

`app.py` solo crea la app; la API vive en el paquete `permisos/`:

| Archivo | Qué tiene |
|---|---|
| `permisos/config.py` | Variables de entorno y constantes (categorías, plazos, roles) |
| `permisos/reglas.py` | Reglas puras: semáforo, verificación de documentos, política de contraseñas |
| `permisos/bd.py` | Conexión a MySQL, consultas compartidas y preparación de la base al arrancar |
| `permisos/seguridad.py` | Sesión, protección CSRF y permisos por rol |
| `permisos/errores.py` | Forma única de los errores y cabeceras de seguridad |
| `permisos/utiles.py` | Lectura de la petición, formato de salida y archivos subidos |
| `permisos/rutas/` | Un blueprint por área: `auth`, `cuenta`, `invitaciones`, `organizaciones`, `plataforma`, `colaboracion`, `dashboard`, `expedientes`, `documentos`, `flujo`, `historial`, `equipo`, `publico` |
| `permisos/totp.py` | Verificación en dos pasos (TOTP, RFC 6238) y códigos de recuperación |
| `permisos/almacenamiento.py` | Archivos en disco local o en un servicio compatible con S3 (firma SigV4 propia) |
| `permisos/respaldos.py` | Respaldos (base + archivos) con verificación, retención y restauración |
| `permisos/limitador.py` | Límite de intentos fallidos (login, recuperación, invitaciones) |
| `permisos/registro_errores.py` | Registro propio de errores con identificador de petición |

Los documentos del proyecto (plan de los Sprints 9 y 10, guía del PO) están en la rama
[`context`](../../tree/context/docs), separados del código.

## Variables del `.env`

| Variable | Para qué |
|---|---|
| `MYSQL_ROOT_PASSWORD` | Contraseña de MySQL local |
| `MYSQL_DATABASE` | Nombre de la base (`permisos_ambientales`) |
| `SECRET_KEY` | Firma la cookie de sesión. Sin ella las sesiones se pierden al reiniciar |
| `SESSION_COOKIE_SECURE` | `true` solo en el despliegue con HTTPS |
| `JEFE_EMAIL` / `JEFE_PASSWORD` / `JEFE_NOMBRE` | Usuario jefe que se crea al arrancar si no existe (opcional; por defecto `jefe1@ejemplo.com` / `Jefe2026*`). En Railway conviene poner una contraseña propia |
| `SEED_DEMO` | `true` solo para cargar los datos de prueba con `scripts/init_db.py` (una vez) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NOMBRE` | Primer administrador de la plataforma, que se crea al arrancar si no existe (por defecto `admin@ejemplo.com` / `Admin2026*`). **En el despliegue, definir una contraseña propia** y, si se quiere, `ADMIN_NOMBRE` con su nombre. Los demás administradores se invitan desde `/admin` → «Administradores» |
| `ADMIN_DOMINIOS` | Dominios de correo permitidos para los administradores de la plataforma, separados por coma (por ejemplo `apto.com.pa`). Vacío = cualquiera. Rige al crear el primero (`ADMIN_EMAIL`), al invitar, al registrarse y al entrar por `/admin`; en producción la app no arranca si `ADMIN_EMAIL` no cumple |
| `ADMIN_EXIGE_2FA` | Obliga a los administradores a activar los dos pasos al entrar. Por defecto `true` en producción (`SESSION_COOKIE_SECURE=true`) y `false` en local |
| `ORG_POR_DEFECTO` | Nombre de la empresa que recibe los datos anteriores a la separación por empresa (por defecto `Consultora Demo`) |
| `SESION_MINUTOS` | Minutos de inactividad antes de cerrar la sesión (120) |
| `INVITACION_HORAS` | Vigencia de un enlace de invitación (72) |
| `ALMACENAMIENTO` | `local` (volumen de Docker, por defecto) o `s3` |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_REGION` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Servicio compatible con S3 (Cloudflare R2, Backblaze B2, MinIO, AWS) cuando `ALMACENAMIENTO=s3` |
| `BACKUP_DIR` | Carpeta de los respaldos (`/app/respaldos`, un volumen aparte) |
| `RESPALDO_AUTOMATICO` / `RESPALDO_HORA` / `RESPALDOS_CONSERVAR` | Respaldo diario (hora de Panamá, 2 a. m. por defecto) y cuántos se conservan (14) |

En el despliegue también se usan `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` y
`PROXY_SALTOS` (ver la sección de Railway). Para una base externa con SSL (Aiven), `DB_SSL_CA`
apunta al `ca.pem` que entrega el proveedor.

## Despliegue en Railway

La aplicación y la base de datos corren en el mismo proyecto de Railway, con el `Dockerfile`
del repositorio. Railway ya no permite `railway.json` en servicios nuevos, así que todo se
configura desde el panel.

1. **Proyecto:** crear el proyecto con **Database → MySQL** (queda vacío: `init_db.py` crea las
   tablas) y, si se quiere guardar archivos y respaldos fuera del servidor, un **Bucket**.
   Después **GitHub Repository**, rama `main`; Railway detecta el `Dockerfile`.
2. **Variables de la app** (en el servicio de la app, pestaña *Variables*). La base se enlaza
   con variables de referencia al servicio `MySQL`, sin copiar contraseñas:

   | Variable | Valor |
   |---|---|
   | `DB_HOST` | `${{MySQL.MYSQLHOST}}` |
   | `DB_PORT` | `${{MySQL.MYSQLPORT}}` |
   | `DB_USER` | `${{MySQL.MYSQLUSER}}` |
   | `DB_PASSWORD` | `${{MySQL.MYSQLPASSWORD}}` |
   | `DB_NAME` | `${{MySQL.MYSQLDATABASE}}` |
   | `SECRET_KEY` | texto aleatorio de 32 caracteres o más |
   | `SESSION_COOKIE_SECURE` | `true` |
   | `PROXY_SALTOS` | `1` (la IP real del cliente llega en `X-Forwarded-For`; sin esto el límite de intentos y el registro de accesos usarían la IP del proxy) |
   | `ADMIN_EMAIL`, `ADMIN_PASSWORD` | el administrador de la plataforma, con contraseña propia |

   En producción la app crea **solo al primer administrador**; los demás (por ejemplo, un equipo de tres)
   se invitan desde `/admin` → «Administradores» con un enlace de un solo uso. Todos tienen los mismos
   permisos, nadie puede desactivarse a sí mismo y la plataforma nunca se queda sin un administrador activo.
   En producción cada administrador debe activar los **dos pasos en su primer ingreso**: tenga a mano
   una app de autenticación y guarde los códigos de recuperación que se muestran una vez.
   Si un administrador pierde el acceso, otro puede «Restablecer acceso» desde la misma pestaña.
   Las empresas y sus directores de proyectos
   se crean desde `/admin` (cada empresa genera un enlace de invitación para su director, que a su
   vez invita a su equipo). `JEFE_EMAIL`, `JEFE_PASSWORD` y `ORG_POR_DEFECTO` no se usan salvo que se
   fuerce `JEFE_INICIAL=true` (pensado para local y pruebas).

   Con `SESSION_COOKIE_SECURE=true` la app **se niega a arrancar** si `SECRET_KEY` es corta o
   si `ADMIN_PASSWORD` sigue con la contraseña de prueba.
   **No use `SEED_DEMO=true` en producción:** crearía las cuentas de prueba.
3. **Archivos y respaldos.** Un servicio de Railway admite un solo volumen, así que no se montan
   dos. Elegir una opción:
   - **Volumen:** montarlo en `/data` y definir `UPLOADS_DIR=/data/uploads` y
     `BACKUP_DIR=/data/respaldos`. Sencillo, pero archivos y respaldos viven en el mismo disco.
   - **Bucket (recomendado):** `ALMACENAMIENTO=s3` con `S3_ENDPOINT`, `S3_BUCKET`, `S3_REGION`,
     `S3_ACCESS_KEY` y `S3_SECRET_KEY`. Los documentos van al bucket y cada respaldo se copia
     allí también. Se puede combinar con el volumen en `/data` para los respaldos locales.
4. **Settings → Deploy → Pre-Deploy Command:** `python scripts/init_db.py` (aplica `schema.sql`;
   es idempotente). La app crea sola al administrador y al primer director al arrancar.
5. **Settings → Deploy → Healthcheck Path:** `/health`.
6. **Una sola réplica:** el límite de intentos y el respaldo diario viven en memoria del proceso.
7. **Settings → Networking → Generate Domain** para la URL pública. El administrador entra por
   `/admin`.

Después del primer despliegue: abrir `/estado`, entrar a `/admin`, crear la primera empresa y
usar su enlace de invitación para registrar al director de proyectos; con esa cuenta invitar al
equipo, subir un documento, y en «Respaldos» (administrador) hacer uno y pulsar «Verificar».

## Cómo bajar los cambios más recientes

1. `git pull`
2. `docker compose up -d --build`

## Credenciales de prueba

- **Jefe:** `jefe1@ejemplo.com` / `Jefe2026*` (lo crea la app al arrancar)
- **Consultor:** `consultor1@ejemplo.com` / `Clave123`
- **Consultor 2:** `consultor2@ejemplo.com` / `Clave2026`
- **Promotor:** `promotor1@ejemplo.com` / `Clave456`
- **Administrador de la plataforma:** `admin@ejemplo.com` / `Admin2026*` (lo crea la app al arrancar; no ve expedientes). **Entra por su propia URL: `http://localhost:5000/admin`** (el panel queda en `/admin/panel`). No se enlaza desde la página pública, `login.html` no acepta esta cuenta y `plataforma.html` ya no se sirve por su nombre.
- **Segunda empresa («Ambiental del Pacífico»):** jefe `jefe2@ejemplo.com` / `Jefe2026*` y consultor `consultor3@ejemplo.com` / `Clave2026`. Sirve para comprobar que una consultora no ve lo de otra.

Desde el Sprint 9 todas cumplen la política de contraseñas. Si tu base local se creó
antes, vuelve a correr el seed (`.\start.ps1` lo hace) para actualizarlas.

## Pruebas

Las pruebas unitarias no necesitan base de datos:

```
pip install -r requirements-test.txt
python -m unittest tests/test_semaforo.py tests/test_sprint9.py tests/test_ipe.py tests/test_ipe_api.py tests/test_documentos.py tests/test_equipo.py tests/test_sprint10.py tests/test_plataforma.py tests/test_sigv4_botocore.py
```

Las de Robot Framework necesitan la app corriendo en `http://localhost:5000` con la base
recién sembrada (registran usuarios y crean expedientes; nunca correrlas contra Railway):

```
robot --outputdir resultados tests/login tests/sprint4 tests/sprint5 tests/sprint6 tests/sprint7 tests/sprint8 tests/sprint9 tests/sprint10 tests/plataforma
```

El pipeline de GitHub Actions corre todo en cada push a `main` y en cada Pull Request
hacia `main`.

## Plataforma multiempresa

La plataforma ya no es de una sola consultora: cada **empresa** tiene sus usuarios y sus
expedientes, y ninguna ve lo de otra.

**Aislamiento.** La regla vive en un solo lugar, `permisos/seguridad.py` (`puede_ver`,
`exigir_gestion`, `exigir_jefe_de`, `filtro_de`, `condicion_empresa`); las rutas no comparan
empresas por su cuenta. Un expediente de otra empresa responde 404, como si no existiera. El
**administrador de la plataforma** (rol `admin`) crea las empresas, ve el estado del servicio y
administra los respaldos; no tiene acceso a ninguna pantalla de expedientes. Las bases anteriores
se migran solas al arrancar: sus usuarios y expedientes pasan a la empresa por defecto.

**Cuentas.** No hay registro abierto. El administrador crea una empresa y recibe un enlace de
invitación (de un solo uso, vence en 72 h, solo se guarda su SHA-256) para el jefe; el jefe invita
a su equipo igual desde «Equipo». Sin servicio de correo, la recuperación funciona así: cada
persona puede guardar **códigos de recuperación** (se muestran una sola vez) para fijar una
contraseña nueva en `recuperar.html`; si no los tiene, su jefe le genera una contraseña temporal
(al jefe, el administrador). Las contraseñas temporales y los códigos cierran las sesiones abiertas.

**Seguridad de la cuenta.** Verificación en dos pasos opcional (TOTP compatible con Google/Microsoft
Authenticator, Authy y 1Password; el secreto se guarda cifrado y cada código sirve una vez),
«cerrar sesión en los demás dispositivos», sesión que vence por inactividad (`SESION_MINUTOS`),
límite de intentos, aceptación de términos y privacidad, y cabeceras de seguridad con una política
de contenido sin scripts en línea. `Strict-Transport-Security` y la cookie `Secure` se activan con
`SESSION_COOKIE_SECURE=true` (solo con HTTPS).

**Archivos y respaldos.** Con `ALMACENAMIENTO=s3` los documentos van a un bucket (los mismos nombres
de siempre; para pasar los que ya hay en disco: `python scripts/migrar_archivos.py --simular` y luego
sin `--simular`). Los respaldos (`/plataforma` → «Respaldos») traen la base completa y los documentos en
un ZIP con su huella; se pueden verificar, descargar y restaurar (antes de restaurar se guarda uno del
estado actual). Con `RESPALDO_AUTOMATICO=true` se hace uno cada día. `/estado` (público) y
`estado.html` muestran si la base y los archivos responden; `/plataforma/errores` guarda los últimos
errores con un código que la persona afectada puede citar.

**Trabajo en equipo y reportes.** Responsable de cada expediente (lo cambia el jefe y queda en el
historial), comentarios internos (el promotor no los ve), vistas guardadas de filtros, búsqueda global
con `Ctrl+K`, exportación de la cartera a Excel y del historial a CSV (sin inyección de fórmulas), marca
propia por empresa (nombre, color y logo, que también salen en el PDF y en la consulta pública), guía
de primeros pasos en el panel y página de ayuda.

**Mi consultora (director de proyectos).** Siete pestañas: *Marca* (nombre, color y logo), *Datos de la empresa*
(razón social, RUC, dirección, contacto y pie; salen en el PDF y, el contacto, en la consulta pública),
*Políticas* (dos pasos obligatorios para el equipo, con la salvaguarda de que el director active primero los suyos;
cierre por inactividad propio de 15 a 120 minutos y aviso de vencimiento por defecto), *Uso*, *Mis datos* (ZIP con
cartera, historial, comentarios, equipo y todos los documentos con su índice SHA-256), *Accesos* (registro de inicios
de sesión y cambios, sin contenido de expedientes) y *Titularidad* (el titular invita a otros directores, asciende o
degrada roles y transfiere la cuenta). No hay feriados propios por empresa a propósito: los plazos en días hábiles
dependen de los feriados nacionales y cambiarlos distorsionaría el vencimiento legal. Planes y facturación quedan
para más adelante.

**Qué no cubre (a propósito).** No hay dominio propio ni avisos por correo. Los textos de términos y
privacidad son una base de trabajo y **deben revisarse con asesoría legal** antes de su uso comercial.
La firma S3 se verificó contra botocore (la implementación de referencia de AWS) y contra un servicio S3
emulado, no contra un proveedor real: pruebe con su bucket antes de depender de él. No se corrió un
escaneo de vulnerabilidades (OpenVAS) sobre esta versión.

## Correcciones del Sprint 9

- **Consulta pública (HU-09):** si el expediente no tiene acceso público, `/consulta/<codigo>`
  responde 403 y no entrega ningún dato (tampoco se puede armar el PDF). Si lo tiene,
  muestra además el consultor responsable y el estado público. Solo el jefe lo cambia:
  `POST /expedientes/<codigo>/acceso-publico` con `{"acceso_publico": true|false}`.
- **Cuentas de promotor:** el promotor ya no se registra solo (`/registro` solo crea
  consultores). El consultor del expediente, o el jefe, crea su acceso con
  `POST /expedientes/<codigo>/promotor/cuenta`, que devuelve una contraseña temporal
  una sola vez. Cualquier usuario la cambia en **Mi cuenta** (`POST /cuenta/contrasena`).
- **Login:** tras 5 intentos fallidos en un minuto para el mismo correo e IP, responde 429
  (`LOGIN_MAX_FALLOS` y `LOGIN_VENTANA_SEGUNDOS` lo ajustan).
- **Documentos (HU-01): solo PDF y ZIP, revisados y versionados.**
  - La extensión debe coincidir con el contenido. Un PDF se rechaza si trae JavaScript,
    acciones `/Launch`, archivos incrustados o multimedia activa (también dentro de
    objetos comprimidos o con nombres camuflados con `#xx`). Un ZIP se rechaza si trae
    ejecutables o scripts (por extensión o por su firma), rutas con `..`, enlaces
    simbólicos, contraseña, otros comprimidos o una compresión anómala; sus PDF se
    revisan igual. La lógica está en `permisos/inspeccion.py`.
  - **Un documento nunca se elimina:** `.../eliminar` responde 405. Cada subida es una
    versión nueva en `documento_versiones`, con su huella SHA-256 y un **código de
    trazabilidad** único: `<expediente>-D<documento>-V<versión>-<8 primeros del SHA-256>`.
    Las versiones anteriores se conservan y se descargan:
    `GET .../documentos/<carpeta>/versiones`, `GET .../versiones/<n>/descargar` y
    `GET /documentos/trazabilidad/<codigo>`. La tabla se crea sola al arrancar.
- **Historial (HU-14):** registra también `subió nueva versión`, `sometió`,
  `registró aprobación de MiAmbiente`, `cambió acceso público` y `creó cuenta del promotor`.
- **Estados (HU-07):** el promotor y el público ven *Pendiente de subsanación*,
  *En evaluación* o *Aprobado*; la consultora ve además *Aprobado internamente*.
- **ZIP (HU-06):** se descarga como `<codigo>_<AAAA-MM-DD>.zip`.
- Si falla la base al subir un documento, el archivo nuevo ya no queda en disco.
- **Contraseña temporal:** la cuenta que crea el consultor para el promotor queda marcada
  (`usuarios.debe_cambiar_clave`). Mientras no la cambie, toda la API responde 403 con
  `cambio_clave_obligatorio: true` salvo `/sesion` y `/cuenta/contrasena`, y las pantallas
  lo llevan a **Mi cuenta**. La columna se agrega sola al arrancar en bases anteriores.
- **Nuevo expediente:** casilla para permitir o no la consulta pública desde el inicio.

## Índice de Preparación del Expediente (HU-15, Sprint 9)

`IPE = 0,5 × D + 0,3 × P + 0,2 × V`, de 0 a 100, redondeado con las mitades hacia arriba:

| Componente | Cálculo |
|---|---|
| D · documentos | recibidos ÷ requeridos por la categoría × 100 |
| P · plazo | en plazo o resuelto 100 · por vencer 50 · vencido 0 (el semáforo de HU-07) |
| V · vigencia | 100 menos 25 por cada documento que vence en menos de 30 días (mínimo 0) |

Bandas: **Listo** desde 80, **En preparación** de 50 a 79, **En riesgo** por debajo de 50.
Un expediente nuevo sin documentos vale 50. Las reglas están en `permisos/reglas.py`
(`calcular_ipe`).

- `GET /expedientes/<codigo>` devuelve `ipe` con el valor, la banda, el desglose y las
  **próximas acciones** (documentos que faltan, plazo, vigencia y el siguiente paso del flujo).
- `GET /expedientes` trae `ipe` en cada fila; `?orden=ipe` ordena de menor a mayor (los
  resueltos al final). `GET /dashboard` trae `prioridades`: los 5 abiertos menos preparados.
- Solo la consultora (jefe y consultor) lo recibe; para el promotor `ipe` es `null` o no existe.

## Ver la aplicación con datos de demostración

`.\start.ps1 -Demo` (Docker Desktop) levanta todo y carga, además de los 3 expedientes de
prueba, 7 de demostración con fechas relativas a hoy: todos los estados, las tres
categorías, plazos vencido, por vencer y en plazo, un documento por vencer, uno sin acceso
público, aprobaciones e historial. Para un expediente en riesgo, abre el `SP-A8-2026-107`.
Sin Docker: `python seed_usuarios.py --demo` sobre una base MySQL ya creada con `schema.sql`
(variables `DB_HOST`, `DB_PASSWORD`, `DB_NAME`). El seed normal no incluye los de demostración
para no alterar las pruebas de Robot.

## Sesión y seguridad (Sprint 7)

- La sesión vive en una cookie firmada por el servidor (`SECRET_KEY`). La cabecera
  `X-Usuario-Email` ya no identifica al usuario.
- Los `POST` con sesión deben llevar la cabecera `X-Requested-With: fetch` (protección
  contra CSRF). `apiFetch` y `cabecerasApi()` de `static/js/api.js` la agregan solos.
- Las pruebas de Robot inician sesión con los keywords de `tests/recursos/sesion.resource`.

## Rol de jefe e historial (Sprint 8)

- **HU-13.** El jefe ve todos los expedientes (se asume una sola consultora), con su
  consultor y su plazo, y es el único que aprueba internamente. Un consultor que
  intenta aprobar recibe 403. El jefe no se puede registrar desde `/registro`.
- **HU-14.** La tabla `historial_expediente` registra `creó`, `subió documento` y
  `aprobó`, con el usuario de la sesión y la fecha y hora de Panamá, en la misma
  transacción que la acción. Se ve en **Historial** (menú lateral) y en el botón
  **Ver historial** del detalle. El jefe ve todo; el consultor, solo lo de sus
  expedientes; el promotor recibe 403. Es de solo lectura: cualquier `POST`, `PUT`,
  `PATCH` o `DELETE` sobre el historial responde 405.
- **Al arrancar,** la app crea la tabla del historial y el usuario jefe si no existen,
  y lo deja en el log (`Sprint 8: tabla historial_expediente y usuario jefe
  verificados.`). Si la base todavía no tiene las tablas, reintenta cada 30 s.
  Si en el log sale `AVISO: no se pudo preparar la base para el Sprint 8`, está el
  plan B en `sql/sprint8_manual.sql`.

| Endpoint | Jefe | Consultor | Promotor | Sin sesión |
|---|---|---|---|---|
| `GET /historial` y `GET /historial?codigo=X` | todo | solo los suyos | 403 | 401 |
| `GET /expedientes/<codigo>/historial` | 200 | 200 si es suyo, si no 403 | 403 | 401 |
| `POST /expedientes/<codigo>/aprobar` | 200 | 403 | 403 | 401 |

## Equipo de consultores (HU-16) y uso en el celular (HU-12), Sprint 9

> Numeración del Sprint 9: **HU-15** es el Índice de Preparación del Expediente (IPE), **HU-16** el equipo de consultores y **HU-12** el uso desde el celular.

- **Equipo de consultores.** El jefe gestiona su equipo en **Equipo** (menú lateral; solo lo
  ve el jefe):
  - **Alta:** nombre y correo. La app genera una contraseña temporal que se muestra una sola
    vez, igual que la cuenta del promotor; si el jefe manda una propia, debe cumplir la
    política del Sprint 6. En los dos casos el consultor la cambia en su primer ingreso.
  - **Baja:** desactiva a un consultor. Ya no puede iniciar sesión (el login responde 403 y
    su sesión abierta deja de valer), pero el usuario no se borra: sus expedientes y su
    historial se conservan. Se puede reactivar.
  - **Reasignar:** pasa los expedientes de un consultor desactivado a otro activo. Cada
    expediente reasignado queda en el historial como `reasignó`, a nombre del jefe.
  - La columna `usuarios.activo` la agrega la app al arrancar si no existe. Plan B:
    `sql/sprint9_manual.sql`.
- **Uso en el celular.** En pantallas de 820 px o menos, el menú lateral se abre y se cierra
  con el botón **Menú** de la barra de arriba (antes quedaba apilado encima de cada
  pantalla). En celular, Mis expedientes, Historial y Equipo se muestran como tarjetas, sin
  desplazamiento horizontal.

| Endpoint | Jefe | Consultor | Promotor | Sin sesión |
|---|---|---|---|---|
| `GET /consultores` | 200 | 403 | 403 | 401 |
| `POST /consultores` (`nombre`, `email`, `password` opcional) | 201 (400 clave débil, 409 correo repetido) | 403 | 403 | 401 |
| `POST /consultores/<id>/desactivar` | 200 (409 si ya lo está) | 403 | 403 | 401 |
| `POST /consultores/<id>/activar` | 200 (409 si ya lo está) | 403 | 403 | 401 |
| `POST /consultores/<id>/reasignar` (`destino_id`) | 200 (409 si el consultor sigue activo) | 403 | 403 | 401 |
| `POST /login` de un consultor desactivado | — | 403 | — | — |

