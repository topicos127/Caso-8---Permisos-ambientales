"""Punto de entrada. El codigo de la API esta en el paquete permisos/.

gunicorn usa "app:app" (Dockerfile) y el CI corre "python app.py".
"""
from permisos import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
