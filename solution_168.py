import os
import requests
from decimal import Decimal

# ------------------- CONFIGURATION -------------------
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")  # set your Etherscan API key in the environment
TARGET_ADDRESS = "0x74aa5387681505c806ff1e972b12cdfd01406828".lower()
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48".lower()
TARGET_AMOUNT = Decimal("-1007676.08328900")  # USDC (6 decimals)
# -----------------------------------------------------


def get_erc20_transfers(address: str, start_block: int = 0, end_block: int = 99999999):
    """
    Pull ERC‑20 token transfer events for an address using the Etherscan API.
    """
    url = "https://api.etherscan.io/api"
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": start_block,
        "endblock": end_block,
        "sort": "asc",
        "apikey": ETHERSCAN_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data["status"] != "1":
        raise RuntimeError(f"Etherscan error: {data.get('message')}")
    return data["result"]


def usdc_value(value_str: str) -> Decimal:
    """Convert raw token amount (as string) to USDC decimal representation (6 decimals)."""
    return Decimal(value_str) / Decimal(10**6)


def find_destination(transfers):
    """
    Locate the transaction where TARGET_ADDRESS sent exactly TARGET_AMOUNT USDC.
    Returns a tuple (tx_hash, to_address, block_number) or None.
    """
    for tx in transfers:
        if tx["contractAddress"].lower() != USDC_CONTRACT:
            continue
        from_addr = tx["from"].lower()
        to_addr = tx["to"].lower()
        amount = usdc_value(tx["value"])
        # Etherscan lists outgoing transfers with a negative sign in the UI,
        # but the raw API always returns a positive number.
        if from_addr == TARGET_ADDRESS and amount == -TARGET_AMOUNT:
            return tx["hash"], to_addr, int(tx["blockNumber"])
    return None


def main():
    if not ETHERSCAN_API_KEY:
        raise EnvironmentError("Set the ETHERSCAN_API_KEY environment variable.")
    print(f"Fetching ERC‑20 transfers for {TARGET_ADDRESS} ...")
    transfers = get_erc20_transfers(TARGET_ADDRESS)
    result = find_destination(transfers)

    if result:
        tx_hash, dest, block = result
        print("\n=== Match found ===")
        print(f"Transaction hash : {tx_hash}")
        print(f"Destination      : {dest}")
        print(f"Block number     : {block}")
        print(f"Amount transferred: {abs(TARGET_AMOUNT)} USDC")
    else:
        print("\nNo matching USDC transfer of the specified amount was found.")


if __name__ == "__main__":
    main()