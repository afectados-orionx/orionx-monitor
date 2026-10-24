def process_transaction(network: str, address: str, change_usdc: float, change_usd: float):
    """
    Process a discovered outgoing transaction.

    Parameters:
        network (str): Blockchain network name (e.g., "ETH").
        address (str): Destination address.
        change_usdc (float): Amount of USDC moved (negative for outgoing).
        change_usd (float): Approximate USD value of the movement.

    Returns:
        dict: Summary of the processed transaction.
    """
    if change_usdc >= 0:
        direction = "incoming"
    else:
        direction = "outgoing"

    summary = {
        "network": network,
        "address": address,
        "direction": direction,
        "amount_usdc": change_usdc,
        "approx_usd": change_usd,
        "alert": direction == "outgoing"
    }

    if summary["alert"]:
        print(
            f"[ALERT] {network} transaction detected: "
            f"{abs(change_usdc):,.6f} USDC ({abs(change_usd):,.2f} USD) sent to {address}"
        )
    else:
        print(
            f"[INFO] {network} transaction: {change_usdc:,.6f} USDC ({change_usd:,.2f} USD) "
            f"to {address}"
        )
    return summary


# Example usage with the provided data
if __name__ == "__main__":
    network = "ETH"
    address = "0x58b704065b7aff3ed351052f8560019e05925023"
    change_usdc = -3_754_969.70163500
    change_usd = -3_754_631.75

    result = process_transaction(network, address, change_usdc, change_usd)