"""Clasifica en paralelo los destinos relevantes de agregados.json.

Uso: python3 clasificar_todo.py [MIN_ETH] [MIN_TOKEN]
Resultado acumulativo en clasificacion.json (se puede reanudar).
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import descargar_y_agregar as D  # noqa: E402

# 0x36da0bfe... mueve miles de millones de USDT/USDC y no pertenece al grupo
# OrionX (ver informe): se excluye para que no domine la agregacion.
RUIDO = {"0x36da0bfe6e0cb2d84ee84b1d832e5b1693b76448"}
MIN_ETH = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
MIN_TOK = float(sys.argv[2]) if len(sys.argv) > 2 else 100000.0

agg = json.load(open(os.path.join(D.AQUI, "agregados.json")))
tot = {}
for o, ds in agg.items():
    if o in RUIDO:
        continue
    for t, r in ds.items():
        a = tot.setdefault(t, {"eth": 0, "usdt": 0, "usdc": 0, "n": 0,
                               "origenes": [], "primera": None, "ultima": None})
        a["eth"] += r["eth"]
        a["usdt"] += r["usdt"]
        a["usdc"] += r["usdc"]
        a["n"] += r["n_eth"] + r["n_usdt"] + r["n_usdc"]
        if o not in a["origenes"]:
            a["origenes"].append(o)
        if r["primera"] and (a["primera"] is None or r["primera"] < a["primera"]):
            a["primera"] = r["primera"]
        if r["ultima"] and (a["ultima"] is None or r["ultima"] > a["ultima"]):
            a["ultima"] = r["ultima"]

rel = [t for t, a in tot.items()
       if a["eth"] >= MIN_ETH or a["usdt"] >= MIN_TOK or a["usdc"] >= MIN_TOK]
rel.sort(key=lambda t: -(tot[t]["usdt"] + tot[t]["usdc"] + tot[t]["eth"] * 3000))
print("a clasificar:", len(rel), flush=True)

RUTA = os.path.join(D.AQUI, "clasificacion.json")
out = json.load(open(RUTA)) if os.path.exists(RUTA) else {}
lock = threading.Lock()
D.labels_publicas()


def trabajo(t):
    if t in out:
        return
    try:
        tipo, etq = D.clasificar(t)
    except Exception as e:  # una direccion no debe tumbar el lote
        tipo, etq = "error", str(e)
    with lock:
        out[t] = {"tipo": tipo, "etiqueta": etq, **tot[t]}
        print("%s | %s | %s" % (t, tipo, etq), flush=True)


with ThreadPoolExecutor(max_workers=5) as ex:
    list(ex.map(trabajo, rel))
json.dump(out, open(RUTA, "w"), indent=1)
print("listo", len(out), "clasificadas")
