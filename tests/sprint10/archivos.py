"""Archivos de prueba para la suite del Sprint 10 (Robot Framework)."""
import io
import zipfile


def zip_con_nombres(*nombres):
    """Un ZIP en memoria con esos nombres de archivo, listo para el campo
    'archivo' de la subida (files= de RequestsLibrary)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for nombre in nombres:
            zf.writestr(nombre, b"datos de prueba del Sprint 10")
    return {"archivo": ("cartografia.zip", buffer.getvalue(), "application/zip")}
