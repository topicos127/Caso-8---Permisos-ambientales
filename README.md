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

## Variables del `.env`

| Variable | Para qué |
|---|---|
| `MYSQL_ROOT_PASSWORD` | Contraseña de MySQL local |
| `MYSQL_DATABASE` | Nombre de la base (`permisos_ambientales`) |
| `SECRET_KEY` | Firma la cookie de sesión. Sin ella las sesiones se pierden al reiniciar |
| `SESSION_COOKIE_SECURE` | `true` solo en el despliegue con HTTPS |
| `JEFE_EMAIL` / `JEFE_PASSWORD` / `JEFE_NOMBRE` | Usuario jefe que se crea al arrancar si no existe (opcional; por defecto `jefe1@ejemplo.com` / `Jefe2026*`). En Render conviene poner una contraseña propia |

En el despliegue también se usan `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`,
`DB_NAME` y, para Aiven, `DB_SSL_CA` (ruta al `ca.pem` que da Aiven, para verificar el
certificado de la base).

## Cómo bajar los cambios más recientes

1. `git pull`
2. `docker compose up -d --build`

## Credenciales de prueba

- **Jefe:** `jefe1@ejemplo.com` / `Jefe2026*` (lo crea la app al arrancar)
- **Consultor:** `consultor1@ejemplo.com` / `clave123`
- **Consultor 2:** `consultor2@ejemplo.com` / `Clave2026`
- **Promotor:** `promotor1@ejemplo.com` / `clave456`

## Pruebas

Con la app corriendo en `http://localhost:5000`:

```
pip install -r requirements-test.txt
python -m unittest tests/test_semaforo.py
robot --outputdir resultados tests/sprint4 tests/sprint5 tests/sprint6 tests/sprint7
```

El pipeline de GitHub Actions corre lo mismo en cada push a `main`.

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

## Equipo de consultores y uso en el celular (Sprint 9)

- **HU-15.** El jefe gestiona su equipo en **Equipo** (menú lateral, solo lo ve el jefe):
  - **Alta:** crea consultores con la política de contraseñas del Sprint 6.
  - **Baja:** desactiva a un consultor. Ya no puede iniciar sesión (el login responde
    403 y su sesión abierta deja de valer), pero el usuario no se borra: sus
    expedientes y su historial se conservan. También se puede reactivar.
  - **Reasignar:** pasa los expedientes de un consultor desactivado a otro activo.
    Cada expediente reasignado queda en el historial como `reasignó`, a nombre del jefe.
  - `/registro` ya no crea consultores (responde 403): solo promotores.
  - La columna `usuarios.activo` la agrega la app al arrancar si no existe. Plan B:
    `sql/sprint9_manual.sql`.
- **HU-12.** En pantallas de 820 px o menos, el menú lateral se abre y se cierra con el
  botón **Menú** de la barra de arriba. En celular, las tablas (Mis expedientes,
  Historial y Equipo) se muestran como tarjetas, sin desplazamiento horizontal.

| Endpoint | Jefe | Consultor | Promotor | Sin sesión |
|---|---|---|---|---|
| `GET /consultores` | 200 | 403 | 403 | 401 |
| `POST /consultores` (`nombre`, `email`, `password`) | 201 (400 clave débil, 409 correo repetido) | 403 | 403 | 401 |
| `POST /consultores/<id>/desactivar` | 200 (409 si ya lo está) | 403 | 403 | 401 |
| `POST /consultores/<id>/activar` | 200 (409 si ya lo está) | 403 | 403 | 401 |
| `POST /consultores/<id>/reasignar` (`destino_id`) | 200 (409 si el consultor sigue activo) | 403 | 403 | 401 |
| `POST /login` de un consultor desactivado | — | 403 | — | — |
| `POST /registro` con `rol=consultor` | — | — | — | 403 |
