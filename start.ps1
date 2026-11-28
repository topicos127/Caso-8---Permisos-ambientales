# .\start.ps1        usuarios y 3 expedientes de prueba
# .\start.ps1 -Demo  ademas 7 expedientes de demostracion (todos los estados y plazos)
param([switch]$Demo)

Write-Host "=== Iniciando Apto ===" -ForegroundColor Cyan

# 0. El .env tiene la contrasena de MySQL y la SECRET_KEY (no esta en GitHub).
if (-not (Test-Path ".env")) {
    Write-Host "Falta el archivo .env. Copie .env.example como .env y ponga los valores." -ForegroundColor Red
    exit 1
}
$envVars = @{}
Get-Content .env | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $partes = $_ -split '=', 2
    $envVars[$partes[0].Trim()] = $partes[1].Trim()
}
$dbPassword = $envVars['MYSQL_ROOT_PASSWORD']
$dbName = $envVars['MYSQL_DATABASE']
if (-not $dbPassword -or -not $dbName) {
    Write-Host "El .env debe tener MYSQL_ROOT_PASSWORD y MYSQL_DATABASE." -ForegroundColor Red
    exit 1
}
if (-not $envVars['SECRET_KEY']) {
    Write-Host "Aviso: el .env no tiene SECRET_KEY; las sesiones se pierden al reiniciar la app." -ForegroundColor Yellow
}

# 1. Levantar los contenedores y construir la imagen local
Write-Host "1. Construyendo y levantando contenedores..." -ForegroundColor Yellow
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "docker compose fallo. Abra Docker Desktop y reintente." -ForegroundColor Red; exit 1 }

# 2. Esperar a que MySQL responda (hasta 60 s)
Write-Host "2. Esperando a que MySQL este listo..." -ForegroundColor Yellow
$listo = $false
for ($i = 0; $i -lt 30; $i++) {
    docker exec mysql-permisos mysqladmin ping -h localhost -uroot "-p$dbPassword" --silent 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $listo = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $listo) { Write-Host "MySQL no respondio a tiempo." -ForegroundColor Red; exit 1 }

# 3. Aplicar el schema
Write-Host "3. Aplicando esquema de base de datos..." -ForegroundColor Yellow
Get-Content schema.sql | docker exec -i mysql-permisos mysql -uroot "-p$dbPassword" $dbName

# 4. Correr el seed
$semilla = if ($Demo) { "python seed_usuarios.py --demo" } else { "python seed_usuarios.py" }
Write-Host "4. Poblando la base de datos con datos de prueba..." -ForegroundColor Yellow
docker run --rm --network container:mysql-permisos -v ${PWD}:/app -w /app -e DB_HOST=127.0.0.1 -e "DB_PASSWORD=$dbPassword" -e "DB_NAME=$dbName" python:3.11-slim sh -c "pip install -q pymysql werkzeug && $semilla"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " ¡TODO LISTO!" -ForegroundColor Green
Write-Host " Abre http://localhost:5000 en tu navegador" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
