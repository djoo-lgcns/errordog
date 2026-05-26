"""Scenario 1: TypeError — 주문 가격 계산 (문자열 * 정수)"""

import errordog.tracker  # noqa: F401 — auto-capture on import


def calculate_total(items: list[dict]) -> float:
    """Calculate total price for a list of order items."""
    return sum(item["price"] * item["qty"] for item in items)


orders = [
    {"product": "Laptop", "price": 1_200_000, "qty": 1},
    {"product": "Mouse", "price": 35_000, "qty": 2},
    {"product": "Promotion", "price": "free", "qty": 1},  # bug: string price
]

total = calculate_total(orders)
print(f"Total: {total:,}원")
