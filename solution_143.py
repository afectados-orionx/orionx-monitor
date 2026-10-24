"""
Descubierta: destino de una salida (tipo "descubierta")
=====================================================

Este script consulta la blockchain de Ethereum para obtener todas las transferencias
de USDC (ERC‑20) asociadas a una dirección y calcula el balance neto (entrada‑salida).
Se usa la API pública de Etherscan; necesitas una API‑Key (gratuita al registrarte).

Requisitos:
    pip install requests

Uso:
    python usdc_flow.py <ETH_ADDRESS>
"""

import sys
import json
import time
from decimal import Decimal
from typing import List, Dict

import requests

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
ETHERSCAN_API_KEY = "YOUR_ETHERSCAN_API_KEY"   # <-- REEMPLAZA AQUÍ
ETHERSCAN_BASE_URL = "https://api.etherscan.io/api"

# Dirección del contrato USDC en mainnet
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9EB0cE3606EB48"

# Número de decimales de USDC (6)
USDC_DECIMALS = 6


# ----------------------------------------------------------------------
# Funciones auxiliares
# ----------------------------------------------------------------------
def etherscan_get(url: str, params: dict) -> dict:
    """Realiza una petición GET a Etherscan y devuelve el JSON decodificado."""
    params["apikey"] = ETHERSCAN_API_KEY
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("status") not in ("1", "0"):
        raise RuntimeError(f"Etherscan error: {data.get('message')}")
    return data


def get_usdc_transfers(address: str, start_block: int = 0, end_block: int = 99999999) -> List[Dict]:
    """
    Obtiene todas las transferencias de USDC (ERC‑20) para `address`.
    Usa el endpoint `tokentx` de Etherscan.
    """
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "contractaddress": USDC_CONTRACT,
        "startblock": start_block,
        "endblock": end_block,
        "page": 1,
        "offset": 10000,          # máximo permitido por petición
        "sort": "asc",
    }

    data = etherscan_get(ETHERSCAN_BASE_URL, params)
    return data.get("result", [])


def format_usdc(value_wei: str) -> Decimal:
    """Convierte el valor bruto (string) a USDC con los decimales correctos."""
    return Decimal(value_wei) / (10 ** USDC_DECIMALS)


def summarize_usdc_flow(transfers: List[Dict], target_address: str) -> Dict:
    """
    Calcula el total de USDC enviados y recibidos por `target_address`.
    Devuelve un dict con:
        - total_in:  Decimal
        - total_out: Decimal
        - net_change: Decimal  (in - out)
    """
    total_in = Decimal(0)
    total_out = Decimal(0)

    for tx in transfers:
        # Etherscan devuelve los campos como strings
        value = format_usdc(tx["value"])
        # Determinamos la dirección del remitente y del destinatario
        from_addr = tx["from"].lower()
        to_addr   = tx["to"].lower()
        if to_addr == target_address.lower():
            total_in += value
        if from_addr == target_address.lower():
            total_out += value

    net_change = total_in - total_out
    return {
        "total_in": total_in,
        "total_out": total_out,
        "net_change": net_change,
    }


def main():
    if len(sys.argv) != 2:
        print("Uso: python usdc_flow.py <ETH_ADDRESS>")
        sys.exit(1)

    address = sys.argv[1]
    print(f"\nConsultando transferencias USDC para la dirección {address} ...\n")

    try:
        transfers = get_usdc_transfers(address)
        if not transfers:
            print("No se encontraron transferencias USDC para esta dirección.")
            return

        summary = summarize_usdc_flow(transfers, address)

        # Presentación de resultados
        print("Resumen de flujo USDC")
        print("----------------------")
        print(f"Entradas  (USDC recibidos) : {summary['total_in']:.6f}")
        print(f"Salidas   (USDC enviados) : {summary['total_out']:.6f}")
        print(f"Balance neto (in - out)   : {summary['net_change']:.6f} USDC")
        print("\nDetalle de transferencias (últimas 10):")
        for tx in transfers[-10:]:
            direction = "→" if tx["from"].lower() == address.lower() else "←"
            amount = format_usdc(tx["value"])
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(tx["timeStamp"])))
            print(f"{ts}  {direction}  {amount:.6f} USDC  (txHash={tx['hash'][:12]}...)")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()