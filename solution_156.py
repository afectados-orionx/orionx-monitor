"""
Script to investigate the USDC token activity of an Ethereum address.

Features:
- Retrieves the current USDC balance of the target address.
- Lists recent USDC token transfers involving the address.
- Calculates the net USDC change over the fetched transfer window.

Requirements:
    pip install requests

Replace `YOUR_ETHERSCAN_API_KEY` with a valid Etherscan API key.
"""

import requests
from decimal import Decimal
from datetime import datetime

# -------------------------- Configuration -------------------------- #
ETHERSCAN_API_KEY = "YOUR_ETHERSCAN_API_KEY"          # <-- replace this
TARGET_ADDRESS = "0x74aa5387681505c806ff1e972b12cdfd01406828".lower()
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48".lower()
# Number of recent token transfer events to fetch (max 1000)
TX_LIMIT = 100
# ------------------------------------------------------------------ #


def etherscan_get(endpoint: str, params: dict) -> dict:
    """Helper to call the Etherscan API and return the JSON response."""
    base_url = "https://api.etherscan.io/api"
    params.update({"module": endpoint.split("/")[0], "action": endpoint.split("/")[1], "apikey": ETHERSCAN_API_KEY})
    resp = requests.get(base_url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") not in ("1", "0"):
        raise RuntimeError(f"Etherscan error: {data.get('message')}")
    return data


def get_usdc_balance(address: str) -> Decimal:
    """Return the USDC token balance (as a Decimal) for the given address."""
    data = etherscan_get(
        "account/tokenbalance",
        {
            "contractaddress": USDC_CONTRACT,
            "address": address,
            "tag": "latest",
        },
    )
    # USDC uses 6 decimal places
    raw_balance = Decimal(data.get("result", "0"))
    return raw_balance / Decimal(10 ** 6)


def get_recent_usdc_transfers(address: str, limit: int = 100) -> list:
    """
    Return a list of recent USDC token transfer dicts involving the address.
    Each dict contains: blockNumber, timeStamp, hash, from, to, value (USDC).
    """
    data = etherscan_get(
        "account/tokentx",
        {
            "contractaddress": USDC_CONTRACT,
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": "desc",
        },
    )
    transfers = []
    for tx in data.get("result", []):
        # Normalize fields
        transfers.append(
            {
                "block": int(tx["blockNumber"]),
                "timestamp": datetime.utcfromtimestamp(int(tx["timeStamp"])),
                "tx_hash": tx["hash"],
                "from": tx["from"].lower(),
                "to": tx["to"].lower(),
                "value": Decimal(tx["value"]) / Decimal(10 ** 6),  # USDC has 6 decimals
            }
        )
    return transfers


def compute_net_change(transfers: list, address: str) -> Decimal:
    """Calculate net USDC change for the address over the provided transfers."""
    net = Decimal(0)
    for tx in transfers:
        if tx["to"] == address:
            net += tx["value"]      # incoming
        elif tx["from"] == address:
            net -= tx["value"]      # outgoing
    return net


def main():
    print(f"Analyzing USDC activity for address: {TARGET_ADDRESS}\n")

    # 1️⃣ Current USDC balance
    balance = get_usdc_balance(TARGET_ADDRESS)
    print(f"Current USDC balance: {balance:,.6f} USDC\n")

    # 2️⃣ Recent transfers
    transfers = get_recent_usdc_transfers(TARGET_ADDRESS, TX_LIMIT)
    if not transfers:
        print("No recent USDC transfers found.")
        return

    print(f"Last {len(transfers)} USDC transfers (newest first):")
    for tx in transfers[:5]:  # show a few examples
        direction = "IN" if tx["to"] == TARGET_ADDRESS else "OUT"
        print(
            f"{tx['timestamp'].isoformat()} | {direction} | "
            f"{tx['value']:.6f} USDC | TxHash: {tx['tx_hash'][:10]}..."
        )
    print("...")

    # 3️⃣ Net change over the fetched window
    net_change = compute_net_change(transfers, TARGET_ADDRESS)
    sign = "+" if net_change >= 0 else "-"
    print(f"\nNet USDC change over the last {len(transfers)} transfers: {sign}{abs(net_change):,.6f} USDC")

    # 4️⃣ Simple sanity check against the displayed "Cambio" in the task description
    # (the task mentions a change of -147,788.00408100 USDC)
    expected_change = Decimal("-147788.00408100")
    diff = net_change - expected_change
    print(f"Difference from reported change ({expected_change} USDC): {diff:.6f} USDC")


if __name__ == "__main__":
    main()