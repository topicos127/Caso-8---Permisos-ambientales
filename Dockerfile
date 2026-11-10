FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY static ./static

EXPOSE 5000

# gunicorn en vez del servidor de desarrollo de Flask. Un proceso con hilos:
# si SECRET_KEY falta, la clave temporal es la misma para todas las peticiones.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--access-logfile", "-", "app:app"]