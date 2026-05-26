"""CLI entry point for Errordog."""

import sys


def main() -> None:
    """Route subcommands: serve, run, dap, or script path."""
    args = sys.argv[1:]

    if not args or args[0] == "serve":
        from errordog.server import create_server

        server = create_server()
        if "--http" in args:
            port = 8080
            for a in args:
                if a.startswith("--port="):
                    port = int(a.split("=", 1)[1])
            server.run(transport="http", host="0.0.0.0", port=port)
        else:
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

    elif args[0] == "select":
        from errordog.store import SnapshotStore
        from pathlib import Path

        store = SnapshotStore()
        summaries = store.list_summaries()

        if not summaries:
            print("No snapshots available", file=sys.stderr)
            sys.exit(1)

        # Check if index provided as argument
        if len(args) > 1:
            try:
                idx = int(args[1])
                if not 0 <= idx < len(summaries):
                    print(f"Invalid index: {idx}", file=sys.stderr)
                    sys.exit(1)
                selected_id = summaries[idx].error_id
            except ValueError:
                print(f"Invalid index: {args[1]}", file=sys.stderr)
                sys.exit(1)
        else:
            # Interactive mode: display and prompt
            # Check if stdin is available (terminal mode)
            if not sys.stdin.isatty():
                # Non-interactive: select most recent
                selected_id = summaries[0].error_id
                print(f"Auto-selecting most recent: {selected_id}", file=sys.stderr)
            else:
                # Interactive: show list and prompt
                for i, summary in enumerate(summaries[:10]):
                    print(f"{i:2} | {summary.error_id:30} | {summary.exception_type:15} | {summary.file_path}:{summary.line_number}")

                try:
                    choice = input("\nSelect snapshot [0-9]: ").strip()
                    idx = int(choice)
                    if not 0 <= idx < len(summaries):
                        print("Invalid selection", file=sys.stderr)
                        sys.exit(1)
                    selected_id = summaries[idx].error_id
                except ValueError:
                    print("Invalid input", file=sys.stderr)
                    sys.exit(1)

        # Save to config file
        config_dir = Path.home() / ".errordog"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "selected_error_id").write_text(selected_id)
        print(f"✓ Selected: {selected_id}", file=sys.stderr)

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
