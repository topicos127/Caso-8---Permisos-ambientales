FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py schema.sql seed_usuarios.py ./
COPY permisos ./permisos
COPY scripts ./scripts
COPY static ./static

EXPOSE 5000

# gunicorn en vez del servidor de desarrollo de Flask. Un proceso con hilos:
# si SECRET_KEY falta, la clave temporal es la misma para todas las peticiones.
# Railway inyecta PORT; en local (docker compose) se usa 5000. Forma shell para
# que ${PORT} se expanda.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 8 --access-logfile - app:app"]
