"""Scenario 3: ZeroDivisionError — 재고 소진율 계산"""

import errordog.tracker  # noqa: F401


def calculate_turnover_rate(warehouse: dict) -> dict[str, float]:
    """Calculate inventory turnover rate for each product category."""
    rates = {}
    for category, data in warehouse["categories"].items():
        sold = data["sold_this_month"]
        avg_stock = (data["opening_stock"] + data["closing_stock"]) / 2
        rates[category] = sold / avg_stock  # bug: avg_stock can be 0
    return rates


def generate_report(warehouse: dict) -> None:
    rates = calculate_turnover_rate(warehouse)
    for category, rate in rates.items():
        print(f"  {category}: {rate:.2f}x turnover")


warehouse_data = {
    "name": "Seoul Warehouse",
    "categories": {
        "Electronics": {"sold_this_month": 120, "opening_stock": 200, "closing_stock": 80},
        "Furniture": {"sold_this_month": 15, "opening_stock": 50, "closing_stock": 35},
        "Discontinued": {"sold_this_month": 0, "opening_stock": 0, "closing_stock": 0},  # bug: both stocks are 0
    },
}

generate_report(warehouse_data)
