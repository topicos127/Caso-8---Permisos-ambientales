# Sistema de Permisos Ambientales

Flask + MySQL, con frontend en HTML y JS. Se corre localmente con Docker Compose.

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
| `permisos/rutas/` | Un blueprint por área: `auth`, `dashboard`, `expedientes`, `documentos`, `flujo`, `historial`, `publico` |

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

En el despliegue también se usan `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`,
`DB_NAME` y, para Aiven, `DB_SSL_CA` (ruta al `ca.pem` que da Aiven, para verificar el
certificado de la base).

## Despliegue en Railway (Sprint 9; reemplaza a Render)

La app corre en Railway (plan Hobby) con el `Dockerfile` del repositorio. La base sigue
en Aiven, así que la migración solo mueve la aplicación. Railway ya no permite
`railway.json` en servicios nuevos (se deja de leer el 01/12/2026), por eso todo se
configura desde el panel del servicio:

1. **New Project → Deploy from GitHub repo**, rama `main`. Railway detecta el `Dockerfile`.
2. **Variables:** `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (los de Aiven),
   `SECRET_KEY` (texto largo y aleatorio), `SESSION_COOKIE_SECURE=true`, `JEFE_PASSWORD`
   (propia) y `UPLOADS_DIR=/app/uploads`. Si se usa `DB_SSL_CA`, ver la nota de abajo.
   Railway inyecta `PORT`; el `Dockerfile` lo usa solo.
3. **Settings → Deploy → Pre-Deploy Command:** `python scripts/init_db.py` (aplica
   `schema.sql`; es idempotente). La primera vez, agregar `SEED_DEMO=true` y quitarla
   después del primer despliegue.
4. **Settings → Deploy → Healthcheck Path:** `/health`.
5. **Volume** montado en `/app/uploads`, para que los documentos subidos sobrevivan a cada
   despliegue (en Render se perdían).
6. **Settings → Networking → Generate Domain** para obtener la URL pública.

Sobre `DB_SSL_CA`: sin esa variable, la conexión a Aiven va cifrada pero sin verificar
el certificado (la app lo avisa en el log). Para verificarlo, el `ca.pem` de Aiven tiene
que existir dentro del contenedor y `DB_SSL_CA` debe apuntar a su ruta.

Costo: el plan Hobby cuesta $5 al mes e incluye $5 de consumo. Una sola instancia de
gunicorn con la base fuera (Aiven) queda, en principio, dentro de ese consumo; conviene
revisar **Usage** la primera semana.

## Cómo bajar los cambios más recientes

1. `git pull`
2. `docker compose up -d --build`

## Credenciales de prueba

- **Jefe:** `jefe1@ejemplo.com` / `Jefe2026*` (lo crea la app al arrancar)
- **Consultor:** `consultor1@ejemplo.com` / `Clave123`
- **Consultor 2:** `consultor2@ejemplo.com` / `Clave2026`
- **Promotor:** `promotor1@ejemplo.com` / `Clave456`

Desde el Sprint 9 todas cumplen la política de contraseñas. Si tu base local se creó
antes, vuelve a correr el seed (`.\start.ps1` lo hace) para actualizarlas.

## Pruebas

Las pruebas unitarias no necesitan base de datos:

```
pip install -r requirements-test.txt
python -m unittest tests/test_semaforo.py tests/test_sprint9.py tests/test_ipe.py tests/test_ipe_api.py tests/test_documentos.py
```

Las de Robot Framework necesitan la app corriendo en `http://localhost:5000` con la base
recién sembrada (registran usuarios y crean expedientes; nunca correrlas contra Railway):

```
robot --outputdir resultados tests/login tests/sprint4 tests/sprint5 tests/sprint6 tests/sprint7 tests/sprint8 tests/sprint9
```

El pipeline de GitHub Actions corre todo en cada push a `main` y en cada Pull Request
hacia `main`.

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
