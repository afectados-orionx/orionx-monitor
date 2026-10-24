import re
from decimal import Decimal

def parse_transaction(text: str) -> dict:
    """
    Parse a transaction description like:

        Task:**Descubierta: destino de una salida** (tipo `descubierta`).

        - Red: **ETH**
        - Dirección: `0x58b704065b7aff3ed351052f8560019e05925023`
        - Cambio: **-404,108.70301400 USDC** (≈US$ 403,908.27)
        - Saldo an ...

    Returns a dictionary with the extracted fields.
    """
    result = {}

    # Network (Red)
    net_match = re.search(r"-\s*Red:\s*\*\*(\w+)\*\*", text)
    if net_match:
        result["network"] = net_match.group(1)

    # Address (Dirección)
    addr_match = re.search(r"-\s*Dirección:\s*`([^`]+)`", text)
    if addr_match:
        result["address"] = addr_match.group(1)

    # Amount (Cambio) – may contain commas as thousand separators
    amount_match = re.search(
        r"-\s*Cambio:\s*\*\*([-\d,\.]+)\s+([A-Z]{3,5})\*\*\s*\(≈US\$\s*([\d,\.]+)\)", text
    )
    if amount_match:
        raw_amount, token, approx_usd = amount_match.groups()
        # Normalise the numeric strings (remove commas)
        amount = Decimal(raw_amount.replace(",", ""))
        usd = Decimal(approx_usd.replace(",", ""))
        result["change"] = {
            "raw": raw_amount,
            "value": amount,
            "token": token,
            "approx_usd": usd,
        }

    # Optional: capture any trailing "Saldo ..." line
    saldo_match = re.search(r"-\s*Saldo\s+(.*)", text)
    if saldo_match:
        result["saldo"] = saldo_match.group(1).strip()

    return result


# ----------------------------------------------------------------------
# Example usage
if __name__ == "__main__":
    sample_text = """
    Task:**Descubierta: destino de una salida** (tipo `descubierta`).

    - Red: **ETH**
    - Dirección: `0x58b704065b7aff3ed351052f8560019e05925023`
    - Cambio: **-404,108.70301400 USDC** (≈US$ 403,908.27)
    - Saldo an
    """

    parsed = parse_transaction(sample_text)
    print("Parsed transaction data:")
    for k, v in parsed.items():
        print(f"{k}: {v}")

    # Simple sanity check: compare token amount vs approx USD (USDC ~ 1:1)
    if "change" in parsed:
        token_amount = parsed["change"]["value"]
        approx_usd = parsed["change"]["approx_usd"]
        diff = approx_usd - token_amount
        print(f"\nDifference between USDC amount and approx USD: {diff:.2f}")