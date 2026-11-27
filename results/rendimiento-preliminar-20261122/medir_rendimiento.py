# -*- coding: utf-8 -*-
"""Medicion preliminar de rendimiento: 20 usuarios simultaneos, solo lecturas."""
import json
import statistics
import sys
import threading
import time

import requests

BASE = "http://localhost:5000"
USUARIOS = 20
VUELTAS = 10
H = {"X-Requested-With": "fetch"}
tiempos = {"login": [], "listado": [], "detalle": [], "panel": []}
errores = []
lock = threading.Lock()
barrera = threading.Barrier(USUARIOS)


def medir(sesion, nombre, metodo, ruta, **kw):
    t0 = time.perf_counter()
    try:
        r = sesion.request(metodo, BASE + ruta, timeout=20, **kw)
        ok = r.status_code == 200
    except Exception as e:  # noqa: BLE001
        ok = False
        r = None
    dt = (time.perf_counter() - t0) * 1000
    with lock:
        if ok:
            tiempos[nombre].append(dt)
        else:
            errores.append((nombre, getattr(r, "status_code", "ERR")))
    return ok


def usuario(i):
    s = requests.Session()
    s.headers.update(H)
    barrera.wait()
    medir(s, "login", "POST", "/login", json={"email": "consultor1@ejemplo.com", "password": "Clave123"})
    for _ in range(VUELTAS):
        medir(s, "listado", "GET", "/expedientes")
        medir(s, "detalle", "GET", "/expedientes/SP-A8-2026-101")
        medir(s, "panel", "GET", "/dashboard")


# calentamiento (no cuenta)
w = requests.Session(); w.headers.update(H)
w.post(BASE + "/login", json={"email": "consultor1@ejemplo.com", "password": "Clave123"})
for ruta in ("/expedientes", "/expedientes/SP-A8-2026-101", "/dashboard"):
    w.get(BASE + ruta)

t0 = time.perf_counter()
hilos = [threading.Thread(target=usuario, args=(i,)) for i in range(USUARIOS)]
[h.start() for h in hilos]
[h.join() for h in hilos]
total = time.perf_counter() - t0


def p(vals, q):
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


res = {}
for k, v in tiempos.items():
    if v:
        res[k] = {"n": len(v), "media_ms": round(statistics.mean(v)), "p50_ms": round(p(v, .5)),
                  "p95_ms": round(p(v, .95)), "max_ms": round(max(v))}
todos = [x for v in tiempos.values() for x in v]
res["todas"] = {"n": len(todos), "media_ms": round(statistics.mean(todos)), "p95_ms": round(p(todos, .95)),
                "max_ms": round(max(todos))}
res["errores"] = len(errores)
res["duracion_s"] = round(total, 1)
res["peticiones_por_s"] = round(len(todos) / total, 1)
print(json.dumps(res, indent=1, ensure_ascii=False))
