"""Copia los archivos subidos del disco local (UPLOADS_DIR) al almacenamiento S3 configurado.

Úselo una sola vez al pasar de ALMACENAMIENTO=local a ALMACENAMIENTO=s3. Las claves son las
mismas rutas relativas de siempre, así que la base de datos no se toca. No borra nada del disco:
cuando compruebe que todo está en el bucket, apague el volumen cuando quiera.

    S3_ENDPOINT=... S3_BUCKET=... S3_ACCESS_KEY=... S3_SECRET_KEY=... UPLOADS_DIR=/app/uploads \\
        python scripts/migrar_archivos.py [--simular]

Cada archivo se vuelve a leer del bucket y se compara su huella SHA-256 con la del original.
Termina con código 1 si alguno no coincide.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from permisos import almacenamiento  # noqa: E402


def main(simular):
    origen = almacenamiento.Local()
    destino = almacenamiento.S3()
    copiados = omitidos = errores = 0
    for clave in sorted(origen.listar()):
        datos = origen.leer(clave)
        if datos is None:
            continue
        huella = hashlib.sha256(datos).hexdigest()
        try:
            ya = destino.leer(clave)
            if ya is not None and hashlib.sha256(ya).hexdigest() == huella:
                omitidos += 1
                print(f"= {clave} (ya está en el bucket)")
                continue
            if simular:
                print(f"+ {clave} ({len(datos)} bytes) [simulado]")
                continue
            destino.guardar(clave, datos)
            comprobado = destino.leer(clave)
            if comprobado is None or hashlib.sha256(comprobado).hexdigest() != huella:
                raise almacenamiento.AlmacenamientoError("la copia no coincide con el original")
            copiados += 1
            print(f"+ {clave} ({len(datos)} bytes)")
        except almacenamiento.AlmacenamientoError as e:
            errores += 1
            print(f"! {clave}: {e}")
    print(f"\nCopiados: {copiados}  ya estaban: {omitidos}  con error: {errores}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main("--simular" in sys.argv))
