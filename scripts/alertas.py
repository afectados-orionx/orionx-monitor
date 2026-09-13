#!/usr/bin/env python3
"""Alertas de movimiento de las billeteras vigiladas. Solo librería estándar.

Compara dos fotos de `data.json` (la anterior y la que acaba de escribir
`monitor.py`) y levanta una alerta por dirección y moneda cuando:

  * el saldo cambia más que el umbral de esa moneda (ver UMBRALES: 0,01 BTC,
    0,5 ETH, 1.000 XRP, 1.000 USDT/USDC, 5 LTC, 500 TRX; en BSC y Polygon lo
    que equivalga a ≈US$ 500), o
  * sale cualquier cantidad desde una dirección `desvio` o `atribuida` con rol
    de almacenamiento en frío: ahí no hay umbral, que se mueva ya es la noticia.

`monitor.py` sigue anotando en `historial.jsonl` todo cambio desde US$ 1; esto
es la capa de aviso, con umbrales más altos para no gritar por el ruido.

Dos pasos, para que el issue se abra después de que los datos ya estén en el
repositorio:

  python scripts/alertas.py --anterior ANT.json [--actual data.json] \
                            [--nuevas /tmp/alertas_nuevas.json]
      detecta, actualiza `alertas.json` (máximo 50, la más reciente primero) y
      deja las alertas nuevas en el archivo `--nuevas`.

  python scripts/alertas.py --avisar /tmp/alertas_nuevas.json
      abre un issue por alerta (o comenta en el que ya esté abierto para esa
      dirección en las últimas 24 h) y manda el mismo texto a Telegram.

Variables de entorno (todas opcionales):
  ALERTA_UMBRALES     JSON con umbrales por moneda, p. ej. {"BTC": 0.02}
  ALERTA_MAX_AVISOS   máximo de issues/mensajes por corrida (por defecto 10)
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
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from monitor import EXPLORER, krd  # noqa: E402  (mismo repo, solo stdlib)

UA = {"User-Agent": "orionx-monitor-alertas/1.0 (github pages; afectados)"}
MONITOR_URL = "https://afectados-orionx.github.io/orionx-monitor/#movimientos"
FRASE = "Dato en cadena; la Fiscalía debe establecer responsabilidades."

# Umbral en unidades de la propia moneda.
UMBRALES = {"BTC": 0.01, "ETH": 0.5, "XRP": 1000.0, "USDT": 1000.0, "USDC": 1000.0, "LTC": 5.0, "TRX": 500.0}
# BSC y Polygon: el umbral es ≈US$ 500 al precio del momento.
UMBRAL_USD = {"BNB": 500.0, "POL": 500.0}
# Respaldo en unidades si CoinGecko no respondió y no hay precio para convertir.
RESPALDO_UNIDADES = {"BNB": 0.7, "POL": 5000.0}
# Por debajo de esto no hay movimiento: son redondeos de las APIs (se vieron
# oscilaciones de 0,000001 TRX y 0,000002 XRP sin ninguna transacción nueva).
RUIDO = 1e-6
MAX_ALERTAS = 50          # cuántas guarda alertas.json para la web
TIPOS_FRIO = ("desvio", "atribuida")
RE_FRIO = re.compile(r"fr[ií]o|cold", re.IGNORECASE)


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


def umbral_de(moneda, precios, umbrales):
    """(umbral en unidades, cómo se explica). None = sin umbral aplicable."""
    if moneda in umbrales:
        return umbrales[moneda], f"{num_es(umbrales[moneda])} {moneda}"
    if moneda in UMBRAL_USD:
        usd = (precios.get(moneda) or {}).get("usd")
        if usd:
            return UMBRAL_USD[moneda] / usd, f"≈US$ {num_es(UMBRAL_USD[moneda])}"
        return RESPALDO_UNIDADES[moneda], f"{num_es(RESPALDO_UNIDADES[moneda])} {moneda} (sin precio para convertir)"
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


# ------------------------------------------------------------- la detección

def redactar(a):
    """Título y cuerpo del aviso. Redacción prudente: el dato, no la acusación."""
    signo = "+" if a["delta"] > 0 else ""
    monto = f"{signo}{a['delta']:,.8f} {a['moneda']}"
    titulo = f"Movimiento: {a['red']} {a['abreviada']} {monto} {a['fecha']}"
    usd = f" (≈US$ {a['valor_usd']:,.2f})" if a.get("valor_usd") is not None else ""
    rol = f", rol declarado: {a['rol']}" if a.get("rol") else ""
    cuerpo = "\n".join([
        f"**{a['etiqueta']}** (tipo `{a['tipo']}`{rol}).",
        "",
        f"- Red: **{a['red']}**",
        f"- Dirección: `{a['direccion']}`",
        f"- Cambio: **{monto}**{usd}",
        f"- Saldo antes: {a['saldo_antes']:,.8f} {a['moneda']}",
        f"- Saldo después: {a['saldo_despues']:,.8f} {a['moneda']}",
        f"- Detectado: {a['fecha']} (comparando dos chequeos horarios del monitor)",
        f"- Por qué se avisa: {a['motivo']}",
        f"- Explorador: {a['explorador']}",
        f"- Monitor: {a['monitor']}",
        "",
        FRASE,
    ])
    return titulo, cuerpo


def detectar(anterior, actual, registros):
    """Lista de alertas comparando dos data.json."""
    umbrales = umbrales_config()
    precios = actual.get("precios") or {}
    fecha = actual.get("actualizado") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    previas = {krd(b["red"], b["direccion"]): b for b in anterior.get("billeteras", []) if b.get("red") and b.get("direccion")}
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
        sa, sd = saldos(antes), saldos(fila)
        for moneda in sorted(set(sa) & set(sd)):
            a0, a1 = sa[moneda], sd[moneda]
            if a0 is None or a1 is None:
                continue
            d = a1 - a0
            if abs(d) <= RUIDO:
                continue
            umbral, texto_umbral = umbral_de(moneda, precios, umbrales)
            salida_frio = frio and d < 0
            if not salida_frio and (umbral is None or abs(d) < umbral):
                continue
            usd_unit = (precios.get(moneda) or {}).get("usd")
            if usd_unit is None and moneda in ("USDT", "USDC"):
                usd_unit = 1.0
            que_es = "atribuida" if (reg or {}).get("tipo") == "atribuida" else "de desvío"
            motivo = (f"salida desde una dirección {que_es} con rol de almacenamiento en frío: se avisa sin umbral"
                      if salida_frio else f"el cambio supera el umbral de aviso de la red ({texto_umbral})")
            alerta = {
                "fecha": fecha,
                "red": fila["red"],
                "direccion": fila["direccion"],
                "abreviada": corto(fila["direccion"]),
                "etiqueta": (reg or {}).get("etiqueta_publica") or fila.get("etiqueta") or "dirección vigilada",
                "tipo": fila.get("tipo") or (reg or {}).get("tipo") or "vigilada",
                "rol": (reg or {}).get("rol"),
                "moneda": moneda,
                "delta": round(d, 8),
                "saldo_antes": a0,
                "saldo_despues": a1,
                "valor_usd": round(abs(d) * usd_unit, 2) if usd_unit else None,
                "motivo": motivo,
                "frio": bool(salida_frio),
                "explorador": EXPLORER[fila["red"]].format(a=fila["direccion"]),
                "monitor": MONITOR_URL,
            }
            alerta["titulo"], alerta["cuerpo"] = redactar(alerta)
            alertas.append(alerta)
    return alertas


def clave_alerta(a):
    return (a.get("red"), a.get("direccion"), a.get("moneda"), a.get("saldo_antes"), a.get("saldo_despues"))


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
        "umbrales": {"unidades": umbrales_config(), "usd": UMBRAL_USD,
                     "nota": "Salidas desde almacenamiento en frío (desvío o atribuida) se avisan sin umbral."},
        "alertas": (frescas + previas)[:MAX_ALERTAS],
    }
    Path(ruta).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frescas


# ------------------------------------------------------------------- avisos

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
