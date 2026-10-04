@echo off
cd /d "%~dp0"

echo [1/3] Building Docker image...
docker build -t login-service:tilt .
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2/3] Loading image into Minikube...
minikube image load login-service:tilt
if %errorlevel% neq 0 exit /b %errorlevel%

echo [3/3] Restarting deployment...
kubectl rollout restart deployment/login-service
if %errorlevel% neq 0 exit /b %errorlevel%

echo Done.