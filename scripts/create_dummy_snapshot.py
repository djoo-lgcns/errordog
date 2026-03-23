"""Create dummy ESF snapshot files for integration testing."""

from errordog.models import ErrorSnapshot, Frame, generate_error_id
from errordog.store import SnapshotStore


def main() -> None:
    store = SnapshotStore()  # defaults to ~/.errordog/snapshots/

    # Snapshot 1: TypeError in data processing
    snap1 = ErrorSnapshot(
        error_id=generate_error_id(),
        timestamp="2026-03-10T14:00:00Z",
        exception_type="TypeError",
        exception_message="unsupported operand type(s) for +: 'int' and 'str'",
        frames=[
            Frame(
                file_path="/home/user/app/processor.py",
                line_number=87,
                function_name="merge_records",
                locals={"a": "42", "b": "'hello'", "result": "None"},
            ),
            Frame(
                file_path="/home/user/app/main.py",
                line_number=23,
                function_name="run_pipeline",
                locals={"records": "[{'id': 1}, {'id': 2}]", "config": "{'mode': 'merge'}"},
            ),
        ],
    )

    # Snapshot 2: KeyError in config lookup
    snap2 = ErrorSnapshot(
        error_id=generate_error_id(),
        timestamp="2026-03-10T14:05:00Z",
        exception_type="KeyError",
        exception_message="'database_url'",
        frames=[
            Frame(
                file_path="/home/user/app/config.py",
                line_number=15,
                function_name="get_config",
                locals={"key": "'database_url'", "config": "{'host': 'localhost', 'port': '5432'}"},
            ),
        ],
    )

    path1 = store.save_snapshot(snap1)
    path2 = store.save_snapshot(snap2)
    print(f"Created: {path1}")
    print(f"Created: {path2}")
    print(f"\nSnapshots stored in: {store.snapshot_dir}")
    print(f"Total snapshots: {len(store.list_snapshots())}")


if __name__ == "__main__":
    main()
