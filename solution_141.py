import re
from typing import Dict, Any

def parse_transaction(text: str) -> Dict[str, Any]:
    """
    Parse a transaction description in Spanish and extract key information.

    Expected fields:
    - Red (Network)
    - Dirección (Address)
    - Cambio (Change amount with token)
    - Approximate USD value (if present)

    Returns a dictionary with the extracted data.
    """
    result = {}

    # Network
    net_match = re.search(r'Red:\s*\*\*(\w+)\*\*', text, re.IGNORECASE)
    if net_match:
        result['network'] = net_match.group(1)

    # Address
    addr_match = re.search(r'Dirección:\s*`([^`]+)`', text, re.IGNORECASE)
    if addr_match:
        result['address'] = addr_match.group(1)

    # Change amount and token
    change_match = re.search(r'Cambio:\s*\*\*([-\d.,]+)\s*([A-Z]+)\*\*', text, re.IGNORECASE)
    if change_match:
        raw_amount = change_match.group(1).replace(',', '')
        try:
            amount = float(raw_amount)
        except ValueError:
            amount = None
        result['change'] = {
            'amount': amount,
            'token': change_match.group(2)
        }

    # Approximate USD value
    usd_match = re.search(r'≈US\$\s*([\d.,]+)', text, re.IGNORECASE)
    if usd_match:
        usd_raw = usd_match.group(1).replace(',', '')
        try:
            result['approx_usd'] = float(usd_raw)
        except ValueError:
            result['approx_usd'] = None

    return result

# Example usage
if __name__ == "__main__":
    sample_text = """Task:**Descubierta: destino de una salida** (tipo `descubierta`).

- Red: **ETH**
- Dirección: `0x58b704065b7aff3ed351052f8560019e05925023`
- Cambio: **-100,453.21000000 USDC** (≈US$ 100,411.02)
- Saldo an"""
    parsed = parse_transaction(sample_text)
    print(parsed)