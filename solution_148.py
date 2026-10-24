import re
from decimal import Decimal

def parse_transaction(text):
    """
    Parse a transaction description in Spanish and extract network, address,
    change amount (USDC) and the approximate USD value.

    Example input:
        Task:**Descubierta: destino de una salida** (tipo `descubierta`).
        - Red: **ETH**
        - Dirección: `0x74aa5387681505c806ff1e972b12cdfd01406828`
        - Cambio: **-965,498.22145200 USDC** (≈US$ 965,367.88)
        - Saldo anterior: ...

    Returns a dict with keys:
        network, address, change_usdc (Decimal), approx_usd (Decimal or None)
    """
    result = {
        "network": None,
        "address": None,
        "change_usdc": None,
        "approx_usd": None,
    }

    # Network
    net_match = re.search(r"-\s*Red:\s*\*\*(\w+)\*\*", text, re.IGNORECASE)
    if net_match:
        result["network"] = net_match.group(1)

    # Address (hex string inside backticks)
    addr_match = re.search(r"-\s*Dirección:\s*`([^`]+)`", text, re.IGNORECASE)
    if addr_match:
        result["address"] = addr_match.group(1).strip()

    # Change amount (USDC) – may contain commas as thousand separators
    change_match = re.search(r"-\s*Cambio:\s*\*\*([-\d.,]+)\s*USDC\*\*", text, re.IGNORECASE)
    if change_match:
        raw_amount = change_match.group(1).replace(",", "")
        try:
            result["change_usdc"] = Decimal(raw_amount)
        except Exception:
            pass

    # Approximate USD value inside parentheses (≈US$ 965,367.88)
    usd_match = re.search(r"\(≈US\$\s*([-\d.,]+)\)", text)
    if usd_match:
        raw_usd = usd_match.group(1).replace(",", "")
        try:
            result["approx_usd"] = Decimal(raw_usd)
        except Exception:
            pass

    return result

# Example usage
if __name__ == "__main__":
    sample_text = """
    Task:**Descubierta: destino de una salida** (tipo `descubierta`).

    - Red: **ETH**
    - Dirección: `0x74aa5387681505c806ff1e972b12cdfd01406828`
    - Cambio: **-965,498.22145200 USDC** (≈US$ 965,367.88)
    - Saldo anterior: 1,200,000 USDC
    """
    parsed = parse_transaction(sample_text)
    print(parsed)