# Tiltfile — Permisos Ambientales

k8s_yaml('k8s/login-deployment.yaml')
k8s_yaml('k8s/login-service.yaml')

local_resource(
    'build-and-redeploy-login',
    'cmd /c build-login.bat',
    deps=['app.py', 'static/', 'Dockerfile', 'requirements.txt'],
    trigger_mode=TRIGGER_MODE_AUTO,
)