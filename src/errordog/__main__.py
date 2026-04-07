"""CLI entry point for Errordog."""

import sys


def main() -> None:
    """Route subcommands: serve, run, dap, or script path."""
    args = sys.argv[1:]

    if not args or args[0] == "serve":
        from errordog.server import create_server

        server = create_server()
        server.run()

    elif args[0] == "run":
        if len(args) < 2:
            print("Usage: errordog run <script.py> [args...]", file=sys.stderr)
            sys.exit(1)
        from errordog.runner import run

        run(args[1], args[2:])

    elif args[0] == "dap":
        from errordog.dap.proxy import run

        run()

    elif args[0] == "clean":
        from errordog.store import SnapshotStore
        from pathlib import Path

        store = SnapshotStore()
        snapshots = list(store.snapshot_dir.glob("*.json"))
        if not snapshots:
            print("No snapshots to remove.")
            sys.exit(0)
        print(f"Remove {len(snapshots)} snapshot(s) from {store.snapshot_dir}? [y/N] ", end="")
        if input().strip().lower() == "y":
            for p in snapshots:
                p.unlink()
            print(f"Removed {len(snapshots)} snapshot(s).")
        else:
            print("Aborted.")

    else:
        # Treat first arg as script path: python -m errordog script.py [args...]
        from errordog.runner import run

        run(args[0], args[1:])


if __name__ == "__main__":
    main()
