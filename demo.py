import errordog.tracker


def calculate_price(items):
    total = sum(item["price"] * item["qty"] for item in items)
    return total


orders = [
    {"price": 1500, "qty": 2},
    {"price": "free", "qty": 1},  # bug, int 자리에 string
]

calculate_price(orders)
