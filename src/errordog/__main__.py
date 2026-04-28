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

        # Collect matching dumps
        dump_dir = Path.home() / ".errordog" / "dumps"
        dumps = [
            dump_dir / f"{s.stem}.dump"
            for s in snapshots
            if (dump_dir / f"{s.stem}.dump").exists()
        ]

        # Calculate total size
        total_size = sum(s.stat().st_size for s in snapshots) + \
                     sum(d.stat().st_size for d in dumps)
        total_kb = total_size / 1024

        print(f"Remove {len(snapshots)} snapshot(s) + {len(dumps)} dump(s)?")
        print(f"Total size: {total_kb:.1f}KB")
        print("Continue? [y/N] ", end="")

        if input().strip().lower() == "y":
            for p in snapshots + dumps:
                p.unlink()
            print(f"Removed {len(snapshots)} snapshot(s) and {len(dumps)} dump(s).")
        else:
            print("Aborted.")

    else:
        # Treat first arg as script path: python -m errordog script.py [args...]
        from errordog.runner import run

        run(args[0], args[1:])


if __name__ == "__main__":
    main()
