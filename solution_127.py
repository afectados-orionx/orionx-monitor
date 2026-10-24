import os
import requests
from decimal import Decimal, getcontext

# Set precision for Decimal calculations
getcontext().prec = 30

# ---- Configuration ----
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "YourEtherscanAPIKey")
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"  # USDC token contract on Ethereum
ADDRESS = "0x74aa5387681505c806ff1e972b12cdfd01406828"
CHANGE_USDC = Decimal("-407295.98863100")  # Change amount in USDC (negative for outflow)

# ---- Helper Functions ----
def get_usdc_balance(address: str) -> Decimal:
    """
    Retrieves the USDC token balance for a given Ethereum address using Etherscan API.
    Returns the balance as a Decimal in standard USDC units (6 decimal places).
    """
    url = "https://api.etherscan.io/api"
    params = {
        "module": "account",
        "action": "tokenbalance",
        "contractaddress": USDC_CONTRACT,
        "address": address,
        "tag": "latest",
        "apikey": ETHERSCAN_API_KEY,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if data["status"] != "1":
        raise ValueError(f"Etherscan error: {data.get('message', 'Unknown error')}")

    # Etherscan returns balance in the token's smallest unit (USDC has 6 decimals)
    raw_balance = Decimal(data["result"])
    return raw_balance.scaleb(-6)  # Convert to standard USDC amount

def format_decimal(value: Decimal) -> str:
    """Format Decimal to string with 6 decimal places (USDC standard)."""
    return f"{value:.6f}"

# ---- Main Logic ----
def main():
    try:
        old_balance = get_usdc_balance(ADDRESS)
        new_balance = old_balance + CHANGE_USDC

        print("=== Transaction Summary ===")
        print(f"Network       : ETH")
        print(f"Address       : {ADDRESS}")
        print(f"Old USDC Balance : {format_decimal(old_balance)} USDC")
        print(f"Change          : {format_decimal(CHANGE_USDC)} USDC")
        print(f"New USDC Balance : {format_decimal(new_balance)} USDC")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()