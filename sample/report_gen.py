"""Scenario 5: AttributeError — 리포트 생성 (None 반환값에 .total 접근)"""

import errordog.tracker  # noqa: F401


def fetch_sales_data(region: str, month: str):
    """Simulate fetching sales data — returns None for missing regions."""
    database = {
        "Seoul": {"total": 4_800_000, "orders": 320, "avg": 15_000},
        "Busan": {"total": 2_100_000, "orders": 140, "avg": 15_000},
    }
    return database.get(region)  # returns None for unknown regions


def generate_regional_report(regions: list[str], month: str) -> None:
    for region in regions:
        data = fetch_sales_data(region, month)
        total = data["total"]  # bug: data is None when region not in DB
        orders = data["orders"]
        print(f"  {region} ({month}): {total:,}원 / {orders}건")


generate_regional_report(
    regions=["Seoul", "Busan", "Daegu"],  # Daegu not in database
    month="2026-04",
)
