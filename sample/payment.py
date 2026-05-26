"""Scenario 2: ValueError — 결제 금액 유효성 검사 (음수 금액 & 중첩 dict)"""

import errordog.tracker  # noqa: F401


def apply_discount(payment: dict) -> dict:
    """Apply discount code and return updated payment dict."""
    code = payment["discount"]["code"]
    rate = payment["discount"]["rate"]
    original = payment["amount"]
    discounted = original * (1 - rate)
    if discounted < 0:
        raise ValueError(
            f"Discounted amount {discounted} is negative "
            f"(original={original}, rate={rate}, code={code!r})"
        )
    return {**payment, "amount": discounted, "discount_applied": True}


def process_checkout(cart: dict) -> None:
    for item in cart["items"]:
        updated = apply_discount(item["payment"])
        print(f"  {item['name']}: {updated['amount']:,.0f}원")


checkout = {
    "user_id": "user_42",
    "items": [
        {
            "name": "Keyboard",
            "payment": {"amount": 150_000, "discount": {"code": "SUMMER10", "rate": 0.10}},
        },
        {
            "name": "Monitor",
            "payment": {"amount": 500_000, "discount": {"code": "INVALID_CODE", "rate": 1.5}},  # bug: rate > 1
        },
    ],
}

process_checkout(checkout)
