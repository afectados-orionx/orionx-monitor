import re
import sys

def parse_transaction(text):
    result = {}

    # Red (network)
    network_match = re.search(r'Red:\s*\*\*(\w+)\*\*', text)
    if network_match:
        result['network'] = network_match.group(1)

    # Dirección (address)
    address_match = re.search(r'Dirección:\s*`([^`]+)`', text)
    if address_match:
        result['address'] = address_match.group(1)

    # Cambio (change amount)
    change_match = re.search(r'Cambio:\s*\*\*([-\d.,]+)\s*USDC\*\*', text)
    if change_match:
        # Normalize number (remove commas, keep dot as decimal separator)
        amount_str = change_match.group(1).replace(',', '')
        try:
            result['change_usdc'] = float(amount_str)
        except ValueError:
            result['change_usdc'] = amount_str

    # Saldo (balance) if present
    balance_match = re.search(r'Saldo\s*([-\d.,]+)\s*USDC', text, re.IGNORECASE)
    if balance_match:
        bal_str = balance_match.group(1).replace(',', '')
        try:
            result['balance_usdc'] = float(bal_str)
        except ValueError:
            result['balance_usdc'] = bal_str

    return result

if __name__ == "__main__":
    input_text = sys.stdin.read()
    parsed = parse_transaction(input_text)
    for key, value in parsed.items():
        print(f"{key}: {value}")