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

En el despliegue también se usan `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`,
`DB_NAME` y, para Aiven, `DB_SSL_CA` (ruta al `ca.pem` que da Aiven, para verificar el
certificado de la base).

## Cómo bajar los cambios más recientes

1. `git pull`
2. `docker compose up -d --build`

## Credenciales de prueba

- **Consultor:** `consultor1@ejemplo.com` / `clave123`
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
