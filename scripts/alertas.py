#!/usr/bin/env python3
"""Alertas de movimiento de las billeteras vigiladas. Solo librería estándar.

Compara dos fotos de `data.json` (la anterior y la que acaba de escribir
`monitor.py`) y levanta una alerta por dirección y moneda cuando:

  * el saldo cambia más que el umbral de esa moneda (ver UMBRALES: 0,01 BTC,
    0,5 ETH, 1.000 XRP, 1.000 USDT/USDC, 5 LTC, 500 TRX; en BSC y Polygon lo
    que equivalga a ≈US$ 500; para cualquier otro token, ≈US$ 500), o
  * sale cualquier cantidad desde una dirección `desvio` o `atribuida` con rol
    de almacenamiento en frío: ahí no hay umbral, que se mueva ya es la noticia, o
  * (desde el 15-sep-2026) hay una señal previa al movimiento: una aprobación
    ERC-20 desde la dirección, un cambio de permisos de la cuenta en Tron, un
    congelamiento del emisor (Tether/Circle) o un "fondeo de gas": una entrada
    pequeña de moneda nativa en una dirección que guarda tokens por más de
    US$ 1.000 (es lo que se hace justo antes de vaciarla).

Cada alerta lleva, cuando el monitor las tiene, las transacciones con hash y
contraparte que explican el cambio (y la etiqueta pública de la contraparte).

`monitor.py` sigue anotando en `historial.jsonl` todo cambio desde US$ 1; esto
es la capa de aviso, con umbrales más altos para no gritar por el ruido.

Dos pasos, para que el issue se abra después de que los datos ya estén en el
repositorio:

  python scripts/alertas.py --anterior ANT.json [--actual data.json] \
                            [--nuevas /tmp/alertas_nuevas.json]
      detecta, actualiza `alertas.json` (máximo 50, la más reciente primero) y
      deja las alertas nuevas en el archivo `--nuevas`.

  python scripts/alertas.py --avisar /tmp/alertas_nuevas.json
      pide a Wayback Machine una copia fechada del explorador (dirección y
      transacciones), abre un issue por alerta (o comenta en el que ya esté
      abierto para esa dirección en las últimas 24 h) y manda el mismo texto a
      Telegram si están los secretos.

Variables de entorno (todas opcionales):
  ALERTA_UMBRALES     JSON con umbrales por moneda, p. ej. {"BTC": 0.02}
  ALERTA_MAX_AVISOS   máximo de issues/mensajes por corrida (por defecto 10)
  ALERTA_SIN_WAYBACK  si está definida, no se piden copias a web.archive.org
  GITHUB_TOKEN        token del workflow; necesita permiso `issues: write`
  GITHUB_REPOSITORY   "dueño/repo" (lo define GitHub Actions)
  TELEGRAM_BOT_TOKEN  \\ si falta cualquiera de los dos, se salta Telegram
  TELEGRAM_CHAT_ID    /  sin fallar ni avisar de error

Sin claves de terceros en el repositorio: todo viene del entorno.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from monitor import EXPLORER, EXPLORER_TX, NATIVO, krd  # noqa: E402  (mismo repo, solo stdlib)

UA = {"User-Agent": "orionx-monitor-alertas/1.0 (github pages; afectados)"}
MONITOR_URL = "https://afectados-orionx.github.io/orionx-monitor/#movimientos"
FRASE = "Dato en cadena; la Fiscalía debe establecer responsabilidades."

# Umbral en unidades de la propia moneda.
UMBRALES = {"BTC": 0.01, "ETH": 0.5, "XRP": 1000.0, "USDT": 1000.0, "USDC": 1000.0, "LTC": 5.0, "TRX": 500.0}
# BSC y Polygon: el umbral es ≈US$ 500 al precio del momento. Cualquier otro token (DAI, XAUT, DOT…): lo mismo.
UMBRAL_USD = {"BNB": 500.0, "POL": 500.0}
UMBRAL_USD_OTROS = 500.0
# Respaldo en unidades si CoinGecko no respondió y no hay precio para convertir.
RESPALDO_UNIDADES = {"BNB": 0.7, "POL": 5000.0}
# Por debajo de esto no hay movimiento: son redondeos de las APIs (se vieron
# oscilaciones de 0,000001 TRX y 0,000002 XRP sin ninguna transacción nueva).
RUIDO = 1e-6
MAX_ALERTAS = 50          # cuántas guarda alertas.json para la web
TIPOS_FRIO = ("desvio", "atribuida")
RE_FRIO = re.compile(r"fr[ií]o|cold", re.IGNORECASE)
# Fondeo de gas: entrada de nativo entre estos dólares, en una dirección con tokens por más de GAS_TOKENS_USD.
GAS_MIN_USD, GAS_MAX_USD, GAS_TOKENS_USD = 0.2, 400.0, 1000.0
CLASES = {"saldo": "Movimiento", "aprobacion": "Aprobación", "permisos": "Permisos", "congelamiento": "Congelamiento", "gas": "Fondeo de gas"}


# ---------------------------------------------------------------- utilidades

def leer_json(ruta, por_defecto=None):
    p = Path(ruta)
    if not p.exists():
        return por_defecto
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        print(f"alertas: no se pudo leer {p.name}: {e}")
        return por_defecto


def corto(a):
    return a if len(a) <= 22 else a[:10] + "…" + a[-6:]


def umbrales_config():
    """UMBRALES con lo que traiga ALERTA_UMBRALES (JSON) encima."""
    u = dict(UMBRALES)
    crudo = os.environ.get("ALERTA_UMBRALES")
    if crudo:
        try:
            u.update({k.upper(): float(v) for k, v in json.loads(crudo).items()})
        except (ValueError, AttributeError, TypeError) as e:
            print(f"alertas: ALERTA_UMBRALES se ignora, no es un JSON de números: {e}")
    return u


def num_es(x):
    """Número con formato chileno: 1.000 / 0,01 (los umbrales se leen en la web)."""
    s = f"{x:,.8f}".rstrip("0").rstrip(".") if x % 1 else f"{x:,.0f}"
    return s.replace(",", "·").replace(".", ",").replace("·", ".")


# Las direcciones que el monitor descubrió solo (tipo "descubierta") todavía no están validadas y
# algunas son agregadores que mueven dinero de terceros todo el día: avisan solo si el movimiento es
# grande, para no ahogar las alertas de las billeteras de OrionX.
UMBRAL_DESCUBIERTA_USD = float(os.environ.get("ALERTA_UMBRAL_DESCUBIERTA_USD", "50000"))


def umbral_de(moneda, precios, umbrales):
    """(umbral en unidades, cómo se explica). None = sin umbral aplicable."""
    if moneda in umbrales:
        return umbrales[moneda], f"{num_es(umbrales[moneda])} {moneda}"
    usd = (precios.get(moneda) or {}).get("usd")
    if moneda in UMBRAL_USD:
        if usd:
            return UMBRAL_USD[moneda] / usd, f"≈US$ {num_es(UMBRAL_USD[moneda])}"
        return RESPALDO_UNIDADES[moneda], f"{num_es(RESPALDO_UNIDADES[moneda])} {moneda} (sin precio para convertir)"
    if usd:      # cualquier otro token con precio (DAI, XAUT, DOT, ADA, SOL…)
        return UMBRAL_USD_OTROS / usd, f"≈US$ {num_es(UMBRAL_USD_OTROS)}"
    return None, None


def es_frio(reg):
    """Dirección de desvío o atribuida cuyo rol declarado es almacenamiento en frío."""
    if not reg or reg.get("tipo") not in TIPOS_FRIO:
        return False
    return bool(RE_FRIO.search(str(reg.get("rol") or "")))


def registros_por_clave(doc):
    if not doc:
        return {}
    return {krd(r["red"], r["direccion"]): r for r in doc.get("direcciones", []) if r.get("red") and r.get("direccion")}


def saldos(fila):
    """Pares (moneda, cantidad) de una fila de data.json: el nativo y sus tokens.
    'pendiente' (mempool de Bitcoin) no es un token: no se compara."""
    out = {}
    if fila.get("moneda"):
        out[fila["moneda"]] = fila.get("saldo")
    for k, v in (fila.get("tokens") or {}).items():
        if k != "pendiente":
            out[k] = v
    return out


def eventos_de_la_corrida(actual):
    """Eventos que monitor.py anotó en esta misma corrida, agrupados por (red, dirección)."""
    out = {}
    fecha = actual.get("actualizado")
    for e in actual.get("eventos") or []:
        if e.get("fecha") != fecha or not e.get("red") or not e.get("direccion"):
            continue
        out.setdefault(krd(e["red"], e["direccion"]), []).append(e)
    return out


def transacciones(eventos, moneda=None):
    """Resumen de los eventos con hash (transferencias) de una dirección, opcionalmente de una moneda."""
    out = []
    for e in eventos:
        if e.get("tipo_evento") != "transferencia" or not e.get("hash"):
            continue
        if moneda and e.get("moneda") != moneda:
            continue
        out.append({k: e.get(k) for k in ("hash", "hash_url", "contraparte", "contraparte_etiqueta", "cantidad", "moneda", "sentido", "fecha_cadena", "valor_usd")})
    return out[:12]


# ------------------------------------------------------------- la detección

def redactar(a):
    """Título y cuerpo del aviso. Redacción prudente: el dato, no la acusación."""
    clase = a.get("clase") or "saldo"
    rol = f", rol declarado: {a['rol']}" if a.get("rol") else ""
    lineas = [f"**{a['etiqueta']}** (tipo `{a['tipo']}`{rol}).", "", f"- Red: **{a['red']}**", f"- Dirección: `{a['direccion']}`"]
    if clase in ("saldo", "gas"):
        signo = "+" if a["delta"] > 0 else ""
        monto = f"{signo}{a['delta']:,.8f} {a['moneda']}"
        titulo = f"{CLASES[clase]}: {a['red']} {a['abreviada']} {monto} {a['fecha']}"
        usd = f" (≈US$ {a['valor_usd']:,.2f})" if a.get("valor_usd") is not None else ""
        lineas += [f"- Cambio: **{monto}**{usd}",
                   f"- Saldo antes: {a['saldo_antes']:,.8f} {a['moneda']}",
                   f"- Saldo después: {a['saldo_despues']:,.8f} {a['moneda']}"]
    else:
        titulo = f"{CLASES.get(clase, clase)}: {a['red']} {a['abreviada']} {a.get('moneda') or ''} {a['fecha']}".replace("  ", " ")
        lineas += [f"- Qué pasó: **{a.get('descripcion') or a.get('motivo')}**"]
        if a.get("contraparte"):
            et = f" ({a['contraparte_etiqueta']})" if a.get("contraparte_etiqueta") else ""
            lineas.append(f"- Contraparte: `{a['contraparte']}`{et}")
        if a.get("hash_url"):
            lineas.append(f"- Transacción: {a['hash_url']}")
    for t in a.get("transacciones") or []:
        et = f" ({t['contraparte_etiqueta']})" if t.get("contraparte_etiqueta") else ""
        flecha = "→" if t.get("sentido") == "salida" else "←"
        cant = f"{t['cantidad']:,.8f}".rstrip("0").rstrip(".") if isinstance(t.get("cantidad"), (int, float)) else ""
        lineas.append(f"- Tx: {cant} {t.get('moneda') or ''} {flecha} `{t.get('contraparte') or '?'}`{et} · {t.get('hash_url') or t.get('hash')}"
                      + (f" · {t['fecha_cadena']}" if t.get("fecha_cadena") else ""))
    lineas += [f"- Detectado: {a['fecha']} (comparando dos chequeos del monitor)",
               f"- Por qué se avisa: {a['motivo']}",
               f"- Explorador: {a['explorador']}",
               f"- Monitor: {a['monitor']}"]
    if a.get("wayback"):
        lineas.append("- Copia fechada (Wayback Machine): " + " · ".join(a["wayback"]))
    lineas += ["", FRASE]
    return titulo, "\n".join(lineas)


def base_alerta(fila, reg, fecha, clase, moneda):
    return {
        "fecha": fecha,
        "clase": clase,
        "red": fila["red"],
        "direccion": fila["direccion"],
        "abreviada": corto(fila["direccion"]),
        "etiqueta": (reg or {}).get("etiqueta_publica") or fila.get("etiqueta") or "dirección vigilada",
        "tipo": fila.get("tipo") or (reg or {}).get("tipo") or "vigilada",
        "rol": (reg or {}).get("rol"),
        "moneda": moneda,
        "delta": None, "saldo_antes": None, "saldo_despues": None, "valor_usd": None,
        "motivo": "", "frio": False,
        "explorador": EXPLORER[fila["red"]].format(a=fila["direccion"]),
        "monitor": MONITOR_URL,
    }


def detectar(anterior, actual, registros):
    """Lista de alertas comparando dos data.json."""
    umbrales = umbrales_config()
    precios = actual.get("precios") or {}
    fecha = actual.get("actualizado") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    previas = {krd(b["red"], b["direccion"]): b for b in anterior.get("billeteras", []) if b.get("red") and b.get("direccion")}
    por_dir = eventos_de_la_corrida(actual)
    alertas = []
    for fila in actual.get("billeteras", []):
        if not fila.get("red") or not fila.get("direccion"):
            continue
        clave = krd(fila["red"], fila["direccion"])
        antes = previas.get(clave)
        if antes is None or fila.get("error") or antes.get("error"):
            continue          # dirección nueva o consulta fallida: no hay comparación fiable
        reg = registros.get(clave)
        frio = es_frio(reg)
        evs = por_dir.get(clave, [])
        sa, sd = saldos(antes), saldos(fila)
        nativo = NATIVO.get(fila["red"])
        valor_tokens = (fila.get("valor_usd") or 0) - (fila.get("saldo") or 0) * ((precios.get(nativo) or {}).get("usd") or 0)
        for moneda in sorted(set(sa) & set(sd)):
            a0, a1 = sa[moneda], sd[moneda]
            if a0 is None or a1 is None:
                continue
            d = a1 - a0
            if abs(d) <= RUIDO:
                continue
            umbral, texto_umbral = umbral_de(moneda, precios, umbrales)
            usd_unit = (precios.get(moneda) or {}).get("usd")
            if usd_unit is None and moneda in ("USDT", "USDC"):
                usd_unit = 1.0
            if fila.get("tipo") == "descubierta" and usd_unit:
                minimo = UMBRAL_DESCUBIERTA_USD / usd_unit
                if umbral is None or umbral < minimo:
                    umbral = minimo
                    texto_umbral = f"≈US$ {num_es(UMBRAL_DESCUBIERTA_USD)}, el que rige para las direcciones descubiertas sin validar"
            salida_frio = frio and d < 0
            valor = abs(d) * usd_unit if usd_unit else None
            gas = (moneda == nativo and d > 0 and valor is not None and GAS_MIN_USD <= valor <= GAS_MAX_USD
                   and valor_tokens >= GAS_TOKENS_USD and (umbral is None or abs(d) < umbral))
            if not salida_frio and not gas and (umbral is None or abs(d) < umbral):
                continue
            que_es = "atribuida" if (reg or {}).get("tipo") == "atribuida" else "de desvío"
            if salida_frio:
                motivo = f"salida desde una dirección {que_es} con rol de almacenamiento en frío: se avisa sin umbral"
            elif gas:
                motivo = (f"entrada pequeña de {moneda} en una dirección que guarda tokens por ≈US$ {valor_tokens:,.0f}: "
                          "es el gas que hace falta para moverlos (posible preparación de un retiro)")
            else:
                motivo = f"el cambio supera el umbral de aviso de la red ({texto_umbral})"
            alerta = base_alerta(fila, reg, fecha, "gas" if gas else "saldo", moneda)
            alerta.update({"delta": round(d, 8), "saldo_antes": a0, "saldo_despues": a1,
                           "valor_usd": round(valor, 2) if valor is not None else None,
                           "motivo": motivo, "frio": bool(salida_frio), "transacciones": transacciones(evs, moneda)})
            alerta["titulo"], alerta["cuerpo"] = redactar(alerta)
            alertas.append(alerta)
        # señales previas al movimiento: siempre se avisan, sin umbral
        for e in evs:
            clase = e.get("tipo_evento")
            if clase not in ("aprobacion", "permisos", "congelamiento"):
                continue
            alerta = base_alerta(fila, reg, fecha, clase, e.get("moneda") or "")
            desc = {"aprobacion": "la dirección autorizó a otra a mover sus tokens (Approval ERC-20); es el paso previo a un retiro vía contrato o a una venta",
                    "permisos": "cambiaron los permisos owner/active de la cuenta en Tron: cambio de quién controla las llaves",
                    "congelamiento": "cambió el estado de lista negra del emisor de la stablecoin para esta dirección"}[clase]
            alerta.update({"descripcion": e.get("detalle"), "motivo": desc, "hash": e.get("hash"), "hash_url": e.get("hash_url"),
                           "contraparte": e.get("contraparte"), "contraparte_etiqueta": e.get("contraparte_etiqueta"),
                           "valor_usd": e.get("valor_usd"), "delta": 0.0, "saldo_antes": sa.get(e.get("moneda")), "saldo_despues": sd.get(e.get("moneda"))})
            alerta["titulo"], alerta["cuerpo"] = redactar(alerta)
            alertas.append(alerta)
    return alertas


def clave_alerta(a):
    return (a.get("red"), a.get("direccion"), a.get("moneda"), a.get("saldo_antes"), a.get("saldo_despues"), a.get("clase") or "saldo", a.get("hash"))


def guardar(alertas_nuevas, ruta):
    """Mete las nuevas al principio de alertas.json, sin repetir, máximo 50."""
    doc = leer_json(ruta, {}) or {}
    previas = doc.get("alertas") or []
    vistas = {clave_alerta(a) for a in previas}
    frescas = [a for a in alertas_nuevas if clave_alerta(a) not in vistas]
    if not frescas and doc:
        return []          # sin novedad: no se reescribe el archivo (así no hay commit de ruido cada hora)
    doc = {
        "actualizado": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "umbrales": {"unidades": umbrales_config(), "usd": {**UMBRAL_USD, "otros tokens": UMBRAL_USD_OTROS},
                     "nota": "Salidas desde almacenamiento en frío (desvío o atribuida), aprobaciones, cambios de permisos, congelamientos y fondeos de gas se avisan sin umbral."},
        "alertas": (frescas + previas)[:MAX_ALERTAS],
    }
    Path(ruta).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frescas


# ------------------------------------------------------------------- avisos

def wayback(url):
    """Pide a Wayback Machine que guarde la página; devuelve la URL de la copia o None. Un intento, nunca lanza."""
    try:
        req = urllib.request.Request("https://web.archive.org/save/" + url, headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            loc = r.headers.get("Content-Location") or ""
            final = r.geturl() or ""
        if loc.startswith("/web/"):
            return "https://web.archive.org" + loc
        if "web.archive.org/web/" in final:
            return final
        return "https://web.archive.org/web/*/" + url
    except Exception as e:  # noqa: BLE001
        print("alertas: Wayback no guardó", url[:60], type(e).__name__)
        return None


def archivar(a):
    """Copias fechadas por un tercero del explorador: la dirección y la primera transacción. Es un intento de cortesía:
    el 15-sep-2026 Save Page Now devolvía 500 a todo; si no responde, la alerta sale igual, sin la línea de Wayback."""
    if os.environ.get("ALERTA_SIN_WAYBACK"):
        return
    urls = [a["explorador"]] + [t["hash_url"] for t in (a.get("transacciones") or []) if t.get("hash_url")][:1]
    if a.get("hash_url"):
        urls.append(a["hash_url"])
    copias = []
    for u in dict.fromkeys(urls):
        c = wayback(u)
        if c:
            copias.append(c)
    if copias:
        a["wayback"] = copias
        a["titulo"], a["cuerpo"] = redactar(a)


def github(metodo, ruta, payload=None):
    """Llamada a la API de GitHub con el GITHUB_TOKEN del workflow."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    url = f"https://api.github.com/repos/{repo}{ruta}"
    req = urllib.request.Request(
        url, method=metodo,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={**UA, "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cuerpo = r.read()
        return json.loads(cuerpo) if cuerpo else {}


def issue_abierto_reciente(direccion, horas=24):
    """Número del issue abierto de esa dirección en las últimas `horas`, si existe."""
    try:
        issues = github("GET", "/issues?state=open&labels=movimiento&per_page=100&sort=created&direction=desc") or []
    except (urllib.error.URLError, OSError, ValueError) as e:
        print("alertas: no se pudo listar issues:", type(e).__name__)
        return None
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=horas)
    for it in issues:
        if "pull_request" in it:
            continue
        try:
            creado = dt.datetime.strptime(it.get("created_at", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if creado >= limite and direccion in (it.get("body") or ""):
            return it.get("number")
    return None


def avisar_github(a):
    """Abre el issue, o comenta en el que ya está abierto para esa dirección."""
    if not (os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY")):
        print("alertas: sin GITHUB_TOKEN/GITHUB_REPOSITORY, no se abre issue")
        return
    try:
        numero = issue_abierto_reciente(a["direccion"])
        if numero:
            github("POST", f"/issues/{numero}/comments", {"body": f"### {a['titulo']}\n\n{a['cuerpo']}"})
            print(f"alertas: comentario en el issue #{numero} ({a['red']} {a['abreviada']})")
        else:
            r = github("POST", "/issues", {"title": a["titulo"], "body": a["cuerpo"], "labels": ["movimiento"]}) or {}
            print(f"alertas: issue #{r.get('number', '?')} abierto ({a['red']} {a['abreviada']})")
    except (urllib.error.URLError, OSError, ValueError) as e:
        # Nunca interrumpir la corrida por un aviso, y nunca imprimir cabeceras (llevan el token).
        print("alertas: aviso a GitHub no enviado:", type(e).__name__, getattr(e, "code", ""))


def avisar_telegram(a):
    """Opcional y desacoplado: si no están los dos secretos, no se hace nada."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    texto = (a["titulo"] + "\n\n" + a["cuerpo"].replace("**", "").replace("`", ""))[:3800]
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": texto, "disable_web_page_preview": True}).encode(),
            headers={**UA, "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        print(f"alertas: enviada a Telegram ({a['red']} {a['abreviada']})")
        return True
    except (urllib.error.URLError, OSError, ValueError) as e:
        # La URL lleva el token del bot: solo el tipo de error.
        print("alertas: aviso a Telegram no enviado:", type(e).__name__)
        return False


def avisar(ruta):
    alertas = leer_json(ruta, []) or []
    if isinstance(alertas, dict):
        alertas = alertas.get("alertas") or []
    if not alertas:
        print("alertas: nada que avisar")
        return 0
    tope = int(os.environ.get("ALERTA_MAX_AVISOS", "10"))
    for a in alertas[:tope]:
        archivar(a)
        avisar_github(a)
        avisar_telegram(a)
    if len(alertas) > tope:
        print(f"alertas: {len(alertas) - tope} alerta(s) más no se avisaron (tope ALERTA_MAX_AVISOS={tope}); quedan en alertas.json")
    return 0


# --------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Alertas de movimiento de las billeteras vigiladas")
    ap.add_argument("--anterior", help="data.json de antes de la última consulta")
    ap.add_argument("--actual", default=str(ROOT / "data.json"), help="data.json recién escrito por monitor.py")
    ap.add_argument("--direcciones", default=str(ROOT / "direcciones.json"))
    ap.add_argument("--salida", default=str(ROOT / "alertas.json"), help="archivo que lee la web (máximo 50)")
    ap.add_argument("--nuevas", help="archivo donde dejar solo las alertas nuevas (para el paso de aviso)")
    ap.add_argument("--avisar", metavar="ARCHIVO", help="manda a GitHub y Telegram las alertas de ese archivo")
    ap.add_argument("--sin-guardar", action="store_true", help="no escribir alertas.json (pruebas)")
    args = ap.parse_args(argv)

    if args.avisar:
        return avisar(args.avisar)
    if not args.anterior:
        ap.error("hace falta --anterior (o --avisar ARCHIVO)")

    anterior = leer_json(args.anterior)
    actual = leer_json(args.actual)
    if not actual:
        print(f"alertas: no hay {args.actual}, nada que comparar")
        return 0
    if not anterior:
        print(f"alertas: no hay foto anterior ({args.anterior}); primera corrida, sin alertas")
        nuevas = []
    else:
        nuevas = detectar(anterior, actual, registros_por_clave(leer_json(args.direcciones)))

    if not args.sin_guardar:
        nuevas = guardar(nuevas, args.salida)
    if args.nuevas:
        Path(args.nuevas).write_text(json.dumps(nuevas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"alertas: {len(nuevas)} alerta(s) nueva(s)")
    for a in nuevas:
        print("  ALERTA", a["titulo"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
