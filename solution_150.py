import requests
from decimal import Decimal

# ------------------- CONFIGURATION -------------------
ETHERSCAN_API_KEY = "YOUR_ETHERSCAN_API_KEY"   # <-- replace with your Etherscan API key
ADDRESS = "0x58b704065b7aff3ed351052f8560019e05925023"
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
# -----------------------------------------------------

def get_usdc_transfers(address: str, startblock: int = 0, endblock: int = 99999999) -> list:
    """
    Retrieve USDC token transfer events for the given address using Etherscan API.
    """
    url = (
        "https://api.etherscan.io/api"
        "?module=account"
        "&action=tokentx"
        f"&address={address}"
        f"&startblock={startblock}"
        f"&endblock={endblock}"
        "&page=1"
        "&offset=10000"
        "&sort=desc"
        f"&apikey={ETHERSCAN_API_KEY}"
    )
    resp = requests.get(url, timeout=30)
    data = resp.json()
    if data.get("status") != "1":
        raise RuntimeError(f"Etherscan error: {data.get('message')}")
    return [tx for tx in data["result"] if tx["contractAddress"].lower() == USDC_CONTRACT.lower()]

def format_usdc(value_str: str) -> Decimal:
    """USDC has 6 decimals."""
    return Decimal(value_str) / Decimal(10**6)

def main():
    transfers = get_usdc_transfers(ADDRESS)

    # Filter only outgoing transfers (negative change)
    outgoing = [
        tx for tx in transfers
        if tx["from"].lower() == ADDRESS.lower()
    ]

    if not outgoing:
        print("No outgoing USDC transfers found for the address.")
        return

    print(f"Found {len(outgoing)} outgoing USDC transfer(s):\n")
    for tx in outgoing:
        to_addr = tx["to"]
        amount = format_usdc(tx["value"])
        tx_hash = tx["hash"]
        block = tx["blockNumber"]
        timestamp = int(tx["timeStamp"])
        print(
            f"TxHash   : {tx_hash}\n"
            f"Block    : {block}\n"
            f"Timestamp: {timestamp}\n"
            f"To       : {to_addr}\n"
            f"Amount   : {amount} USDC\n"
            f"{'-'*40}"
        )

if __name__ == "__main__":
    main()