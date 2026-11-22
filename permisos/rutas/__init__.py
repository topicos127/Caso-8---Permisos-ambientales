"""Un blueprint por area de la API."""
from . import auth, dashboard, documentos, equipo, expedientes, flujo, historial, publico

BLUEPRINTS = [publico.bp, auth.bp, dashboard.bp, expedientes.bp, documentos.bp, flujo.bp, historial.bp, equipo.bp]
