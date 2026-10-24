import os
import requests
from decimal import Decimal

# Configurable parameters
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")  # Set your Etherscan API key as an environment variable
ADDRESS = "0x58b704065b7aff3ed351052f8560019e05925023"
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
BASE_URL = "https://api.etherscan.io/api"

def fetch_usdc_transfers(address, start_block=0, end_block=99999999):
    """
    Fetch USDC ERC-20 token transfer events for a given address using Etherscan API.
    Returns a list of dicts with 'value' (as integer) and 'to'/'from' addresses.
    """
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "contractaddress": USDC_CONTRACT,
        "startblock": start_block,
        "endblock": end_block,
        "page": 1,
        "offset": 10000,
        "sort": "asc",
        "apikey": ETHERSCAN_API_KEY,
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "1":
        raise RuntimeError(f"Etherscan error: {data.get('message')}")
    return data.get("result", [])

def calculate_net_usdc(transfers):
    """
    Calculate net USDC change (in whole USDC units) for the address.
    Returns a Decimal representing the net amount.
    """
    net = Decimal(0)
    for tx in transfers:
        value = Decimal(tx["value"]) / Decimal(10**6)  # USDC has 6 decimals
        if tx["to"].lower() == ADDRESS.lower():
            net += value
        elif tx["from"].lower() == ADDRESS.lower():
            net -= value
    return net

def main():
    if not ETHERSCAN_API_KEY:
        raise EnvironmentError("Please set the ETHERSCAN_API_KEY environment variable.")
    transfers = fetch_usdc_transfers(ADDRESS)
    net_change = calculate_net_usdc(transfers)
    print(f"Net USDC change for {ADDRESS}: {net_change} USDC")

if __name__ == "__main__":
    main()