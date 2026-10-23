Write-Host "=== Iniciando Sistema de Permisos Ambientales ===" -ForegroundColor Cyan

# 1. Levantar los contenedores y construir la imagen local
Write-Host "1. Construyendo y levantando contenedores..." -ForegroundColor Yellow
docker compose up -d --build

# 2. Esperar a que MySQL esté listo (el healthcheck de docker-compose ayuda, pero por seguridad esperamos)
Write-Host "2. Esperando a que MySQL esté listo..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 3. Aplicar el schema
Write-Host "3. Aplicando esquema de base de datos..." -ForegroundColor Yellow
Get-Content schema.sql | docker exec -i mysql-permisos mysql -uroot -ppermisos123 permisos_ambientales

# 4. Correr el seed
Write-Host "4. Poblando la base de datos con datos de prueba..." -ForegroundColor Yellow
docker run --rm --network container:mysql-permisos -v ${PWD}:/app -w /app -e DB_HOST=127.0.0.1 python:3.11-slim sh -c "pip install pymysql werkzeug && python seed_usuarios.py"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " ¡TODO LISTO!" -ForegroundColor Green
Write-Host " Abre http://localhost:5000 en tu navegador" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green