#!/usr/bin/env python3
"""
Descarga y agrega las SALIDAS (ETH nativo, USDT y USDC) de un conjunto de
direcciones Ethereum, para localizar destinos de tipo "depósito de exchange".

Solo stdlib. Caché en ./datos/ : no vuelve a bajar lo que ya está.

Fuentes:
  - Routescan (API compatible etherscan, sin clave) para listados masivos.
  - Blockscout v2 (sin clave) para etiquetas públicas / si es contrato.

Uso:
  python3 descargar_y_agregar.py            # baja y agrega las direcciones base
  python3 descargar_y_agregar.py 0xabc...   # agrega direcciones extra al lote
  python3 descargar_y_agregar.py --clasificar  # clasifica los destinos relevantes
  python3 descargar_y_agregar.py --info 0xabc...  # etiqueta pública / contrato
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "datos")
os.makedirs(DATOS, exist_ok=True)

ROUTESCAN = ("https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api"
             "?module=account&action={accion}&address={addr}"
             "&startblock={sb}&endblock=99999999&sort=asc&page=1&offset={off}")
BLOCKSCOUT = "https://eth.blockscout.com/api/v2"

USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
DECIMALES = {USDT: 6, USDC: 6}

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
           "accept": "application/json"}

# --- direcciones conocidas de OrionX en Ethereum (monitor-web/direcciones.json)
CONOCIDAS = {
    "0x5528d82423d91da8e8fe8066fab15cc014ebd5e2": "OrionX hot wallet EVM",
    "0x0c827a9651630be28444d9f6ee21d997f2f3d272": "OrionX central de depositos",
    "0x551189f8531a88f2083077b70176a86915797a14": "OrionX recolector",
    "0xb72ae9366865e58f240ca42399df3fe8340fdd1e": "OrionX reenvio a Kraken",
    "0xafda8eba0ac933661f45b41a438840dc07df1761": "Orionx 1 (etiqueta publica)",
    "0x1028ffd61ba8ae40f65127cd7461c636f3075d4c": "OrionX operativa",
    "0x3892c819bb3995515fe7b7a092c860238a92279d": "atribuida: posible cold storage",
    "0x594cd3f2f43c9121c72398610ebc792953f7c592": "atribuida: posible cold storage 2",
    "0xc48485c211842437db9d4f0092024b7411cc1ec0": "atribuida: ingreso desde exchanges",
    "0x4b413bdf16ebc8bb5a05855608f1c71f25634c2a": "en evaluacion",
    "0xb6184e6403c517f27c39a95e0fb635929495d828": "en evaluacion",
    "0xbc1eff8eae5a523b02d5139491b114e080b2c1c5": "en evaluacion",
    "0xdf9390b86e365602d22eda5797670e49a9a69cee": "en evaluacion",
    "0xb964bd2a238c7e59125032a0585fa8c21ed2f529": "en evaluacion",
    "0x6bf3db49f7a014f463c03b0560353549c2788fa2": "en evaluacion",
    "0xdabb47be57b62caa8e17e4a3fff30468dd02f49f": "en evaluacion",
    "0x93afb95fa151e2d7848a007ce1c9d9b77eb4db2e": "en evaluacion",
    "0x36da0bfe6e0cb2d84ee84b1d832e5b1693b76448": "en evaluacion",
    "0x5a19332e8ee918bcab9d28ffa0be3ef304424b78": "en evaluacion",
    "0xb349689dc6db306a35af244a47c1a67374ae32b9": "en evaluacion",
}

# --- hot wallets publicas de Binance en Ethereum
BINANCE_HOT = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance 17",
    "0x9696f59e4d72e237be84ffd425dcad154bf96976": "Binance 18",
    "0x4976a4a02f38326660d17bf34b431dc6e2eb2327": "Binance 20",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance 8",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": "Binance 7",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance 28",
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance 1",
    "0xd551234ae421e3bcba99a0da6d736074f22192ff": "Binance 2",
    "0x564286362092d8e7936f0549571a803b203aaced": "Binance 3",
    "0x0681d8db095565fe8a346fa0277bffde9c0edbbf": "Binance 4",
    "0xfe9e8709d3215310075d67e3ed32a380ccf451c8": "Binance 5",
    "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67": "Binance 6",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance Hot Wallet 12",
}

# --- palabras clave para reconocer etiquetas de exchanges en Blockscout
EXCHANGES = ["binance", "kraken", "coinbase", "okx", "okex", "bitfinex",
             "bybit", "huobi", "kucoin", "gate", "crypto.com", "poloniex",
             "hitbtc", "bitstamp", "gemini", "celsius", "okcoin", "mexc",
             "bitget", "upbit", "bithumb"]


# ---------------------------------------------------------------- utilidades
def http_json(url, intentos=6):
    espera = 2.0
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                time.sleep(espera)
                espera = min(espera * 2, 30)
                continue
            if e.code == 404:
                return None
            time.sleep(espera)
            espera = min(espera * 2, 30)
        except Exception:
            time.sleep(espera)
            espera = min(espera * 2, 30)
    return None


def cache_path(addr, kind):
    return os.path.join(DATOS, "%s_%s.json" % (addr.lower(), kind))


def bajar_listado(addr, accion, contrato=None, off=2000):
    """Paginacion por cursor de bloque (evita el limite de paginacion profunda)."""
    addr = addr.lower()
    vistos = set()
    salida = []
    sb = 0
    while True:
        url = ROUTESCAN.format(accion=accion, addr=addr, sb=sb, off=off)
        if contrato:
            url += "&contractaddress=" + contrato
        d = http_json(url)
        if d is None:
            print("    ! fallo definitivo en %s %s sb=%d" % (addr, accion, sb))
            break
        res = d.get("result")
        if not isinstance(res, list):
            # "No transactions found" llega como string
            break
        nuevos = 0
        ultimo = sb
        for t in res:
            clave = (t.get("hash"), t.get("logIndex"), t.get("contractAddress"),
                     t.get("to"), t.get("value"))
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append(t)
            nuevos += 1
            ultimo = max(ultimo, int(t.get("blockNumber", 0)))
        if len(res) < off:
            break
        if ultimo <= sb and nuevos == 0:
            break
        sb = ultimo
        time.sleep(0.3)
    return salida


def obtener(addr, kind, forzar=False):
    p = cache_path(addr, kind)
    if os.path.exists(p) and not forzar:
        with open(p) as f:
            return json.load(f)
    if kind == "txlist":
        datos = bajar_listado(addr, "txlist")
    elif kind == "usdt":
        datos = bajar_listado(addr, "tokentx", USDT)
    elif kind == "usdc":
        datos = bajar_listado(addr, "tokentx", USDC)
    elif kind == "tokentx":
        datos = bajar_listado(addr, "tokentx")
    else:
        raise ValueError(kind)
    with open(p, "w") as f:
        json.dump(datos, f)
    return datos


def info_direccion(addr):
    """Etiqueta publica / si es contrato, desde Blockscout (con cache)."""
    p = cache_path(addr, "info")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    d = http_json(BLOCKSCOUT + "/addresses/" + addr) or {}
    out = {
        "hash": d.get("hash"),
        "name": d.get("name"),
        "is_contract": d.get("is_contract"),
        "public_tags": d.get("public_tags") or [],
        "metadata": (d.get("metadata") or {}).get("tags") if d.get("metadata") else None,
        "ens_domain_name": d.get("ens_domain_name"),
    }
    with open(p, "w") as f:
        json.dump(out, f)
    time.sleep(0.3)
    return out


def fecha(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- agregacion
def agregar(direcciones):
    """destinos[origen][destino] = sumas"""
    resultado = {}
    for addr in direcciones:
        addr = addr.lower()
        print("  descargando %s ..." % addr)
        tx = obtener(addr, "txlist")
        ut = obtener(addr, "usdt")
        uc = obtener(addr, "usdc")
        print("    txlist=%d usdt=%d usdc=%d" % (len(tx), len(ut), len(uc)))
        dst = {}

        def fila(to):
            return dst.setdefault(to, {
                "eth": 0.0, "usdt": 0.0, "usdc": 0.0,
                "n_eth": 0, "n_usdt": 0, "n_usdc": 0,
                "primera": None, "ultima": None,
                "hash_eth": None, "hash_usdt": None, "hash_usdc": None,
            })

        def marcar(r, ts):
            f = fecha(ts)
            if r["primera"] is None or f < r["primera"]:
                r["primera"] = f
            if r["ultima"] is None or f > r["ultima"]:
                r["ultima"] = f

        for t in tx:
            if (t.get("from") or "").lower() != addr:
                continue
            if t.get("isError") == "1":
                continue
            v = int(t.get("value") or 0)
            if v <= 0:
                continue
            to = (t.get("to") or "").lower()
            if not to:
                continue
            r = fila(to)
            r["eth"] += v / 1e18
            r["n_eth"] += 1
            if r["hash_eth"] is None:
                r["hash_eth"] = t["hash"]
            marcar(r, t["timeStamp"])

        for lista, clave, contrato in ((ut, "usdt", USDT), (uc, "usdc", USDC)):
            for t in lista:
                if (t.get("from") or "").lower() != addr:
                    continue
                if (t.get("contractAddress") or "").lower() != contrato:
                    continue
                to = (t.get("to") or "").lower()
                if not to:
                    continue
                v = int(t.get("value") or 0) / (10 ** DECIMALES[contrato])
                if v <= 0:
                    continue
                r = fila(to)
                r[clave] += v
                r["n_" + clave] += 1
                if r["hash_" + clave] is None:
                    r["hash_" + clave] = t["hash"]
                marcar(r, t["timeStamp"])

        resultado[addr] = dst
    return resultado


def entradas_grandes(addr, min_eth=10.0, min_tok=100000.0):
    """Entradas relevantes hacia addr (para buscar la cold wallet de origen)."""
    addr = addr.lower()
    tx = obtener(addr, "txlist")
    ut = obtener(addr, "usdt")
    uc = obtener(addr, "usdc")
    src = {}

    def fila(fr):
        return src.setdefault(fr, {"eth": 0.0, "usdt": 0.0, "usdc": 0.0,
                                   "n": 0, "primera": None, "ultima": None,
                                   "hash": None})

    def marcar(r, ts, h):
        f = fecha(ts)
        if r["primera"] is None or f < r["primera"]:
            r["primera"] = f
        if r["ultima"] is None or f > r["ultima"]:
            r["ultima"] = f
        if r["hash"] is None:
            r["hash"] = h
        r["n"] += 1

    for t in tx:
        if (t.get("to") or "").lower() != addr:
            continue
        if t.get("isError") == "1":
            continue
        v = int(t.get("value") or 0)
        if v <= 0:
            continue
        r = fila((t.get("from") or "").lower())
        r["eth"] += v / 1e18
        marcar(r, t["timeStamp"], t["hash"])
    for lista, clave, contrato in ((ut, "usdt", USDT), (uc, "usdc", USDC)):
        for t in lista:
            if (t.get("to") or "").lower() != addr:
                continue
            if (t.get("contractAddress") or "").lower() != contrato:
                continue
            v = int(t.get("value") or 0) / (10 ** DECIMALES[contrato])
            if v <= 0:
                continue
            r = fila((t.get("from") or "").lower())
            r[clave] += v
            marcar(r, t["timeStamp"], t["hash"])
    return {k: v for k, v in src.items()
            if v["eth"] >= min_eth or v["usdt"] >= min_tok or v["usdc"] >= min_tok}


# ------------------------------------------------------------- clasificacion
def siguiente_salto(addr, limite=200):
    """A donde manda sus fondos `addr` (primeras salidas). Devuelve conteo por destino."""
    p = cache_path(addr, "salidas")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    dest = {}
    url = (ROUTESCAN.format(accion="txlist", addr=addr, sb=0, off=limite))
    d = http_json(url) or {}
    for t in (d.get("result") or []) if isinstance(d.get("result"), list) else []:
        if (t.get("from") or "").lower() == addr and int(t.get("value") or 0) > 0:
            to = (t.get("to") or "").lower()
            dest[to] = dest.get(to, 0) + 1
    time.sleep(0.3)
    url = (ROUTESCAN.format(accion="tokentx", addr=addr, sb=0, off=limite))
    d = http_json(url) or {}
    for t in (d.get("result") or []) if isinstance(d.get("result"), list) else []:
        if (t.get("from") or "").lower() == addr:
            to = (t.get("to") or "").lower()
            dest[to] = dest.get(to, 0) + 1
    with open(p, "w") as f:
        json.dump(dest, f)
    time.sleep(0.3)
    return dest


_LABELS = None


def labels_publicas():
    """Snapshot publico de etiquetas de Etherscan (brianleect/etherscan-labels).

    Es una copia comunitaria, no la fuente oficial: sirve de indicio y siempre
    hay que confirmar la etiqueta en etherscan.io antes de citarla.
    """
    global _LABELS
    if _LABELS is None:
        p = os.path.join(DATOS, "etherscan_labels.json")
        if os.path.exists(p):
            with open(p) as f:
                _LABELS = json.load(f)
        else:
            u = ("https://raw.githubusercontent.com/brianleect/etherscan-labels"
                 "/main/data/etherscan/combined/combinedAllLabels.json")
            d = http_json(u) or {}
            _LABELS = {k.lower(): v for k, v in d.items()}
            with open(p, "w") as f:
                json.dump(_LABELS, f)
    return _LABELS


def etiqueta_publica(addr):
    v = labels_publicas().get(addr.lower())
    if not v:
        return ""
    nombre = v.get("name") or ""
    etiquetas = ",".join(v.get("labels") or [])
    return (nombre + (" [" + etiquetas + "]" if etiquetas else "")).strip()


def exchange_de(texto):
    t = (texto or "").lower()
    for ex in EXCHANGES:
        if ex in t:
            return ex
    return None


def clasificar(addr):
    addr = addr.lower()
    if addr in CONOCIDAS:
        return "orionx conocida", CONOCIDAS[addr]
    if addr in BINANCE_HOT:
        return "hot wallet Binance", BINANCE_HOT[addr]
    pub = etiqueta_publica(addr)
    ex = exchange_de(pub)
    if ex:
        return "hot wallet de exchange (etiqueta publica)", pub
    info = info_direccion(addr)
    if info.get("is_contract"):
        return "contrato", pub or (info.get("name") or "contrato sin nombre")
    # mirar el siguiente salto
    dest = siguiente_salto(addr)
    binance = {d: n for d, n in dest.items() if d in BINANCE_HOT}
    if binance:
        nombres = ", ".join(sorted(set(BINANCE_HOT[d] for d in binance)))
        return "deposito Binance", nombres
    otros = []
    for d in sorted(dest, key=lambda x: -dest[x])[:8]:
        p = etiqueta_publica(d)
        if exchange_de(p):
            otros.append(p)
    if otros:
        return "deposito de exchange", ", ".join(sorted(set(otros)))
    if not dest:
        return "sin salidas (acumula)", pub
    return "desconocido", pub


# --------------------------------------------------------------------- main
def analizar(min_eth=1.0, min_tok=10000.0):
    """Lee agregados.json, filtra destinos relevantes y los clasifica."""
    with open(os.path.join(AQUI, "agregados.json")) as f:
        agg = json.load(f)
    filas = []
    for origen, dsts in agg.items():
        for to, r in dsts.items():
            if r["eth"] >= min_eth or r["usdt"] >= min_tok or r["usdc"] >= min_tok:
                filas.append((origen, to, r))
    filas.sort(key=lambda x: -(x[2]["usdt"] + x[2]["usdc"] + x[2]["eth"] * 3000))
    print("destinos relevantes: %d" % len(filas))
    salida = []
    for origen, to, r in filas:
        tipo, etq = clasificar(to)
        salida.append({"origen": origen, "destino": to, "tipo": tipo,
                       "etiqueta": etq, **r})
        print("%s -> %s | ETH %.3f (%d) | USDT %.2f (%d) | USDC %.2f (%d) | %s..%s | %s | %s"
              % (origen[:10], to, r["eth"], r["n_eth"], r["usdt"], r["n_usdt"],
                 r["usdc"], r["n_usdc"], r["primera"], r["ultima"], tipo, etq))
    with open(os.path.join(AQUI, "destinos_clasificados.json"), "w") as f:
        json.dump(salida, f, indent=1)
    return salida


def main():
    args = sys.argv[1:]
    if args and args[0] == "--info":
        for a in args[1:]:
            print(a, json.dumps(info_direccion(a.lower()), ensure_ascii=False),
                  etiqueta_publica(a))
        return
    if args and args[0] == "--analizar":
        analizar()
        return
    extra = [a.lower() for a in args if a.startswith("0x")]
    direcciones = list(CONOCIDAS) + [a for a in extra if a not in CONOCIDAS]
    res = agregar(direcciones)
    out = os.path.join(AQUI, "agregados.json")
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    print("escrito", out)


if __name__ == "__main__":
    main()
