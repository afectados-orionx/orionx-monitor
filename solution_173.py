import os
import json
import requests
from decimal import Decimal
from web3 import Web3

# -------------------------------------------------
# Configuration
# -------------------------------------------------
ETH_RPC_URL = os.getenv("ETH_RPC_URL", "https://rpc.ankr.com/eth")  # public RPC; replace with your own if needed
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")                # get one from https://etherscan.io/apis
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"     # USDC mainnet contract address
ADDRESS = "0x74aa5387681505c806ff1e972b12cdfd01406828".lower()

# -------------------------------------------------
# Helper: ERC‑20 ABI (only the parts we need)
# -------------------------------------------------
ERC20_ABI = json.loads("""[
    {"constant":true,"inputs":[{"name":"_owner","type":"address"}],
     "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],
     "type":"function"},
    {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],
     "type":"function"},
    {"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],
     "type":"function"}
]""")

# -------------------------------------------------
# Initialize Web3
# -------------------------------------------------
w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))
if not w3.isConnected():
    raise ConnectionError("Unable to connect to Ethereum RPC endpoint")

# -------------------------------------------------
# Contract instance
# -------------------------------------------------
usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_CONTRACT), abi=ERC20_ABI)

# -------------------------------------------------
# Fetch token decimals & symbol (cached)
# -------------------------------------------------
DECIMALS = usdc.functions.decimals().call()
SYMBOL   = usdc.functions.symbol().call()

# -------------------------------------------------
# Function: get USDC balance for an address
# -------------------------------------------------
def get_usdc_balance(address: str) -> Decimal:
    """Return the USDC balance of `address` as a Decimal with proper scaling."""
    raw = usdc.functions.balanceOf(Web3.to_checksum_address(address)).call()
    return Decimal(raw) / (Decimal(10) ** DECIMALS)

# -------------------------------------------------
# Function: fetch token transfer events (Etherscan)
# -------------------------------------------------
def get_usdc_transfers(address: str, start_block: int = 0, end_block: int = 99999999):
    """
    Retrieve USDC Transfer events involving `address` using Etherscan API.
    Returns a list of dicts with keys: tx_hash, block_number, from, to, value (Decimal).
    """
    url = "https://api.etherscan.io/api"
    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": USDC_CONTRACT,
        "address": address,
        "startblock": start_block,
        "endblock": end_block,
        "page": 1,
        "offset": 10000,
        "sort": "asc",
        "apikey": ETHERSCAN_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data["status"] != "1":
        return []  # no transfers or API limit reached
    transfers = []
    for tx in data["result"]:
        transfers.append({
            "tx_hash": tx["hash"],
            "block_number": int(tx["blockNumber"]),
            "from": tx["from"].lower(),
            "to": tx["to"].lower(),
            "value": Decimal(tx["value"]) / (Decimal(10) ** DECIMALS),
            "timestamp": int(tx["timeStamp"])
        })
    return transfers

# -------------------------------------------------
# Example usage
# -------------------------------------------------
if __name__ == "__main__":
    # 1️⃣ Current USDC balance
    balance = get_usdc_balance(ADDRESS)
    print(f"Current USDC balance of {ADDRESS}: {balance:.6f} {SYMBOL}")

    # 2️⃣ Recent transfers (last 10 000 txs, adjust as needed)
    transfers = get_usdc_transfers(ADDRESS)
    print(f"\nFound {len(transfers)} USDC transfer(s) involving the address.\n")

    # 3️⃣ Detect large outbound transfers (threshold = 500 000 USDC)
    THRESHOLD = Decimal("500000")
    large_outbound = [
        tx for tx in transfers
        if tx["from"] == ADDRESS and tx["value"] >= THRESHOLD
    ]

    if large_outbound:
        print("⚠️ Large outbound USDC transfers detected:")
        for tx in large_outbound:
            print(f"- Tx {tx['tx_hash'][:10]}… | Block {tx['block_number']} | "
                  f"-{tx['value']:,} {SYMBOL}")
    else:
        print("No large outbound USDC transfers (≥ 500 000) found.")