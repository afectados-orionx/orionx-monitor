#!/usr/bin/env python3
"""Valida direcciones.json (la fuente unica de direcciones).
Pensado para correr en cada Pull Request.

Sale con codigo != 0 y lista todos los problemas si algo no cuadra.

Uso:  python scripts/validate_data.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REDES = {"BTC", "XRP", "TRX", "LTC", "ETH", "BSC", "POLYGON"}
EVM = {"ETH", "BSC", "POLYGON"}
ESTADOS = {"monitor", "evaluacion", "relacionada", "descartada"}
TIPOS = {"orionx", "desvio", "querella", "puente", "atribuida"}
MONEDAS = {"BTC", "XRP", "TRX", "LTC", "ETH", "BNB", "POL", "USDT", None}
CAMPOS_TEXTO = ("etiqueta", "nota", "origen", "rol", "confianza", "evidencia",
                "nota_original", "seccion", "etiqueta_publica", "motivo",
                "estaba_como", "retirada")
RE_EVM = re.compile(r"^0x[0-9a-f]{40}$")


def validar_direcciones(doc, err):
    if not isinstance(doc, dict) or not isinstance(doc.get("direcciones"), list):
        err.append("direcciones.json: falta el array 'direcciones'")
        return []
    regs = doc["direcciones"]
    vistas = {}
    for i, r in enumerate(regs):
        et = f"direcciones[{i}] ({r.get('red')} {str(r.get('direccion'))[:16]})"

        red = r.get("red")
        if red not in REDES:
            err.append(f"{et}: red invalida {red!r}")

        d = r.get("direccion")
        if not isinstance(d, str) or not d:
            err.append(f"{et}: direccion vacia")
        elif red in EVM and not RE_EVM.match(d):
            err.append(f"{et}: direccion EVM debe ser ^0x[0-9a-f]{{40}}$ (minusculas)")

        k = (red, d)
        if k in vistas:
            err.append(f"{et}: duplicada, ya aparece en direcciones[{vistas[k]}]")
        vistas[k] = i

        mon, des = r.get("monitorear"), r.get("descartada")
        if not isinstance(mon, bool) or not isinstance(des, bool):
            err.append(f"{et}: monitorear y descartada deben ser true/false")
        if mon and des:
            err.append(f"{et}: no puede ser monitorear y descartada a la vez")

        est = r.get("estado")
        if est not in ESTADOS:
            err.append(f"{et}: estado invalido {est!r}")
        if mon is True and est != "monitor":
            err.append(f"{et}: monitorear=true exige estado='monitor'")
        if mon is False and est == "monitor":
            err.append(f"{et}: estado='monitor' exige monitorear=true")
        if des is True and est != "descartada":
            err.append(f"{et}: descartada=true exige estado='descartada'")

        if des and not (r.get("motivo") or "").strip():
            err.append(f"{et}: una direccion descartada necesita 'motivo'")

        if mon:
            if not (r.get("etiqueta") or "").strip():
                err.append(f"{et}: monitorear=true necesita 'etiqueta'")
            if r.get("tipo") not in TIPOS:
                err.append(f"{et}: monitorear=true necesita tipo valido {sorted(TIPOS)}")
            if not isinstance(r.get("vigilar"), bool):
                err.append(f"{et}: monitorear=true necesita 'vigilar' true/false")
            if not isinstance(r.get("nota"), str):
                err.append(f"{et}: monitorear=true necesita 'nota' (texto, puede ser \"\")")

        if r.get("moneda") not in MONEDAS:
            err.append(f"{et}: moneda invalida {r.get('moneda')!r}")

        so = r.get("saldo_observado")
        if so is not None and not isinstance(so, (int, float)):
            err.append(f"{et}: saldo_observado debe ser numero o null")

        for campo in CAMPOS_TEXTO:
            v = r.get(campo)
            if isinstance(v, str) and ("<" in v or ">" in v):
                err.append(f"{et}: campo '{campo}' contiene '<' o '>' (riesgo XSS en la web)")

    return regs


def main():
    err = []
    try:
        doc = json.loads((ROOT / "direcciones.json").read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        sys.exit(f"direcciones.json no es JSON valido: {e}")

    regs = validar_direcciones(doc, err)

    if not (doc.get("fuente") or "").strip():
        err.append("direcciones.json: falta el metadato 'fuente' (lo muestra la web)")

    if err:
        print(f"{len(err)} problema(s):")
        for x in err:
            print("  - " + x)
        sys.exit(1)

    mon = sum(1 for r in regs if r["monitorear"])
    des = sum(1 for r in regs if r["descartada"])
    print(f"OK: {len(regs)} direcciones ({mon} en monitor, {des} descartadas), "
          f"sin duplicados, sin HTML en textos.")


if __name__ == "__main__":
    main()
