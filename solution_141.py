import re
from typing import Dict, Any


def parse_transaction(text: str) -> Dict[str, Any]:
    """
    Parse a transaction description in Spanish and extract:
        - network (Red)
        - address (Dirección)
        - change amount in USDC
        - approximate USD value

    Parameters
    ----------
    text : str
        Multiline string containing the transaction description.

    Returns
    -------
    dict
        Dictionary with the extracted fields. Missing fields are omitted.
    """
    result: Dict[str, Any] = {}

    # Network (Red)
    net_match = re.search(r"Red:\s*\*\*(.+?)\*\*", text, re.IGNORECASE)
    if net_match:
        result["network"] = net_match.group(1).strip()

    # Address (Dirección)
    addr_match = re.search(r"Dirección:\s*`([^`]+)`", text, re.IGNORECASE)
    if addr_match:
        result["address"] = addr_match.group(1).strip()

    # Change amount in USDC (Cambio)
    change_match = re.search(r"Cambio:\s*\*\*([-\d,\.]+)\s*USDC\*\*", text, re.IGNORECASE)
    if change_match:
        # Remove thousands separators and convert to float
        amount_str = change_match.group(1).replace(",", "")
        result["change_usdc"] = float(amount_str)

    # Approximate USD value (≈US$ ...)
    usd_match = re.search(r"\(≈US\$\s*([\d,\.]+)\)", text)
    if usd_match:
        usd_str = usd_match.group(1).replace(",", "")
        result["approx_usd"] = float(usd_str)

    return result


# ----------------------------------------------------------------------
# Example usage
if __name__ == "__main__":
    sample_text = """
    Task:**Descubierta: destino de una salida** (tipo `descubierta`).

    - Red: **ETH**
    - Dirección: `0x58b704065b7aff3ed351052f8560019e05925023`
    - Cambio: **-100,453.21000000 USDC** (≈US$ 100,411.02)
    - Saldo an
    """

    parsed = parse_transaction(sample_text)
    print(parsed)
    # Expected output:
    # {
    #   'network': 'ETH',
    #   'address': '0x58b704065b7aff3ed351052f8560019e05925023',
    #   'change_usdc': -100453.21000000,
    #   'approx_usd': 100411.02
    # }