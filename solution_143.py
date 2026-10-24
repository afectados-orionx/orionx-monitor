import re
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class TransactionInfo:
    task_type: str
    network: str
    address: str
    change_amount: float
    change_currency: str
    approx_usd: float
    balance_after: Optional[float] = None

def parse_transaction(text: str) -> TransactionInfo:
    # Detect task type (e.g., "Descubierta")
    task_match = re.search(r'Task:\*{0,2}([^*]+)\*{0,2}', text, re.IGNORECASE)
    task_type = task_match.group(1).strip() if task_match else "unknown"

    # Network
    network_match = re.search(r'Red:\s*\*\*(\w+)\*\*', text)
    network = network_match.group(1).strip() if network_match else ""

    # Address (Ethereum)
    address_match = re.search(r'Dirección:\s*`([^`]+)`', text)
    address = address_match.group(1).strip() if address_match else ""

    # Change amount and currency
    change_match = re.search(r'Cambio:\s*\*\*([-\d,.]+)\s*([A-Z]+)\*\*', text)
    if change_match:
        amount_str = change_match.group(1).replace(',', '')
        change_amount = float(amount_str)
        change_currency = change_match.group(2)
    else:
        change_amount = 0.0
        change_currency = ""

    # Approximate USD value
    usd_match = re.search(r'≈US\$\s*([\d,.]+)', text)
    approx_usd = float(usd_match.group(1).replace(',', '')) if usd_match else 0.0

    # Balance after (optional, may be split across lines)
    balance_match = re.search(r'Saldo\s+([-\d,.]+)', text)
    balance_after = float(balance_match.group(1).replace(',', '')) if balance_match else None

    return TransactionInfo(
        task_type=task_type,
        network=network,
        address=address,
        change_amount=change_amount,
        change_currency=change_currency,
        approx_usd=approx_usd,
        balance_after=balance_after
    )

def summarize_transaction(info: TransactionInfo) -> str:
    direction = "outgoing" if info.change_amount < 0 else "incoming"
    return (f"{info.task_type} transaction on {info.network} network:\n"
            f"  Address: {info.address}\n"
            f"  Direction: {direction}\n"
            f"  Amount: {abs(info.change_amount):,.6f} {info.change_currency}\n"
            f"  Approx. USD: ${info.approx_usd:,.2f}\n"
            f"  Balance after: {info.balance_after if info.balance_after is not None else 'N/A'}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Read from file if provided
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            raw_text = f.read()
    else:
        # Read from stdin
        raw_text = sys.stdin.read()
    tx_info = parse_transaction(raw_text)
    print(summarize_transaction(tx_info))