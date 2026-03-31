"""Tests for errordog.runner — script execution with tracker injection."""

import sys
import textwrap
from pathlib import Path

import pytest

from errordog.runner import run
from errordog.store import SnapshotStore


class TestRun:
    """Tests for the run() function."""

    def test_script_runs_successfully(self, tmp_path: Path) -> None:
        """A normal script should execute without error."""
        script = tmp_path / "ok.py"
        script.write_text("result = 1 + 1\n")
        run(str(script))  # should not raise

    def test_sys_argv_is_set(self, tmp_path: Path) -> None:
        """Target script should see correct sys.argv."""
        script = tmp_path / "check_argv.py"
        script.write_text(textwrap.dedent("""\
            import sys, json
            from pathlib import Path
            Path(sys.argv[0]).parent.joinpath("argv_out.json").write_text(json.dumps(sys.argv))
        """))
        run(str(script), ["--flag", "value"])
        out = tmp_path / "argv_out.json"
        import json
        argv = json.loads(out.read_text())
        assert argv[0] == str(script)
        assert argv[1:] == ["--flag", "value"]

    def test_name_is_main(self, tmp_path: Path) -> None:
        """Target script should see __name__ == '__main__'."""
        script = tmp_path / "check_name.py"
        script.write_text(textwrap.dedent("""\
            from pathlib import Path
            Path(__file__).parent.joinpath("name_out.txt").write_text(__name__)
        """))
        run(str(script))
        out = tmp_path / "name_out.txt"
        assert out.read_text() == "__main__"

    def test_exception_captured_as_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An uncaught exception in the target script should produce a snapshot."""
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()

        # Patch SnapshotStore to use our temp dir
        monkeypatch.setattr(
            "errordog.store.DEFAULT_SNAPSHOT_DIR",
            snapshot_dir,
        )

        script = tmp_path / "crash.py"
        script.write_text("raise ValueError('boom')\n")

        # Runner calls sys.excepthook then sys.exit(1)
        with pytest.raises(SystemExit) as exc_info:
            run(str(script))
        assert exc_info.value.code == 1

        # Tracker's excepthook should have saved a snapshot
        snapshots = list(snapshot_dir.glob("err_*.json"))
        assert len(snapshots) >= 1

    def test_nonexistent_script_exits_with_error(self, tmp_path: Path) -> None:
        """Running a nonexistent script should exit with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            run(str(tmp_path / "no_such_file.py"))
        assert exc_info.value.code == 1


class TestCli:
    """Tests for CLI subcommand routing."""

    def test_unknown_command_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown subcommand should exit with code 1."""
        monkeypatch.setattr(sys, "argv", ["errordog", "nope"])
        from errordog.__main__ import main
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_run_without_script_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """'errordog run' without a script path should exit with code 1."""
        monkeypatch.setattr(sys, "argv", ["errordog", "run"])
        from errordog.__main__ import main
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
