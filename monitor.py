#!/usr/bin/env python3
"""Monitor de billeteras vinculadas a OrionX. Solo librería estándar.
Lee direcciones.json (las que tienen monitorear=true), consulta exploradores públicos, compara con data.json anterior,
registra movimientos en historial.jsonl, reescribe data.json y avisa por Discord (env DISCORD_WEBHOOK) si hubo cambios.
Un movimiento cuenta si vale al menos UMBRAL_USD dólares (por defecto 1) al precio del momento, en cualquier moneda.
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.parse
from pathlib import Path
HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "orionx-monitor/1.0 (github pages; afectados)"}
RPC = {"ETH": ["https://ethereum-rpc.publicnode.com", "https://eth.drpc.org", "https://cloudflare-eth.com"],
       "BSC": ["https://bsc-dataseed.binance.org", "https://bsc-rpc.publicnode.com", "https://bsc.drpc.org"],
       "POLYGON": ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]}
USDT = {"ETH": "0xdac17f958d2ee523a2206206994597c13d831ec7", "BSC": "0x55d398326f99059ff775485246999027b3197955", "POLYGON": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f"}
USDT_DEC = {"ETH": 6, "BSC": 18, "POLYGON": 6}
NATIVO = {"BTC": "BTC", "XRP": "XRP", "TRX": "TRX", "LTC": "LTC", "ETH": "ETH", "BSC": "BNB", "POLYGON": "POL"}
COINGECKO = {"BTC": "bitcoin", "XRP": "ripple", "TRX": "tron", "LTC": "litecoin", "ETH": "ethereum", "BNB": "binancecoin", "POL": "polygon-ecosystem-token", "USDT": "tether"}
UMBRAL_USD = float(os.environ.get("UMBRAL_USD", "1"))   # un movimiento cuenta si vale al menos esto en dólares (≈1.000 CLP)
MIN_UNIDADES = {"BTC": 0.00001, "ETH": 0.0005, "BNB": 0.001, "LTC": 0.01, "XRP": 0.5, "TRX": 5, "POL": 5}   # respaldo si CoinGecko no responde
EXPLORER = {"BTC": "https://mempool.space/address/{a}", "XRP": "https://xrpscan.com/account/{a}", "TRX": "https://tronscan.org/#/address/{a}",
            "LTC": "https://litecoinspace.org/address/{a}", "ETH": "https://etherscan.io/address/{a}", "BSC": "https://bscscan.com/address/{a}", "POLYGON": "https://polygonscan.com/address/{a}"}

def krd(red, a): return (red, a.lower() if red in RPC else a)   # clave (red, direccion) con EVM en minúsculas

def cargar_wallets():
    """Lee direcciones.json (fuente única) y devuelve las que hay que vigilar
    (monitorear=true), con los campos que necesitan consultar() y data.json."""
    reg = json.loads((HERE / "direcciones.json").read_text(encoding="utf-8"))
    out = []
    for w in reg["direcciones"]:
        if not w.get("monitorear"): continue
        m = {k: w.get(k) for k in ("red", "direccion", "etiqueta", "tipo", "vigilar", "nota")}
        if w.get("origen") is not None: m["origen"] = w["origen"]
        out.append(m)
    return out

def get(url, data=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers={**UA, "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r: return json.load(r)
        except Exception as e:
            err = e
            if i < tries - 1: time.sleep(3 + 4 * i)   # sin espera tras el último intento
    raise RuntimeError(f"{url[:60]}: {err}")

def post(url, payload):
    """POST de aviso (Discord): un intento, no parsea la respuesta, nunca lanza,
    y no incluye la URL (lleva el token del webhook) en los mensajes de error."""
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={**UA, "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r: r.read()
    except Exception as e:
        print("aviso no enviado:", type(e).__name__)

def rpc(red, m, p):
    """prueba cada nodo público de la lista hasta que uno responda"""
    time.sleep(0.8); err = None
    for url in RPC[red]:
        try:
            r = get(url, {"jsonrpc": "2.0", "id": 1, "method": m, "params": p}, tries=2)
            if r.get("result") is not None: return r["result"]
            err = r.get("error")
        except Exception as e: err = e
    raise RuntimeError(f"RPC {red}: {err}")
def iso(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ts else None

def consultar(w):
    red, a = w["red"], w["direccion"]; out = {"saldo": None, "tokens": {}, "tx": None, "ultima": None}
    if red == "BTC":
        j = get(f"https://mempool.space/api/address/{a}"); c = j["chain_stats"]
        out["saldo"] = (c["funded_txo_sum"] - c["spent_txo_sum"]) / 1e8; out["tx"] = c["tx_count"]
        if j["mempool_stats"]["tx_count"]: out["tokens"]["pendiente"] = (j["mempool_stats"]["funded_txo_sum"] - j["mempool_stats"]["spent_txo_sum"]) / 1e8
        txs = get(f"https://mempool.space/api/address/{a}/txs")
        if txs: out["ultima"] = iso(txs[0]["status"].get("block_time")) or "en mempool"
    elif red == "XRP":
        j = get(f"https://api.xrpscan.com/api/v1/account/{a}"); out["saldo"] = float(j.get("xrpBalance") or 0); out["tx"] = j.get("Sequence")
        t = get(f"https://api.xrpscan.com/api/v1/account/{a}/transactions?limit=1").get("transactions") or []
        if t: out["ultima"] = t[0]["date"][:16].replace("T", " ") + " UTC"
    elif red == "TRX":
        j = get(f"https://apilist.tronscanapi.com/api/account?address={a}"); out["saldo"] = (j.get("balance") or 0) / 1e6; out["tx"] = j.get("totalTransactionCount")
        for tk in j.get("trc20token_balances", []):
            if tk.get("tokenAbbr") == "USDT": out["tokens"]["USDT"] = float(tk["balance"]) / 10 ** int(tk.get("tokenDecimal", 6))
        t = get(f"https://apilist.tronscanapi.com/api/transaction?address={a}&limit=1&start=0&sort=-timestamp").get("data") or []
        if t: out["ultima"] = iso(t[0]["timestamp"] / 1000)
    elif red == "LTC":
        j = get(f"https://api.blockcypher.com/v1/ltc/main/addrs/{a}?limit=1"); out["saldo"] = j["final_balance"] / 1e8; out["tx"] = j["n_tx"]
        if j.get("txrefs"): out["ultima"] = j["txrefs"][0].get("confirmed", "")[:16].replace("T", " ") + " UTC"
    elif red in RPC:
        out["saldo"] = int(rpc(red, "eth_getBalance", [a, "latest"]), 16) / 1e18; out["tx"] = int(rpc(red, "eth_getTransactionCount", [a, "latest"]), 16)
        bal = rpc(red, "eth_call", [{"to": USDT[red], "data": "0x70a08231" + a[2:].lower().rjust(64, "0")}, "latest"])
        out["tokens"]["USDT"] = int(bal, 16) / 10 ** USDT_DEC[red]
        out["ultima"] = f"{out['tx']} tx enviadas (nonce)"   # sin indexador no hay fecha; el nonce delata salidas
    return out

def precios(previos=None):
    """Devuelve (precios, antiguos). Si CoinGecko no responde y hay precios en el
    data.json anterior, los reutiliza y marca antiguos=True (no dejar todo en 0)."""
    ids = ",".join(sorted(set(COINGECKO.values())))
    try:
        j = get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=clp,usd")
        px = {sym: j.get(cg, {}) for sym, cg in COINGECKO.items()}
        if any(px.values()): return px, False
        raise RuntimeError("respuesta vacía")
    except Exception as e:
        print("precios:", e)
        if previos and any(previos.values()):
            print("precios: se reutilizan los del data.json anterior")
            return previos, True
        return {}, False

def discord(webhook, eventos, data):
    lineas = [f"**Monitor OrionX: {len(eventos)} movimiento(s) nuevo(s)** ({data['actualizado']})"]
    for e in eventos[:15]:
        lineas.append(f"• [{e['red']}] {e['etiqueta']}: {e['detalle']}  <{EXPLORER[e['red']].format(a=e['direccion'])}>")
    post(webhook, {"content": "\n".join(lineas)[:1900]})

def main():
    wallets = cargar_wallets()
    prev, prev_px = {}, {}
    if (HERE / "data.json").exists():
        d_ant = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
        for b in d_ant.get("billeteras", []): prev[krd(b["red"], b["direccion"])] = b
        prev_px = d_ant.get("precios") or {}
    px, precios_antiguos = precios(prev_px)
    ahora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    filas, eventos, errores = [], [], []
    for w in wallets:
        fila = {**w, "explorer": EXPLORER[w["red"]].format(a=w["direccion"]), "moneda": NATIVO[w["red"]]}
        try:
            fila.update(consultar(w))
        except Exception as e:
            errores.append(f"{w['red']} {w['direccion'][:12]}: {e}"); p = prev.get(krd(w["red"], w["direccion"]), {})
            fila.update({k: p.get(k) for k in ("saldo", "tokens", "tx", "ultima")}); fila["error"] = str(e)[:120]
        s = fila.get("saldo"); pr = px.get(fila["moneda"], {})
        fila["valor_clp"] = (s or 0) * pr.get("clp", 0) + sum(v * px.get(k, {}).get("clp", 0) for k, v in (fila.get("tokens") or {}).items() if k in px)
        fila["valor_usd"] = (s or 0) * pr.get("usd", 0) + sum(v * px.get(k, {}).get("usd", 0) for k, v in (fila.get("tokens") or {}).items() if k in px)
        p = prev.get(krd(w["red"], w["direccion"]))
        if p and not fila.get("error") and p.get("saldo") is not None and s is not None:
            d = (s or 0) - p["saldo"]; dt_usdt = (fila.get("tokens") or {}).get("USDT", 0) - (p.get("tokens") or {}).get("USDT", 0)
            # umbral en dólares (UMBRAL_USD, por defecto 1): vale igual para BTC que para XRP. Sin precio, se usa un mínimo en unidades.
            usd_d = abs(d) * pr["usd"] if pr.get("usd") else None
            usd_t = abs(dt_usdt) * px.get("USDT", {}).get("usd", 1.0)
            partes = []
            if (usd_d >= UMBRAL_USD) if usd_d is not None else (abs(d) >= MIN_UNIDADES.get(fila["moneda"], 0.001)):
                partes.append(f"{'+' if d > 0 else ''}{d:,.8f} {fila['moneda']} (≈US$ {usd_d:,.2f}; saldo {s:,.6f})" if usd_d is not None else f"{'+' if d > 0 else ''}{d:,.8f} {fila['moneda']} (saldo {s:,.6f})")
            if usd_t >= UMBRAL_USD: partes.append(f"{'+' if dt_usdt > 0 else ''}{dt_usdt:,.2f} USDT")
            # Un cambio solo en el contador de transacciones cuenta si también cambió la última actividad: los contadores de
            # Tronscan oscilan (137970 → 137968 → 137970 el 10-11 sep 2026 sin ninguna transacción nueva) y eso daba falsas alertas.
            if not partes and fila.get("tx") and p.get("tx") and fila["tx"] != p["tx"] and fila.get("ultima") and fila.get("ultima") != p.get("ultima"):
                partes.append(f"nuevas transacciones ({p['tx']} → {fila['tx']}) " + ("sin cambio de saldo" if not d and not dt_usdt else f"con cambio de saldo menor a US$ {UMBRAL_USD:g}"))
            if partes:
                ev = {"fecha": ahora, "red": w["red"], "direccion": w["direccion"], "etiqueta": w["etiqueta"], "detalle": "; ".join(partes), "saldo_antes": p["saldo"], "saldo_despues": s,
                      "valor_usd": round((usd_d or 0) + usd_t, 2)}
                eventos.append(ev)
        filas.append(fila); time.sleep(0.7)
    hist = HERE / "historial.jsonl"
    previos = [json.loads(l) for l in hist.read_text(encoding="utf-8").splitlines() if l.strip()] if hist.exists() else []
    clave = lambda e: (e.get("red"), e.get("direccion"), e.get("saldo_antes"), e.get("saldo_despues"), e.get("detalle"))
    ya = {clave(e) for e in previos[-400:]}   # no re-anotar el mismo movimiento si una corrida anterior no llegó a hacer push
    nuevos = [e for e in eventos if clave(e) not in ya]
    if nuevos:
        with open(hist, "a", encoding="utf-8") as fh:
            for e in nuevos: fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    todos = previos + nuevos
    data = {"actualizado": ahora, "precios": px, "precios_antiguos": precios_antiguos, "billeteras": filas, "eventos": todos[-200:][::-1], "errores": errores,
            "total_clp": sum(f["valor_clp"] for f in filas), "total_usd": sum(f["valor_usd"] for f in filas)}
    (HERE / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ahora}: {len(filas)} billeteras, {len(nuevos)} movimientos nuevos, {len(errores)} errores; total ≈ {data['total_clp']:,.0f} CLP" + (" (precios antiguos)" if precios_antiguos else ""))
    for e in nuevos: print("  MOV", e["red"], e["etiqueta"], e["detalle"])
    for e in errores: print("  ERR", e)
    wh = os.environ.get("DISCORD_WEBHOOK")
    if wh and nuevos: discord(wh, nuevos, data)
    if wh and errores and os.environ.get("AVISAR_ERRORES"): post(wh, {"content": "Monitor OrionX: errores de consulta\n" + "\n".join(errores)[:1800]})

if __name__ == "__main__":
    main()
