# Tiltfile — Permisos Ambientales

k8s_yaml('k8s/uploads-pvc.yaml')
k8s_yaml('k8s/login-deployment.yaml')
k8s_yaml('k8s/login-service.yaml')

local_resource(
    'build-and-redeploy-login',
    'cmd /c build-login.bat',
    deps=['app.py', 'permisos/', 'static/', 'Dockerfile', 'requirements.txt'],
    trigger_mode=TRIGGER_MODE_AUTO,
    auto_init=True,
)