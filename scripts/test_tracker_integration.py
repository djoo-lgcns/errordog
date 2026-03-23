"""Integration test: verify tracker captures a real exception as ESF snapshot.

Run: uv run python scripts/test_tracker_integration.py
Expected: script crashes with ValueError, snapshot appears in ~/.errordog/snapshots/
"""

import errordog.tracker  # noqa: F401 - activates the hook

from errordog.store import SnapshotStore


def deeply_nested_call(value: str) -> int:
    """Function that will fail on bad input."""
    result = int(value)  # This will raise ValueError for non-numeric input
    return result


def process_data(data: dict) -> int:
    """Process data by converting string value to int."""
    return deeply_nested_call(data["amount"])


def main() -> None:
    store = SnapshotStore()
    count_before = len(store.list_snapshots())
    print(f"Snapshots before: {count_before}")
    print("About to cause a ValueError...")
    print("---")

    # This will raise ValueError and trigger the tracker
    process_data({"amount": "not_a_number"})


if __name__ == "__main__":
    main()
