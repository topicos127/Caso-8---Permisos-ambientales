"""Un blueprint por area de la API."""
from . import (auth, colaboracion, cuenta, dashboard, documentos, equipo, expedientes, flujo, historial,
               invitaciones, organizaciones, plataforma, publico)

BLUEPRINTS = [publico.bp, auth.bp, cuenta.bp, invitaciones.bp, organizaciones.bp, plataforma.bp, dashboard.bp,
              expedientes.bp, documentos.bp, flujo.bp, historial.bp, equipo.bp, colaboracion.bp]
