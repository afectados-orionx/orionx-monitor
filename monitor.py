#!/usr/bin/env python3
"""Monitor de billeteras vinculadas a OrionX. Solo librería estándar.

Lee direcciones.json (las que tienen monitorear=true), consulta exploradores y nodos públicos, compara con el data.json
anterior, registra movimientos en historial.jsonl, reescribe data.json y avisa por Discord (env DISCORD_WEBHOOK).

Qué vigila (desde el 15-sep-2026, versión 3):
  * Saldos del nativo y de los tokens de cada dirección. En las redes EVM (ETH, BSC, Polygon) los tokens NO son una
    lista fija: se descubren con los eventos Transfer que tocan la dirección y, en ETH y Polygon, con el inventario de
    Blockscout una vez al día. Un token solo cuenta si tiene precio conocido por contrato (CoinGecko o Blockscout):
    así los tokens imitadores y de spam no suman ni alertan. En Tron se cuentan todos los TRC-20 con precio en Tronscan.
  * Transferencias con hash y contraparte: eventos Transfer (EVM, vía eth_getLogs en nodos que aceptan filtrar solo
    por tema), transferencias TRC-20 y TRX (Tronscan), pagos XRP (xrpscan) y transacciones BTC/LTC (mempool.space y
    litecoinspace). Cada movimiento queda con `hash`, `contraparte` y su etiqueta si es conocida.
  * Señales previas al movimiento: aprobaciones ERC-20 (`Approval`) desde una dirección vigilada y cambios de permisos
    de cuenta en Tron.
  * Congelamiento: si Tether o Circle bloquean una dirección vigilada (USDT `isBlackListed`, USDC `isBlacklisted`),
    cambia el campo `congelada` y se registra el evento.
  * Direcciones descubiertas: destinos de salidas y, en BTC/LTC, entradas gastadas en conjunto (misma billetera) y
    posibles vueltos. Van a descubiertas.json, no a direcciones.json: una persona decide si se promueven.
    Si la salida es grande (UMBRAL_SEGUIR_USD) y el destino no es un exchange con etiqueta pública, además quedan
    en seguir=true: el monitor las consulta y avisa de sus movimientos desde la corrida siguiente, hasta MAX_SALTOS.

Regla de la primera corrida: cualquier cosa que el monitor ve por primera vez (token nuevo, cursor nuevo, dirección
nueva) fija su punto de partida sin generar movimientos; desde la segunda corrida todo cambio ≥ UMBRAL_USD se anota.
"""
import datetime as dt
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "orionx-monitor/3.0 (github pages; afectados)"}
VERSION = 3

# ----------------------------------------------------------------------------------------------------- redes y fuentes
RPC = {"ETH": ["https://ethereum-rpc.publicnode.com", "https://mainnet.gateway.tenderly.co", "https://rpc.mevblocker.io", "https://cloudflare-eth.com", "https://eth.drpc.org"],
       "BSC": ["https://bsc-dataseed.binance.org", "https://bsc-rpc.publicnode.com", "https://bsc.drpc.org"],
       "POLYGON": ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]}
# Nodos que aceptan eth_getLogs filtrando SOLO por temas (sin 'address'), con el rango máximo de bloques por llamada.
# Probados el 15-sep-2026: publicnode, drpc y blastapi exigen 'address'; 1rpc y nodies limitan a 50 bloques.
# (url, bloques por llamada, máximo de llamadas por corrida). Si no alcanza para llegar al último bloque, el cursor avanza
# hasta donde se llegó y la próxima corrida sigue desde ahí. BSC no tiene un nodo público cómodo: bloXroute admite 5.000
# bloques pero suele agotar el tiempo, y 1rpc solo 50 bloques por llamada (con eso el rock, que corre cada 10 min, alcanza).
RPC_LOGS = {"ETH": [("https://mainnet.gateway.tenderly.co", 20000, 30), ("https://rpc.mevblocker.io", 10000, 30)],
            "BSC": [("https://bsc.rpc.blxrbdn.com", 5000, 12), ("https://1rpc.io/bnb", 50, 60), ("https://bsc-mainnet.gateway.tatum.io", 100, 30)],
            "POLYGON": [("https://polygon.gateway.tenderly.co", 20000, 30)]}
MAX_BLOQUES_ATRAS = {"ETH": 150000, "BSC": 400000, "POLYGON": 600000}   # ≈3 semanas; más atrás se anota hueco
BLOCKSCOUT = {"ETH": "https://eth.blockscout.com", "POLYGON": "https://polygon.blockscout.com"}
CG_PLATAFORMA = {"ETH": "ethereum", "BSC": "binance-smart-chain", "POLYGON": "polygon-pos"}
TOPIC_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOPIC_APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
ILIMITADA = 2 ** 255            # una aprobación por más que esto se describe como "ilimitada"

