"""Genera las tablas del informe a partir de agregados.json + clasif.log."""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RUIDO = {"0x36da0bfe6e0cb2d84ee84b1d832e5b1693b76448"}

agg = json.load(open(os.path.join(AQUI, "agregados.json")))

# tipo por destino, leido del log de clasificacion (o del json si ya existe)
tipos = {}
p = os.path.join(AQUI, "clasificacion.json")
if os.path.exists(p):
    for k, v in json.load(open(p)).items():
        tipos[k] = (v["tipo"], v["etiqueta"])
for linea in open(os.path.join(AQUI, "clasif.log")):
    m = re.match(r"\s*(?:\d+/\d+\s+)?(0x[0-9a-f]{40}) \| ([^|]+) \| (.*)", linea.rstrip())
    if m:
        tipos[m.group(1)] = (m.group(2).strip(), m.group(3).strip())

tot = {}
for o, ds in agg.items():
    if o in RUIDO:
        continue
    for t, r in ds.items():
        a = tot.setdefault(t, {"eth": 0.0, "usdt": 0.0, "usdc": 0.0, "n": 0,
                               "origenes": set(), "primera": None, "ultima": None})
        a["eth"] += r["eth"]; a["usdt"] += r["usdt"]; a["usdc"] += r["usdc"]
        a["n"] += r["n_eth"] + r["n_usdt"] + r["n_usdc"]
        a["origenes"].add(o)
        if r["primera"] and (a["primera"] is None or r["primera"] < a["primera"]):
            a["primera"] = r["primera"]
        if r["ultima"] and (a["ultima"] is None or r["ultima"] > a["ultima"]):
            a["ultima"] = r["ultima"]

modo = sys.argv[1] if len(sys.argv) > 1 else "top"

if modo == "resumen":
    from collections import Counter
    c = Counter()
    val = Counter()
    for t, a in tot.items():
        tipo = tipos.get(t, ("sin clasificar", ""))[0]
        c[tipo] += 1
        val[tipo + "|eth"] += a["eth"]
        val[tipo + "|usdt"] += a["usdt"]
        val[tipo + "|usdc"] += a["usdc"]
    for tipo, n in c.most_common():
        print("%-42s %5d destinos  ETH %10.1f  USDT %13.0f  USDC %13.0f"
              % (tipo, n, val[tipo + "|eth"], val[tipo + "|usdt"], val[tipo + "|usdc"]))
    print()
    print("clasificadas:", sum(1 for t in tot if t in tipos), "de", len(tot))
else:
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    orden = sorted(tot.items(),
                   key=lambda x: -(x[1]["usdt"] + x[1]["usdc"] + x[1]["eth"] * 3000))
    for t, a in orden[:n]:
        tipo, etq = tipos.get(t, ("sin clasificar", ""))
        print("%s | %9.2f | %12.0f | %12.0f | %4d | %s..%s | %s | %s | %s"
              % (t, a["eth"], a["usdt"], a["usdc"], a["n"], a["primera"], a["ultima"],
                 tipo, etq, ",".join(sorted(o[:10] for o in a["origenes"]))))