# Stablecoins que se consultan siempre en cada red EVM: símbolo -> [(contrato, decimales), ...]. Si un símbolo tiene
# varios contratos (Polygon: USDC nativo y USDC.e puenteado) se suman bajo el mismo símbolo.
TOKENS = {"ETH": {"USDT": [("0xdac17f958d2ee523a2206206994597c13d831ec7", 6)], "USDC": [("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6)]},
          "BSC": {"USDT": [("0x55d398326f99059ff775485246999027b3197955", 18)], "USDC": [("0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d", 18)]},
          "POLYGON": {"USDT": [("0xc2132d05d31c914a87c6611c10748aeb04b58e8f", 6)],
                      "USDC": [("0x3c499c542cef5e3811e1192ce70d8cc03d5c3359", 6), ("0x2791bca1f2de4661ed88a30c99a7a9449aa84174", 6)]}}
# Semilla de los activos que OrionX vendía a sus clientes (revisados a mano el 15-sep-2026 contra Bscscan/Blockscout).
# Solo en billeteras tipo 'orionx'. Los demás tokens se descubren solos (ver descubrir_tokens / inventario_blockscout).
TOKENS_ORIONX = {"ETH": {"DAI": [("0x6b175474e89094c44da98b954eedeac495271d0f", 18)], "XAUT": [("0x68749665ff8d2d112fa859aa293f07a622782f38", 6)]},
                 "BSC": {"DOT": [("0x7083609fce4d1d8dc0c979aab8c869ea2c873402", 18)], "ADA": [("0x3ee2200efb3400fabb9aacf31297cbdd1d435d47", 18)],
                         "SOL": [("0x570a5d26f7765ecb712c0924e4de545b89fd43df", 18)], "XRP": [("0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe", 18)],
                         "LTC": [("0x4338665cbb7b2485a8855a139b75d5e34ab0db94", 18)], "TRX": [("0xce7de646e7208a4ef112cb6ed5038fa6cc6b12e3", 6)],
                         "ETH": [("0x2170ed0880ac9a755fd29b2688956bd959f933f8", 18)], "BTCB": [("0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c", 18)],
                         "DAI": [("0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3", 18)]},
                 "POLYGON": {"DAI": [("0x8f3cf7ad23cd3cadbd9735aff958023239c6a063", 18)]}}
# Contratos con lista negra (congelamiento del emisor). Selectores verificados con keccak y con direcciones realmente
# congeladas el 15-sep-2026: isBlackListed(address)=0xe47d6060 (Tether), isBlacklisted(address)=0xfe575a87 (Circle).
CONGELABLES = {"ETH": {"USDT": ("0xdac17f958d2ee523a2206206994597c13d831ec7", "0xe47d6060"),
                       "USDC": ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "0xfe575a87")},
               "POLYGON": {"USDC": ("0x3c499c542cef5e3811e1192ce70d8cc03d5c3359", "0xfe575a87")}}
TRON_USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
NATIVO = {"BTC": "BTC", "XRP": "XRP", "TRX": "TRX", "LTC": "LTC", "ETH": "ETH", "BSC": "BNB", "POLYGON": "POL"}
COINGECKO = {"BTC": "bitcoin", "XRP": "ripple", "TRX": "tron", "LTC": "litecoin", "ETH": "ethereum", "BNB": "binancecoin", "POL": "polygon-ecosystem-token", "USDT": "tether", "USDC": "usd-coin",
             "DAI": "dai", "XAUT": "tether-gold", "DOT": "polkadot", "ADA": "cardano", "SOL": "solana", "BTCB": "bitcoin"}
UMBRAL_USD = float(os.environ.get("UMBRAL_USD", "1"))   # un movimiento cuenta si vale al menos esto en dólares (≈1.000 CLP)
MIN_UNIDADES = {"BTC": 0.00001, "ETH": 0.0005, "BNB": 0.001, "LTC": 0.01, "XRP": 0.5, "TRX": 5, "POL": 5}   # respaldo si CoinGecko no responde
EXPLORER = {"BTC": "https://mempool.space/address/{a}", "XRP": "https://xrpscan.com/account/{a}", "TRX": "https://tronscan.org/#/address/{a}",
            "LTC": "https://litecoinspace.org/address/{a}", "ETH": "https://etherscan.io/address/{a}", "BSC": "https://bscscan.com/address/{a}", "POLYGON": "https://polygonscan.com/address/{a}"}
EXPLORER_TX = {"BTC": "https://mempool.space/tx/{h}", "XRP": "https://xrpscan.com/tx/{h}", "TRX": "https://tronscan.org/#/transaction/{h}",
               "LTC": "https://litecoinspace.org/tx/{h}", "ETH": "https://etherscan.io/tx/{h}", "BSC": "https://bscscan.com/tx/{h}", "POLYGON": "https://polygonscan.com/tx/{h}"}
UTXO_API = {"BTC": "https://mempool.space/api", "LTC": "https://litecoinspace.org/api"}
MAX_DESCUBIERTAS_NUEVAS = 25    # por corrida
MAX_DESCUBIERTAS = 200          # total en descubiertas.json (se conservan las 'misma billetera' y las que se siguen)
MAX_SEGUIDAS = 40               # descubiertas cuyo saldo se consulta en cada corrida
# Vigilancia automática de destinos: un destino de una salida grande se empieza a vigilar solo
# (seguir=true) sin esperar validación humana. Sigue siendo una propuesta: no entra a direcciones.json.
UMBRAL_SEGUIR_USD = float(os.environ.get("UMBRAL_SEGUIR_USD", "10000"))
MAX_SALTOS = 2                  # profundidad máxima que se vigila sola (a 3 saltos el dinero se dispersa)
MAX_AUTO_POR_ORIGEN = 3         # si una dirección reparte a más destinos grandes en una sola corrida es un
                                # agregador (mueve dinero de terceros): sus destinos se anotan pero no se vigilan solos
UMBRAL_AVISO_DESCUBIERTA_USD = float(os.environ.get("UMBRAL_AVISO_DESCUBIERTA_USD", "50000"))   # avisos de descubiertas
TIPOS_SEGUIR = ("orionx", "desvio", "atribuida", "querella", "puente", "descubierta")
PREFIJO_7702 = "0xef0100"       # EIP-7702: EOA con código delegado (billetera con gas patrocinado), no es contrato
PUBLICAS = set()                # claves (red, direccion) con etiqueta pública (exchange, puente, mezclador)
ES_EVM = lambda red: red in RPC   # noqa: E731


def krd(red, a): return (red, a.lower() if red in RPC else a)   # clave (red, direccion) con EVM en minúsculas
def iso(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ts else None
def ahora_txt(): return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
def corto(a): return a if len(a) <= 22 else a[:10] + "…" + a[-6:]
def corto_hash(h): return h[:10] + "…" if h and len(h) > 14 else (h or "")


# ---------------------------------------------------------------------------------------------------------- red/HTTP
def get(url, data=None, tries=3, timeout=40):
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers={**UA, "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
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


def rpc(red, m, p, urls=None):
    """prueba cada nodo público de la lista hasta que uno responda"""
    time.sleep(0.25); err = None
    for url in urls or RPC[red]:
        try:
            r = get(url, {"jsonrpc": "2.0", "id": 1, "method": m, "params": p}, tries=2)
            if r.get("result") is not None: return r["result"]
            err = r.get("error")
        except Exception as e: err = e
    raise RuntimeError(f"RPC {red}: {err}")


def eth_call(red, to, data): return rpc(red, "eth_call", [{"to": to, "data": data}, "latest"])


def rpc_lote(red, llamadas):
    """Varias llamadas en un solo POST (lista JSON-RPC). Devuelve la lista de resultados (None donde hubo error).
    Si el nodo no acepta lotes (drpc: máximo 3), se prueba el siguiente; si ninguno, una por una."""
    time.sleep(0.25); cuerpo = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(llamadas)]
    for url in RPC[red]:
        try:
            r = get(url, cuerpo, tries=1, timeout=60)
            if isinstance(r, list) and len(r) == len(cuerpo):
                por_id = {x.get("id"): x for x in r}
                return [por_id.get(i, {}).get("result") for i in range(len(cuerpo))]
        except Exception: pass
    out = []
    for m, p in llamadas:
        try: out.append(rpc(red, m, p))
        except Exception: out.append(None)
    return out
def pad(a): return a[2:].lower().rjust(64, "0")
def balance_of(red, contrato, a, dec): return int(eth_call(red, contrato, "0x70a08231" + pad(a)), 16) / 10 ** dec


def decodificar_texto(hexs):
    """string ABI (offset+len+bytes) o bytes32 (tokens antiguos tipo MKR)."""
    try:
        b = bytes.fromhex(hexs[2:]) if hexs and hexs != "0x" else b""
        if len(b) >= 64 and int.from_bytes(b[:32], "big") == 32:
            n = int.from_bytes(b[32:64], "big"); return b[64:64 + n].decode("utf-8", "replace").strip("\x00 ")
        return b[:32].decode("utf-8", "replace").strip("\x00 ")
    except Exception: return ""


# ---------------------------------------------------------------------------------------------- archivos de entrada
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


def cargar_etiquetas():
    """(red, direccion) -> nombre. Une direcciones.json (todas, también las descartadas y en evaluación),
    descubiertas.json y etiquetas_publicas.json (exchanges, puentes, mezcladores)."""
    et = {}
    try:
        pub = json.loads((HERE / "etiquetas_publicas.json").read_text(encoding="utf-8")).get("etiquetas", {})
        for red, d in pub.items():
            for a, n in d.items(): et[krd(red, a)] = f"{n} (etiqueta pública)"; PUBLICAS.add(krd(red, a))
    except Exception as e: print("etiquetas públicas:", e)
    try:
        for w in json.loads((HERE / "direcciones.json").read_text(encoding="utf-8"))["direcciones"]:
            nombre = w.get("etiqueta_publica") or w.get("etiqueta") or w.get("rol") or w.get("estado")
            if w.get("descartada"): nombre = f"descartada: {w.get('motivo') or nombre}"
            elif not w.get("monitorear"): nombre = f"{w.get('estado', 'relacionada')}: {nombre}"
            if nombre: et[krd(w["red"], w["direccion"])] = str(nombre)[:80]
    except Exception as e: print("etiquetas direcciones:", e)
    for d in cargar_descubiertas().get("direcciones", []):
        et.setdefault(krd(d["red"], d["direccion"]), f"descubierta {d.get('desde', '')}: {d.get('motivo', '')}"[:80])
    return et


def cargar_descubiertas():
    p = HERE / "descubiertas.json"
    if not p.exists(): return {"direcciones": []}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: print("descubiertas.json ilegible:", e); return {"direcciones": []}


# ------------------------------------------------------------------------------------------------------------ precios
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


def precios_por_contrato(red, contratos):
    """CoinGecko por contrato (de a pocos: en lote grande devuelve 400). contrato -> {'usd','clp'}"""
    out = {}
    contratos = [c for c in contratos]
    for i in range(0, len(contratos), 5):
        lote = contratos[i:i + 5]
        try:
            j = get(f"https://api.coingecko.com/api/v3/simple/token_price/{CG_PLATAFORMA[red]}?contract_addresses={','.join(lote)}&vs_currencies=usd,clp", tries=1)
            for c in lote:
                if j.get(c, {}).get("usd"): out[c] = {"usd": j[c]["usd"], "clp": j[c].get("clp") or 0}
        except Exception:
            for c in lote:   # uno por uno: un contrato desconocido no debe tumbar el lote
                try:
                    j = get(f"https://api.coingecko.com/api/v3/simple/token_price/{CG_PLATAFORMA[red]}?contract_addresses={c}&vs_currencies=usd,clp", tries=1)
                    if j.get(c, {}).get("usd"): out[c] = {"usd": j[c]["usd"], "clp": j[c].get("clp") or 0}
                except Exception: pass
                time.sleep(1.5)
        time.sleep(1.5)
    return out


def precio_blockscout(red, contrato):
    if red not in BLOCKSCOUT: return None
    try:
        t = get(f"{BLOCKSCOUT[red]}/api/v2/tokens/{contrato}", tries=1)
        return float(t["exchange_rate"]) if t.get("exchange_rate") else None
    except Exception: return None


class Tokens:
    """Metadatos y precio por contrato en las redes EVM, con caché en data.json ('tokens_conocidos').
    Un token 'con precio' es el único que cuenta para saldos, movimientos y alertas."""

    def __init__(self, cache, px):
        self.c = {red: dict(v) for red, v in (cache or {}).items()}
        self.px = px            # precios por símbolo (se completa con los de contrato)
        self.nuevos = {red: [] for red in RPC}

    def registrar(self, red, contrato, simbolo=None, decimales=None, precio_usd=None, fuente=None):
        contrato = contrato.lower(); t = self.c.setdefault(red, {}).setdefault(contrato, {})
        if simbolo: t["simbolo"] = simbolo[:20]
        if decimales is not None: t["decimales"] = decimales
        if precio_usd: t["precio_usd"], t["precio_fuente"], t["precio_fecha"] = precio_usd, fuente, ahora_txt()
        t.setdefault("visto", ahora_txt())
        return t

    def meta(self, red, contrato):
        """símbolo y decimales, consultando el contrato la primera vez"""
        contrato = contrato.lower(); t = self.c.get(red, {}).get(contrato)
        if t and t.get("simbolo") and t.get("decimales") is not None: return t
        for sym, lst in {**TOKENS[red], **TOKENS_ORIONX.get(red, {})}.items():
            for c, dec in lst:
                if c == contrato: return self.registrar(red, contrato, sym, dec)
        try:
            sym = decodificar_texto(eth_call(red, contrato, "0x95d89b41")) or contrato[:8]
            dec = int(eth_call(red, contrato, "0x313ce567"), 16)
        except Exception:
            sym, dec = contrato[:8], 18
        t = self.registrar(red, contrato, sym, dec); self.nuevos[red].append(contrato); return t

    def precio(self, red, contrato):
        t = self.c.get(red, {}).get(contrato.lower(), {})
        return t.get("precio_usd")

    def actualizar_precios(self, red, contratos):
        """Refresca el precio de esos contratos (CoinGecko; Blockscout de respaldo). Los de la tabla fija ya vienen por símbolo."""
        fijos = {c for lst in {**TOKENS[red], **TOKENS_ORIONX.get(red, {})}.values() for c, _ in lst}
        hace = lambda h: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=h)).strftime("%Y-%m-%d %H:%M UTC")   # noqa: E731
        def fresco(c):
            t = self.c.get(red, {}).get(c, {}); f = t.get("precio_fecha", "")
            return f > hace(0.9) if t.get("precio_usd") else (t.get("precio_fuente") == "sin precio" and f > hace(24))
        pedir = sorted({c.lower() for c in contratos} - fijos - {c for c in contratos if fresco(c.lower())})
        for c in fijos & {x.lower() for x in contratos}:
            t = self.meta(red, c); p = self.px.get(t.get("simbolo"), {})
            if p.get("usd"): self.registrar(red, c, precio_usd=p["usd"], fuente="coingecko")
            elif not t.get("precio_usd"): pedir.append(c) if c not in pedir else None
        if not pedir: return
        cg = precios_por_contrato(red, pedir)
        for c in pedir:
            if c in cg:
                self.registrar(red, c, precio_usd=cg[c]["usd"], fuente="coingecko")
                sym = self.meta(red, c)["simbolo"]
                if sym not in self.px or not self.px[sym].get("usd"): self.px[sym] = cg[c]
                continue
            t = self.c[red][c]
            # sin CoinGecko: Blockscout una vez al día; si tampoco, queda 'sin precio' y no cuenta
            if t.get("precio_fuente") == "blockscout" and t.get("precio_fecha", "") > (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d %H:%M UTC"): continue
            pb = precio_blockscout(red, c)
            if pb:
                self.registrar(red, c, precio_usd=pb, fuente="blockscout"); sym = self.meta(red, c)["simbolo"]
                clp = pb * (self.px.get("USDT", {}).get("clp", 0) / (self.px.get("USDT", {}).get("usd") or 1))
                if sym not in self.px or not self.px[sym].get("usd"): self.px[sym] = {"usd": pb, "clp": clp}
            else:
                t["precio_usd"] = None; t["precio_fuente"] = "sin precio"; t["precio_fecha"] = ahora_txt()


# ------------------------------------------------------------------------------------------- EVM: logs y descubrimiento
def get_logs(red, ini, fin, topics, url):
    r = get(url, {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{"fromBlock": hex(ini), "toBlock": hex(fin), "topics": topics}]}, tries=2, timeout=60)
    if "result" not in r: raise RuntimeError(str(r.get("error"))[:120])
    return r["result"]


def escanear_evm(red, direcciones, cursor, latest):
    """Eventos Transfer (entrada y salida) y Approval de las direcciones entre cursor+1 y latest.
    Devuelve (logs, nuevo_cursor, hueco). Primera corrida (cursor None): solo fija el cursor."""
    if not direcciones: return [], latest, None
    if cursor is None: return [], latest, None
    desde, hueco = cursor + 1, None
    if latest - desde > MAX_BLOQUES_ATRAS[red]:
        hueco = (desde, latest - MAX_BLOQUES_ATRAS[red]); desde = latest - MAX_BLOQUES_ATRAS[red]
    if desde > latest: return [], cursor, None
    temas = ["0x" + pad(a) for a in direcciones]
    filtros = [[TOPIC_TRANSFER, temas], [TOPIC_TRANSFER, None, temas], [TOPIC_APPROVAL, temas]]
    err, logs, vistos = None, [], set()
    for url, paso, max_llamadas in RPC_LOGS[red]:
        if paso <= 100: filtros = filtros[:2]   # en tramos chicos se ahorra la llamada de aprobaciones
        tramos = [(i, min(i + paso - 1, latest)) for i in range(desde, latest + 1, paso)][:max(1, max_llamadas // len(filtros))]
        hasta, fallo = desde - 1, None
        for ini, fin in tramos:
            try:
                for f in filtros:
                    for l in get_logs(red, ini, fin, f, url):
                        k = (l["transactionHash"], l.get("logIndex"))
                        if k not in vistos: vistos.add(k); logs.append(l)
                    time.sleep(0.3)
                hasta = fin
            except Exception as e:
                fallo = f"{url.split('//')[1][:24]}: {str(e)[:80]}"; break
        if hasta >= desde:   # algo se avanzó con este nodo: el cursor queda ahí (completo o parcial)
            if hasta < latest: print(f"logs {red}: avance parcial hasta {hasta} de {latest} ({url.split('//')[1][:24]})")
            return logs, hasta, hueco
        err = fallo or err
    raise RuntimeError(f"logs {red}: {err}")


def bloque_fecha(red, numero, cache):
    if numero in cache: return cache[numero]
    if len(cache) >= 30: return None   # en una corrida de recuperación no se piden cientos de bloques
    try:
        b = rpc(red, "eth_getBlockByNumber", [hex(numero), False]); cache[numero] = iso(int(b["timestamp"], 16))
    except Exception: cache[numero] = None
    return cache[numero]


def codigo_evm(red, a, cache):
    """Primeros bytes del código de la dirección ("0x" si es una cuenta normal), cacheados. None si
    el RPC falla. Se guarda recortado: basta para saber si hay código y si es una delegación 7702,
    y así el caché no se llena con los kilobytes de cada contrato."""
    a = a.lower()
    if a not in cache:
        try:
            c = rpc(red, "eth_getCode", [a, "latest"])
            cache[a] = c[:64] if isinstance(c, str) else c
        except Exception: cache[a] = None
    return cache[a]


def delegado_7702(red, a, cache):
    """Si la dirección es una EOA con delegación EIP-7702, la dirección a la que delega; si no, None."""
    c = codigo_evm(red, a, cache)
    return "0x" + c[len(PREFIJO_7702):][:40] if c and c.startswith(PREFIJO_7702) else None


def es_contrato(red, a, cache):
    """Contrato de verdad. Una EOA con delegación EIP-7702 tiene código pero sigue siendo una
    billetera de una persona (gas patrocinado): cuenta como cuenta normal, y por eso se descubre."""
    c = codigo_evm(red, a, cache)
    if c is None: return None
    if c.startswith(PREFIJO_7702): return False
    return c not in ("0x", "0x0", "")


def inventario_blockscout(red, a, tokens):
    """Tokens ERC-20 con precio y valor ≥ US$1 que Blockscout ve en la dirección. contrato -> (símbolo, dec, saldo, precio)."""
    out = {}
    j = get(f"{BLOCKSCOUT[red]}/api/v2/addresses/{a}/tokens?type=ERC-20", tries=2)
    for it in j.get("items", []):
        t = it.get("token") or {}; c = (t.get("address_hash") or t.get("address") or "").lower()
        rate, dec = t.get("exchange_rate"), t.get("decimals")
        if not c or not rate or dec is None: continue
        try:
            saldo = int(it.get("value") or 0) / 10 ** int(dec); rate = float(rate)
        except (ValueError, TypeError): continue
        if saldo * rate < UMBRAL_USD: continue
        tokens.registrar(red, c, t.get("symbol") or c[:8], int(dec), rate, "blockscout")
        out[c] = (t.get("symbol") or c[:8], int(dec), saldo, rate)
    return out


# ---------------------------------------------------------------------------------------------- consultas por dirección
def consultar(w, prev, ctx):
    """Saldo, tokens, contador, última actividad y eventos con hash de una dirección.
    prev: la fila de la corrida anterior (para cursores); ctx: precios, tokens, etiquetas, cachés."""
    red, a = w["red"], w["direccion"]
    out = {"saldo": None, "tokens": {}, "tx": None, "ultima": None, "cursor": dict((prev or {}).get("cursor") or {}), "eventos": [],
           "tokens_contratos": dict((prev or {}).get("tokens_contratos") or {})}
    if red in UTXO_API: consultar_utxo(w, out, prev, ctx)
    elif red == "XRP": consultar_xrp(w, out, prev, ctx)
    elif red == "TRX": consultar_tron(w, out, prev, ctx)
    elif red in RPC: consultar_evm(w, out, prev, ctx)
    return out


def clp_por_usd(px):
    u = px.get("USDT") or px.get("USDC") or {}
    return (u.get("clp") or 0) / (u.get("usd") or 1)


def simbolo_unico(ctx, sym, precio, contrato):
    """Si otro activo ya usa ese símbolo con un precio muy distinto (un 'BTC' de BSC que vale centavos), se distingue
    con el inicio del contrato para no valorarlo al precio del símbolo conocido."""
    p = (ctx["px"].get(sym) or {}).get("usd")
    if p and precio and abs(precio - p) / p > 0.2: return f"{sym}~{contrato[2:6]}"
    return sym


def etiqueta_de(ctx, red, a):
    return ctx["etiquetas"].get(krd(red, a))


def evento(w, ctx, tipo, moneda, cantidad, sentido, hash_, contraparte, fecha_cadena=None, detalle_extra="", valor_usd=None):
    """Evento con hash. `sentido`: 'salida', 'entrada' u otro texto (aprobación, permisos, congelamiento)."""
    red = w["red"]; et = etiqueta_de(ctx, red, contraparte) if contraparte else None
    signo = "-" if sentido == "salida" else "+" if sentido == "entrada" else ""
    flecha = "→" if sentido == "salida" else "←" if sentido == "entrada" else "·"
    cant = f"{signo}{cantidad:,.8f}".rstrip("0").rstrip(".") if isinstance(cantidad, (int, float)) else str(cantidad)
    partes = [f"{cant} {moneda}".strip()]
    if contraparte: partes.append(f"{flecha} {corto(contraparte)}" + (f" [{et}]" if et else ""))
    if detalle_extra: partes.append(detalle_extra)
    if hash_: partes.append(f"tx {corto_hash(hash_)}")
    if fecha_cadena: partes.append(f"({fecha_cadena})")
    return {"tipo_evento": tipo, "moneda": moneda, "cantidad": cantidad if isinstance(cantidad, (int, float)) else None, "sentido": sentido,
            "hash": hash_, "hash_url": EXPLORER_TX[red].format(h=hash_) if hash_ else None, "contraparte": contraparte, "contraparte_etiqueta": et,
            "fecha_cadena": fecha_cadena, "detalle": " ".join(partes), "valor_usd": valor_usd}


def salto_de(ctx, red, origen):
    """Distancia en saltos desde una dirección de direcciones.json. Las de la lista son 0; un destino
    suyo, 1; el destino de ese destino, 2. Sirve para no perseguir la dispersión hasta el infinito."""
    d = ctx["descubiertas_idx"].get(krd(red, origen or ""))
    return int(d.get("salto") or 1) if d else 0


def hay_cupo_para_seguir(ctx):
    return sum(1 for x in ctx["descubiertas"] if x.get("seguir")) < MAX_SEGUIDAS


def vigilar_sola(ctx, red, k, salto, valor_usd, w):
    """¿Se empieza a vigilar este destino sin esperar validación humana? Sí cuando el monto es
    grande, el origen es una dirección del caso, el destino no es un exchange con etiqueta pública
    (ahí lo que sirve es oficiar, no vigilar) y no se pasa de MAX_SALTOS ni del cupo."""
    return (valor_usd is not None and valor_usd >= UMBRAL_SEGUIR_USD
            and (w or {}).get("tipo") in TIPOS_SEGUIR
            and k not in PUBLICAS and salto <= MAX_SALTOS and hay_cupo_para_seguir(ctx))


def candidato(ctx, d, origen, valor_usd):
    """Anota un destino como candidato a vigilancia. La decisión se toma al final de la corrida,
    cuando ya se sabe a cuántos destinos repartió cada origen (ver decidir_vigilancia)."""
    ctx.setdefault("candidatos", {}).setdefault(krd(d["red"], origen or ""), []).append((d, valor_usd or 0))


def decidir_vigilancia(ctx):
    """Activa seguir=true en los candidatos de la corrida. Un origen que repartió a más de
    MAX_AUTO_POR_ORIGEN destinos grandes en una sola corrida es un agregador que mueve dinero de
    terceros (el 16-sep-2026 uno repartió 2,4 M USD a nueve cuentas en una hora): seguirlos a todos
    ahoga las alertas de las billeteras de OrionX, así que quedan anotados para revisión humana."""
    for korigen, lista in sorted(ctx.get("candidatos", {}).items()):
        if len(lista) > MAX_AUTO_POR_ORIGEN:
            reparto = ", ".join(f"{corto(d['direccion'])} US$ {v:,.0f}" for d, v in sorted(lista, key=lambda x: -x[1])[:6])
            for d, v in lista:
                d["seguir_motivo"] = (f"NO se vigila sola: el origen {corto(korigen[1])} repartió a {len(lista)} destinos grandes en una sola "
                                      f"corrida (se comporta como agregador de terceros). Revisar a mano. Reparto: {reparto}")
            org = ctx["descubiertas_idx"].get(korigen)
            if org: org["agregador"] = True
            print(f"  agregador: {korigen[1]} repartió a {len(lista)} destinos; no se vigilan solos")
            continue
        for d, v in sorted(lista, key=lambda x: -x[1]):
            if not hay_cupo_para_seguir(ctx):
                d["seguir_motivo"] = f"candidata (US$ {v:,.0f}) pero el cupo de {MAX_SEGUIDAS} direcciones seguidas está lleno"
                continue
            d["seguir"] = True
            d["seguir_motivo"] = f"recibió US$ {v:,.0f} de {corto(korigen[1])}, una dirección vigilada ({ahora_txt()})"
            ctx["seguidas_nuevas"] = ctx.get("seguidas_nuevas", 0) + 1


def descubrir(ctx, red, direccion, origen, motivo, hash_, fuerte, w=None, valor_usd=None):
    """Propone una dirección para descubiertas.json (no toca direcciones.json). Si la salida es
    grande, además la deja en seguir=true: el monitor consulta su saldo y avisa de sus movimientos."""
    if not direccion: return
    k = krd(red, direccion)
    if k in ctx["conocidas"] or k in ctx["vigiladas"]: return
    salto = salto_de(ctx, red, origen) + 1
    d = ctx["descubiertas_idx"].get(k)
    if d:
        d["veces"] = d.get("veces", 1) + 1; d["ultima"] = ahora_txt()
        d["valor_usd_max"] = round(max(d.get("valor_usd_max") or 0, valor_usd or 0), 2)
        if fuerte and not d.get("misma_billetera"): d["misma_billetera"], d["motivo"], d["seguir"] = True, motivo, True
        if not d.get("seguir") and vigilar_sola(ctx, red, k, d.get("salto", salto), valor_usd, w):
            candidato(ctx, d, origen, valor_usd)
        return
    if ctx["descubiertas_nuevas"] >= MAX_DESCUBIERTAS_NUEVAS: return
    if not fuerte and ctx.get("descubiertas_debiles", 0) >= MAX_DESCUBIERTAS_NUEVAS // 2: return   # los destinos no desplazan a las 'misma billetera'
    ctx["descubiertas_nuevas"] += 1
    if not fuerte: ctx["descubiertas_debiles"] = ctx.get("descubiertas_debiles", 0) + 1
    d = {"red": red, "direccion": direccion.lower() if red in RPC else direccion, "origen": origen, "motivo": motivo, "hash": hash_,
         "desde": ahora_txt(), "ultima": ahora_txt(), "veces": 1, "salto": salto, "valor_usd_max": round(valor_usd or 0, 2),
         "misma_billetera": bool(fuerte), "seguir": bool(fuerte),
         "explorer": EXPLORER[red].format(a=direccion)}
    if fuerte: ctx["seguidas_nuevas"] = ctx.get("seguidas_nuevas", 0) + 1
    ctx["descubiertas_idx"][k] = d; ctx["descubiertas"].append(d)
    if vigilar_sola(ctx, red, k, salto, valor_usd, w): candidato(ctx, d, origen, valor_usd)


# --- BTC / LTC ---------------------------------------------------------------------------------------------------------
def consultar_utxo(w, out, prev, ctx):
    red, a, api = w["red"], w["direccion"], UTXO_API[w["red"]]
    j = get(f"{api}/address/{a}"); c = j["chain_stats"]
    out["saldo"] = (c["funded_txo_sum"] - c["spent_txo_sum"]) / 1e8; out["tx"] = c["tx_count"]
    if j["mempool_stats"]["tx_count"]: out["tokens"]["pendiente"] = (j["mempool_stats"]["funded_txo_sum"] - j["mempool_stats"]["spent_txo_sum"]) / 1e8
    txs = get(f"{api}/address/{a}/txs")   # sin confirmar primero, luego las 25 confirmadas más recientes
    if txs: out["ultima"] = iso(txs[0]["status"].get("block_time")) or "en mempool"
    if "txids" not in out["cursor"]:   # primera corrida: se memorizan las transacciones existentes sin generar movimientos
        out["cursor"]["txids"] = [t["txid"] for t in txs][:100]; return
    vistos = list(out["cursor"].get("txids") or [])
    moneda = NATIVO[red]; px = ctx["px"].get(moneda, {}).get("usd")
    for t in reversed(txs):
        if t["txid"] in vistos: continue
        entradas = {v["prevout"]["scriptpubkey_address"] for v in t.get("vin", []) if v.get("prevout", {}).get("scriptpubkey_address")}
        salidas = [(o.get("scriptpubkey_address"), o["value"] / 1e8) for o in t.get("vout", []) if o.get("scriptpubkey_address")]
        fecha = iso(t["status"].get("block_time")) or "sin confirmar"
        if a in entradas:
            for dest, monto in salidas:
                if dest in entradas: continue       # vuelto a una entrada: no salió de la billetera
                vu = monto * px if px else None
                if vu is not None and vu < UMBRAL_USD: continue
                out["eventos"].append(evento(w, ctx, "transferencia", moneda, monto, "salida", t["txid"], dest, fecha, valor_usd=vu))
                descubrir(ctx, red, dest, a, "destino de una salida", t["txid"], fuerte=False, w=w, valor_usd=vu)
            for otra in entradas - {a}:
                descubrir(ctx, red, otra, a, "gastó en la misma transacción que una dirección vigilada (misma billetera)", t["txid"], fuerte=True)
            if len(salidas) == 2:   # heurística de vuelto: 2 salidas, la que no es conocida y comparte formato con la vigilada
                for dest, _ in salidas:
                    if dest not in entradas and dest[:3] == a[:3] and not etiqueta_de(ctx, red, dest):
                        descubrir(ctx, red, dest, a, "posible vuelto de una salida (2 salidas, mismo formato)", t["txid"], fuerte=True)
        else:
            recibido = sum(m for d_, m in salidas if d_ == a); vu = recibido * px if px else None
            if vu is None or vu >= UMBRAL_USD:
                out["eventos"].append(evento(w, ctx, "transferencia", moneda, recibido, "entrada", t["txid"], sorted(entradas)[0] if entradas else None, fecha, valor_usd=vu))
        vistos.append(t["txid"])
    out["cursor"]["txids"] = vistos[-150:]


# --- XRP -----------------------------------------------------------------------------------------------------------------
def consultar_xrp(w, out, prev, ctx):
    a = w["direccion"]
    j = get(f"https://api.xrpscan.com/api/v1/account/{a}"); out["saldo"] = float(j.get("xrpBalance") or 0); out["tx"] = j.get("Sequence")
    txs = get(f"https://api.xrpscan.com/api/v1/account/{a}/transactions?limit=25").get("transactions") or []
    if txs: out["ultima"] = txs[0]["date"][:16].replace("T", " ") + " UTC"
    ledger = out["cursor"].get("ledger")
    if ledger is None:
        out["cursor"]["ledger"] = max([t.get("ledger_index", 0) for t in txs] or [0]); return
    px = ctx["px"].get("XRP", {}).get("usd"); nuevo = ledger
    for t in reversed(txs):
        li = t.get("ledger_index", 0)
        if li <= ledger: continue
        nuevo = max(nuevo, li)
        if t.get("TransactionType") != "Payment" or t.get("meta", {}).get("TransactionResult") != "tesSUCCESS": continue
        amt = t.get("meta", {}).get("delivered_amount", t.get("Amount"))
        if isinstance(amt, dict):
            if amt.get("currency") != "XRP": continue
            monto = float(amt.get("value") or 0)
        else:
            monto = float(amt or 0) / 1e6
        vu = monto * px if px else None
        if vu is not None and vu < UMBRAL_USD: continue
        fecha = (t.get("date") or "")[:16].replace("T", " ") + " UTC"
        if t.get("Account") == a:
            out["eventos"].append(evento(w, ctx, "transferencia", "XRP", monto, "salida", t.get("hash"), t.get("Destination"), fecha, valor_usd=vu,
                                         detalle_extra=f"tag {t['DestinationTag']}" if t.get("DestinationTag") is not None else ""))
            descubrir(ctx, "XRP", t.get("Destination"), a, "destino de una salida", t.get("hash"), fuerte=False, w=w, valor_usd=vu)
        elif t.get("Destination") == a:
            out["eventos"].append(evento(w, ctx, "transferencia", "XRP", monto, "entrada", t.get("hash"), t.get("Account"), fecha, valor_usd=vu))
    out["cursor"]["ledger"] = nuevo


# --- Tron ------------------------------------------------------------------------------------------------------------------
def consultar_tron(w, out, prev, ctx):
    a = w["direccion"]
    j = get(f"https://apilist.tronscanapi.com/api/account?address={a}"); out["saldo"] = (j.get("balance") or 0) / 1e6; out["tx"] = j.get("totalTransactionCount")
    trx_usd = ctx["px"].get("TRX", {}).get("usd") or 0
    for tk in j.get("trc20token_balances", []):
        try:
            monto = float(tk["balance"]) / 10 ** int(tk.get("tokenDecimal", 6)); p_trx = float(tk.get("tokenPriceInTrx") or 0)
        except (ValueError, TypeError): continue
        sym = tk.get("tokenAbbr") or tk.get("tokenId", "")[:8]
        if tk.get("tokenId") == TRON_USDT: sym = "USDT"
        if p_trx <= 0 or monto * p_trx * trx_usd < UMBRAL_USD:
            if monto > 0: out.setdefault("tokens_sin_precio", []).append(sym)
            continue
        if sym in ("USDT", "USDC") and not tk.get("vip"): continue   # imitación de una stablecoin con precio propio
        out["tokens"][sym] = out["tokens"].get(sym, 0) + monto
        if sym not in ctx["px"] or not ctx["px"][sym].get("usd"):
            ctx["px"][sym] = {"usd": p_trx * trx_usd, "clp": p_trx * (ctx["px"].get("TRX", {}).get("clp") or 0)}
    t = get(f"https://apilist.tronscanapi.com/api/transaction?address={a}&limit=1&start=0&sort=-timestamp").get("data") or []
    if t: out["ultima"] = iso(t[0]["timestamp"] / 1000)
    # permisos de la cuenta (cambio = cambio de control de las llaves)
    perm = json.dumps({"owner": j.get("ownerPermission"), "active": j.get("activePermissions")}, sort_keys=True)
    out["permisos"] = hashlib.sha1(perm.encode()).hexdigest()[:12]
    if prev and prev.get("permisos") and prev["permisos"] != out["permisos"]:
        out["eventos"].append(evento(w, ctx, "permisos", "", "cambio de permisos de la cuenta (owner/active)", "permisos", None, None, ahora_txt()))
    # congelamiento en USDT TRC-20
    try:
        r = get("https://api.trongrid.io/wallet/triggerconstantcontract", {"owner_address": a, "contract_address": TRON_USDT, "function_selector": "isBlackListed(address)",
                                                                           "parameter": pad_tron(a), "visible": True}, tries=1)
        cr = (r.get("constant_result") or [""])[0]
        if cr: out["congelada"] = {"USDT": int(cr, 16) == 1}
    except Exception as e: print("tron blacklist:", str(e)[:60])
    # transferencias con hash desde el cursor
    ts = out["cursor"].get("ts")
    if ts is None:
        out["cursor"]["ts"] = int(time.time() * 1000); return
    nuevo = ts
    try:
        k = get(f"https://apilist.tronscanapi.com/api/token_trc20/transfers?relatedAddress={a}&limit=50&start=0&start_timestamp={ts + 1}")
        for x in reversed(k.get("token_transfers") or []):
            info = x.get("tokenInfo") or {}; sym = info.get("tokenAbbr") or "?"
            if x.get("contract_address") == TRON_USDT: sym = "USDT"
            elif not info.get("vip"): continue   # solo tokens verificados por Tronscan; el resto es spam de imitadores
            monto = float(x.get("quant") or 0) / 10 ** int(info.get("tokenDecimal", 6)); vu = monto * (ctx["px"].get(sym, {}).get("usd") or (1.0 if sym in ("USDT", "USDC") else 0))
            nuevo = max(nuevo, int(x.get("block_ts") or 0))
            if vu < UMBRAL_USD: continue
            fecha = iso(x["block_ts"] / 1000)
            if x.get("from_address") == a:
                out["eventos"].append(evento(w, ctx, "transferencia", sym, monto, "salida", x.get("transaction_id"), x.get("to_address"), fecha, valor_usd=vu))
                descubrir(ctx, "TRX", x.get("to_address"), a, "destino de una salida", x.get("transaction_id"), fuerte=False, w=w, valor_usd=vu)
            elif x.get("to_address") == a:
                out["eventos"].append(evento(w, ctx, "transferencia", sym, monto, "entrada", x.get("transaction_id"), x.get("from_address"), fecha, valor_usd=vu))
        k = get(f"https://apilist.tronscanapi.com/api/transaction?address={a}&limit=50&start=0&sort=-timestamp&start_timestamp={ts + 1}")
        for x in reversed(k.get("data") or []):
            nuevo = max(nuevo, int(x.get("timestamp") or 0))
            if x.get("contractType") != 1: continue   # 1 = TransferContract (TRX)
            monto = float(x.get("amount") or 0) / 1e6; vu = monto * trx_usd
            if vu < UMBRAL_USD: continue
            fecha = iso(x["timestamp"] / 1000)
            if x.get("ownerAddress") == a:
                out["eventos"].append(evento(w, ctx, "transferencia", "TRX", monto, "salida", x.get("hash"), x.get("toAddress"), fecha, valor_usd=vu))
                descubrir(ctx, "TRX", x.get("toAddress"), a, "destino de una salida", x.get("hash"), fuerte=False, w=w, valor_usd=vu)
            elif x.get("toAddress") == a:
                out["eventos"].append(evento(w, ctx, "transferencia", "TRX", monto, "entrada", x.get("hash"), x.get("ownerAddress"), fecha, valor_usd=vu))
    except Exception as e:
        print("tron transferencias:", str(e)[:80]); return   # sin avanzar el cursor
    out["cursor"]["ts"] = nuevo


def pad_tron(a):
    """dirección base58 de Tron -> parámetro ABI (20 bytes en 32)."""
    n = 0
    for ch in a: n = n * 58 + "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz".index(ch)
    b = n.to_bytes(25, "big")   # 0x41 + 20 bytes + 4 checksum
    return b[1:21].hex().rjust(64, "0")


# --- EVM -------------------------------------------------------------------------------------------------------------------
def consultar_evm(w, out, prev, ctx):
    red, a = w["red"], w["direccion"]; tokens = ctx["tokens"]
    # 1. tabla de contratos a consultar: fijos + semilla OrionX + descubiertos (logs e inventario)
    contratos = {c: (sym, dec) for sym, lst in TOKENS[red].items() for c, dec in lst}
    if w.get("tipo") == "orionx":
        contratos.update({c: (sym, dec) for sym, lst in TOKENS_ORIONX.get(red, {}).items() for c, dec in lst})
    for sym, lst in out["tokens_contratos"].items():
        for c in lst:
            t = tokens.meta(red, c); contratos.setdefault(c, (t["simbolo"], t["decimales"]))
    for c in ctx["logs_por_direccion"].get(krd(red, a), {}).get("contratos", []):
        t = tokens.meta(red, c); contratos.setdefault(c, (t["simbolo"], t["decimales"]))
    # inventario Blockscout una vez al día (ETH y Polygon): tokens con precio ya existentes en la dirección
    inv_fecha = (prev or {}).get("inventario")
    if red in BLOCKSCOUT and (not inv_fecha or inv_fecha < (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M UTC")):
        try:
            for c, (sym, dec, saldo, rate) in inventario_blockscout(red, a, tokens).items(): contratos.setdefault(c, (sym, dec))
            out["inventario"] = ahora_txt()
        except Exception as e: print(f"inventario {red} {a[:10]}:", str(e)[:60]); out["inventario"] = inv_fecha
    else: out["inventario"] = inv_fecha
    # 2. precios por contrato (los fijos ya vienen por símbolo) y saldos, todo en un lote JSON-RPC; solo cuentan los con precio
    tokens.actualizar_precios(red, list(contratos))
    con_precio = [(c, sym, dec, tokens.precio(red, c)) for c, (sym, dec) in contratos.items() if tokens.precio(red, c)]
    sin_precio = [sym for c, (sym, dec) in contratos.items() if not tokens.precio(red, c)]
    reciente = (prev or {}).get("congelada_fecha", "") > (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=55)).strftime("%Y-%m-%d %H:%M UTC")
    revisar_cong = red in CONGELABLES and not (reciente and isinstance((prev or {}).get("congelada"), dict))
    llamadas = [("eth_getBalance", [a, "latest"]), ("eth_getTransactionCount", [a, "latest"])]
    llamadas += [("eth_call", [{"to": c, "data": "0x70a08231" + pad(a)}, "latest"]) for c, _, _, _ in con_precio]
    if revisar_cong: llamadas += [("eth_call", [{"to": contrato, "data": selector + pad(a)}, "latest"]) for sym, (contrato, selector) in CONGELABLES[red].items()]
    res = rpc_lote(red, llamadas)
    if res[0] is None: raise RuntimeError(f"RPC {red}: sin respuesta para eth_getBalance")
    out["saldo"] = int(res[0], 16) / 1e18; out["tx"] = int(res[1], 16) if res[1] else (prev or {}).get("tx")
    out["ultima"] = f"{out['tx']} tx enviadas (nonce)"   # sin indexador no hay fecha; el nonce delata salidas
    tc = {}
    for (c, sym, dec, precio), r in zip(con_precio, res[2:2 + len(con_precio)]):
        if r is None: print(f"balanceOf {sym} {a[:10]}: sin respuesta"); continue
        sym = simbolo_unico(ctx, sym, precio, c); saldo = int(r, 16) / 10 ** dec
        out["tokens"][sym] = out["tokens"].get(sym, 0) + saldo
        if c not in tc.setdefault(sym, []): tc[sym].append(c)
        if sym not in ctx["px"] or not ctx["px"][sym].get("usd"): ctx["px"][sym] = {"usd": precio, "clp": precio * clp_por_usd(ctx["px"])}
    out["tokens_contratos"] = {s: l for s, l in tc.items() if s not in TOKENS[red] and s not in TOKENS_ORIONX.get(red, {})}
    if sin_precio: out["tokens_sin_precio"] = sorted(set(sin_precio))[:15]
    # 3. congelamiento (se revisa una vez por hora; el rock corre cada 10 min)
    if red in CONGELABLES:
        if revisar_cong:
            cong = {sym: int(r, 16) == 1 for (sym, _), r in zip(CONGELABLES[red].items(), res[2 + len(con_precio):]) if r is not None}
            if cong: out["congelada"], out["congelada_fecha"] = cong, ahora_txt()
        else:
            out["congelada"], out["congelada_fecha"] = prev["congelada"], prev["congelada_fecha"]
    # 4. eventos de los logs de esta corrida (transferencias con hash y aprobaciones)
    for l in ctx["logs_por_direccion"].get(krd(red, a), {}).get("logs", []):
        if len(l.get("topics") or []) != 3: continue   # 4 temas = NFT (ERC-721): no se sigue
        c = l["address"].lower(); t = tokens.meta(red, c); sym = t["simbolo"]; dec = t["decimales"]
        precio = tokens.precio(red, c)   # solo por contrato (ver arriba)
        if not precio: continue     # token sin precio: imitador ("USDT" falso) o sin mercado; no se anota
        sym = simbolo_unico(ctx, sym, precio, c)
        de, para = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:]
        try: crudo = int(l["data"], 16) if l.get("data") not in (None, "0x") else 0
        except ValueError: continue
        valor = crudo / 10 ** dec
        fecha = bloque_fecha(red, int(l["blockNumber"], 16), ctx["bloques"])
        if l["topics"][0] == TOPIC_APPROVAL:
            monto = "ilimitada" if crudo >= ILIMITADA else f"{valor:,.2f}"
            out["eventos"].append(evento(w, ctx, "aprobacion", sym, f"aprobación {monto}", "aprobacion", l["transactionHash"], para, fecha,
                                         detalle_extra="(permite a la contraparte mover el token con transferFrom)"))
            continue
        vu = valor * precio
        if vu < UMBRAL_USD: continue
        if de == a.lower():
            out["eventos"].append(evento(w, ctx, "transferencia", sym, valor, "salida", l["transactionHash"], para, fecha, valor_usd=vu))
            if not es_contrato(red, para, ctx["contratos_cache"]):
                deleg = delegado_7702(red, para, ctx["contratos_cache"])
                motivo = "destino de una salida" + (f" (EOA con delegación EIP-7702 a {corto(deleg)})" if deleg else "")
                descubrir(ctx, red, para, a, motivo, l["transactionHash"], fuerte=False, w=w, valor_usd=vu)
        elif para == a.lower():
            out["eventos"].append(evento(w, ctx, "transferencia", sym, valor, "entrada", l["transactionHash"], de, fecha, valor_usd=vu))


def agrupar_avisos(eventos, maximo=3):
    """Si una misma dirección hizo más de `maximo` movimientos en la corrida, se avisa en una sola
    línea con el neto. Un agregador puede hacer once en una hora y taparía todo lo demás."""
    por_dir, orden = {}, []
    for e in eventos:
        k = (e.get("red"), e.get("direccion"))
        if k not in por_dir: por_dir[k] = []; orden.append(k)
        por_dir[k].append(e)
    out = []
    for k in orden:
        l = por_dir[k]
        if len(l) <= maximo: out.extend(l); continue
        ent = sum(x.get("valor_usd") or 0 for x in l if x.get("sentido") == "entrada")
        sal = sum(x.get("valor_usd") or 0 for x in l if x.get("sentido") == "salida")
        out.append({**l[0], "tipo_evento": "resumen", "moneda": None, "cantidad": None, "sentido": None,
                    "hash": None, "hash_url": None, "contraparte": None, "contraparte_etiqueta": None,
                    "valor_usd": round(ent + sal, 2),
                    "detalle": f"{len(l)} movimientos en esta corrida: entradas ≈US$ {ent:,.0f}, salidas ≈US$ {sal:,.0f} (detalle en el monitor)"})
    return out


# ------------------------------------------------------------------------------------------------------------ Discord
def discord(webhook, eventos, data):
    lineas = [f"**Monitor OrionX: {len(eventos)} movimiento(s) nuevo(s)** ({data['actualizado']})"]
    for e in eventos[:15]:
        lineas.append(f"• [{e['red']}] {e['etiqueta']}: {e['detalle']}  <{e.get('hash_url') or EXPLORER[e['red']].format(a=e['direccion'])}>")
    post(webhook, {"content": "\n".join(lineas)[:1900]})


# --------------------------------------------------------------------------------------------------------------- main
def main():
    wallets = cargar_wallets()
    prev, prev_px, d_ant = {}, {}, {}
    if (HERE / "data.json").exists():
        d_ant = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
        for b in d_ant.get("billeteras", []): prev[krd(b["red"], b["direccion"])] = b
        prev_px = d_ant.get("precios") or {}
    px, precios_antiguos = precios(prev_px)
    ahora = ahora_txt()
    desc_doc = cargar_descubiertas(); descubiertas = desc_doc.get("direcciones", [])
    ctx = {"px": px, "tokens": Tokens(d_ant.get("tokens_conocidos"), px), "etiquetas": cargar_etiquetas(), "bloques": {}, "contratos_cache": {},
           "logs_por_direccion": {}, "descubiertas": descubiertas, "descubiertas_idx": {krd(d["red"], d["direccion"]): d for d in descubiertas},
           "descubiertas_nuevas": 0, "seguidas_nuevas": 0, "vigiladas": {krd(w["red"], w["direccion"]) for w in wallets}, "conocidas": set()}
    try:
        ctx["conocidas"] = {krd(w["red"], w["direccion"]) for w in json.loads((HERE / "direcciones.json").read_text(encoding="utf-8"))["direcciones"]}
    except Exception: pass
    # descubiertas que se siguen (saldo en cada corrida), después de las vigiladas
    seguidas = [d for d in descubiertas if d.get("seguir")][-MAX_SEGUIDAS:]
    for d in seguidas:
        wallets.append({"red": d["red"], "direccion": d["direccion"], "etiqueta": f"Descubierta: {d.get('motivo', '')}"[:90], "tipo": "descubierta", "vigilar": False,
                        "nota": f"Vista el {d.get('desde', '')} desde {corto(d.get('origen') or '')}. Pendiente de validación humana.", "origen": d.get("origen")})
    # 1. logs EVM de toda la red en pocas llamadas (una pasada por red, no por dirección)
    cursores, errores, huecos = dict(d_ant.get("cursores") or {}), [], []
    for red in RPC:
        dirs = [w["direccion"].lower() for w in wallets if w["red"] == red]
        if not dirs: continue
        try:
            latest = int(rpc(red, "eth_blockNumber", []), 16)
            logs, nuevo, hueco = escanear_evm(red, dirs, (cursores.get(red) or {}).get("bloque") if d_ant else None, latest)
            claves = {krd(red, x) for x in dirs}
            for l in logs:
                for t in l["topics"][1:3]:
                    k = krd(red, "0x" + t[-40:])
                    if k in claves:
                        e = ctx["logs_por_direccion"].setdefault(k, {"logs": [], "contratos": []})
                        if l not in e["logs"]: e["logs"].append(l)
                        if l["topics"][0] == TOPIC_TRANSFER and l["address"].lower() not in e["contratos"]: e["contratos"].append(l["address"].lower())
            cursores[red] = {"bloque": nuevo, "fecha": ahora, "logs": len(logs)}
            if hueco: huecos.append(f"{red}: bloques {hueco[0]}-{hueco[1]} no revisados (el monitor estuvo detenido)"); cursores[red]["hueco"] = list(hueco)
        except Exception as e:
            errores.append(f"{red} logs: {str(e)[:140]}")
            if red in cursores: cursores[red]["error"] = str(e)[:100]
    # 2. cada dirección
    filas, eventos = [], []
    for w in wallets:
        k = krd(w["red"], w["direccion"]); p = prev.get(k)
        fila = {**w, "explorer": EXPLORER[w["red"]].format(a=w["direccion"]), "moneda": NATIVO[w["red"]]}
        try:
            fila.update(consultar(w, p, ctx))
        except Exception as e:
            errores.append(f"{w['red']} {w['direccion'][:12]}: {e}"); p = p or {}
            fila.update({kk: p.get(kk) for kk in ("saldo", "tokens", "tx", "ultima", "cursor", "tokens_contratos", "congelada", "congelada_fecha", "permisos", "inventario")}); fila["error"] = str(e)[:120]
            fila["eventos"] = []
        s = fila.get("saldo"); pr = px.get(fila["moneda"], {})
        fila["valor_clp"] = (s or 0) * pr.get("clp", 0) + sum(v * px.get(kk, {}).get("clp", 0) for kk, v in (fila.get("tokens") or {}).items() if kk in px)
        fila["valor_usd"] = (s or 0) * pr.get("usd", 0) + sum(v * px.get(kk, {}).get("usd", 0) for kk, v in (fila.get("tokens") or {}).items() if kk in px)
        base = {"fecha": ahora, "red": w["red"], "direccion": w["direccion"], "etiqueta": w["etiqueta"], "tipo": w.get("tipo"),
                "saldo_antes": (p or {}).get("saldo"), "saldo_despues": s}
        con_hash = fila.pop("eventos", []) or []
        cubiertas = {e["moneda"] for e in con_hash if e.get("tipo_evento") == "transferencia"}
        for e in con_hash: eventos.append({**base, **e, "valor_usd": round(e["valor_usd"], 2) if e.get("valor_usd") is not None else None})
        # congelamiento: cambio respecto de la corrida anterior (la primera vez solo se anota el estado)
        if p and isinstance(p.get("congelada"), dict) and isinstance(fila.get("congelada"), dict):
            for sym, est in fila["congelada"].items():
                if sym in p["congelada"] and p["congelada"][sym] != est:
                    txt = f"{sym}: la dirección {'fue CONGELADA por el emisor' if est else 'dejó de estar congelada'} (lista negra del contrato)"
                    eventos.append({**base, **evento(w, ctx, "congelamiento", sym, txt, "congelamiento", None, None, ahora), "valor_usd": fila.get("tokens", {}).get(sym, 0) * px.get(sym, {}).get("usd", 1)})
        if p and not fila.get("error") and p.get("saldo") is not None and s is not None:
            d = (s or 0) - p["saldo"]
            # umbral en dólares (UMBRAL_USD, por defecto 1): vale igual para BTC que para XRP. Sin precio, se usa un mínimo en unidades.
            usd_d = abs(d) * pr["usd"] if pr.get("usd") else None
            partes = []
            if fila["moneda"] not in cubiertas and ((usd_d >= UMBRAL_USD) if usd_d is not None else (abs(d) >= MIN_UNIDADES.get(fila["moneda"], 0.001))):
                partes.append(f"{'+' if d > 0 else ''}{d:,.8f} {fila['moneda']} (≈US$ {usd_d:,.2f}; saldo {s:,.6f})" if usd_d is not None else f"{'+' if d > 0 else ''}{d:,.8f} {fila['moneda']} (saldo {s:,.6f})")
            # tokens: solo los que ya estaban en la corrida anterior (un token recién descubierto no es una "entrada") y que no
            # quedaron ya explicados por una transferencia con hash. "pendiente" (mempool BTC) no tiene precio y se omite.
            usd_t, tok_ant, tok_act = 0.0, p.get("tokens") or {}, fila.get("tokens") or {}
            for kk in sorted(set(tok_act) & set(tok_ant) & set(px) - cubiertas):
                dk = tok_act[kk] - tok_ant[kk]; usd_k = abs(dk) * px.get(kk, {}).get("usd", 1.0)
                if usd_k >= UMBRAL_USD: partes.append(f"{'+' if dk > 0 else ''}{dk:,.2f} {kk} (saldo {tok_act[kk]:,.2f})"); usd_t += usd_k
            # Un cambio solo en el contador de transacciones cuenta si también cambió la última actividad: los contadores de
            # Tronscan oscilan (137970 → 137968 → 137970 el 10-11 sep 2026 sin ninguna transacción nueva) y eso daba falsas alertas.
            if not partes and not con_hash and fila.get("tx") and p.get("tx") and fila["tx"] != p["tx"] and fila.get("ultima") and fila.get("ultima") != p.get("ultima"):
                partes.append(f"nuevas transacciones ({p['tx']} → {fila['tx']}) " + ("sin cambio de saldo" if not d and not usd_t else f"con cambio de saldo menor a US$ {UMBRAL_USD:g}"))
            if partes:
                eventos.append({**base, "tipo_evento": "saldo", "detalle": "; ".join(partes), "valor_usd": round((usd_d or 0) + usd_t, 2)})
        filas.append(fila); time.sleep(0.2)
    # 3. historial (sin repetir lo ya anotado), descubiertas, data.json
    hist = HERE / "historial.jsonl"
    previos = [json.loads(l) for l in hist.read_text(encoding="utf-8").splitlines() if l.strip()] if hist.exists() else []
    clave = lambda e: (e.get("red"), e.get("direccion"), e.get("hash"), e.get("moneda")) if e.get("hash") else (e.get("red"), e.get("direccion"), e.get("saldo_antes"), e.get("saldo_despues"), e.get("detalle"))   # noqa: E731
    ya = {clave(e) for e in previos[-600:]}   # no re-anotar el mismo movimiento si una corrida anterior no llegó a hacer push
    nuevos = [e for e in eventos if clave(e) not in ya]
    if nuevos:
        with open(hist, "a", encoding="utf-8") as fh:
            for e in nuevos: fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    todos = previos + nuevos
    decidir_vigilancia(ctx)
    fuertes = [d for d in descubiertas if d.get("misma_billetera") or d.get("seguir")]
    debiles = [d for d in descubiertas if not (d.get("misma_billetera") or d.get("seguir"))]
    descubiertas = debiles[-(MAX_DESCUBIERTAS - len(fuertes)):] + fuertes if len(descubiertas) > MAX_DESCUBIERTAS else descubiertas
    if descubiertas or not (HERE / "descubiertas.json").exists():
        (HERE / "descubiertas.json").write_text(json.dumps({
            "_nota": "Direcciones propuestas por el monitor a partir de movimientos reales: destinos de salidas y, en BTC/LTC, entradas gastadas junto a una vigilada "
                     "(misma billetera) o posibles vueltos. NO están validadas: una persona debe confirmar la liga y, si corresponde, pasarlas a direcciones.json. "
                     "'seguir': true hace que el monitor consulte su saldo en cada corrida y avise de sus movimientos; se activa sola cuando el "
                     f"destino recibe US$ {UMBRAL_SEGUIR_USD:,.0f} o más de una dirección del caso, no tiene etiqueta pública de exchange y está a {MAX_SALTOS} "
                     "saltos o menos ('salto': 1 = destino directo de una dirección de la lista). Vigilar no es afirmar: para publicarla como dirección del "
                     "caso hay que validar la liga a mano.",
            "actualizado": ahora, "direcciones": descubiertas}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    data = {"version": VERSION, "actualizado": ahora, "precios": px, "precios_antiguos": precios_antiguos, "billeteras": filas, "eventos": todos[-300:][::-1],
            "errores": errores + huecos, "cursores": cursores, "tokens_conocidos": ctx["tokens"].c,
            "descubiertas": len(descubiertas), "descubiertas_seguidas": len(seguidas),
            "total_clp": sum(f["valor_clp"] for f in filas if f.get("tipo") != "descubierta"), "total_usd": sum(f["valor_usd"] for f in filas if f.get("tipo") != "descubierta")}
    (HERE / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ahora}: {len(filas)} billeteras, {len(nuevos)} movimientos nuevos, {len(errores)} errores; total ≈ {data['total_clp']:,.0f} CLP" + (" (precios antiguos)" if precios_antiguos else "")
          + f"; descubiertas {len(descubiertas)} (+{ctx['descubiertas_nuevas']}), seguidas {len([d for d in descubiertas if d.get('seguir')])} (+{ctx.get('seguidas_nuevas', 0)})")
    # Los avisos (Telegram en el rock lee estas líneas, y el webhook de Discord) dejan fuera el goteo de las
    # direcciones descubiertas sin validar: algunas son agregadores con decenas de transferencias por hora y
    # taparían los movimientos de las billeteras de OrionX. En data.json y en el historial quedan todos.
    avisables = agrupar_avisos([e for e in nuevos if e.get("tipo") != "descubierta" or (e.get("valor_usd") or 0) >= UMBRAL_AVISO_DESCUBIERTA_USD])
    for e in avisables: print("  MOV", e["red"], e["etiqueta"], e["detalle"])
    callados = len(nuevos) - len(avisables)
    if callados: print(f"  ({callados} movimiento(s) de direcciones descubiertas bajo US$ {UMBRAL_AVISO_DESCUBIERTA_USD:,.0f}: van a data.json, sin aviso)")
    for e in errores + huecos: print("  ERR", e)
    wh = os.environ.get("DISCORD_WEBHOOK")
    if wh and avisables: discord(wh, avisables, data)
    if wh and errores and os.environ.get("AVISAR_ERRORES"): post(wh, {"content": "Monitor OrionX: errores de consulta\n" + "\n".join(errores)[:1800]})


if __name__ == "__main__":
    main()
