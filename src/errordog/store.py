"""File-based snapshot storage for ESF snapshots."""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from errordog.models import ErrorSnapshot, ErrorSummary

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_DIR = Path.home() / ".errordog" / "snapshots"


class SnapshotStore:
    """Manages file-based persistence of ESF error snapshots."""

    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self.snapshot_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
        self.ensure_directory()

    def ensure_directory(self) -> None:
        """Create snapshot directory if it doesn't exist."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self) -> list[str]:
        """Return list of error_id strings from stored snapshot files."""
        error_ids: list[str] = []
        for path in self.snapshot_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                ErrorSnapshot.model_validate(data)
                error_ids.append(path.stem)
            except (json.JSONDecodeError, ValidationError, OSError) as e:
                logger.warning("Skipping corrupted snapshot file %s: %s", path, e)
        return error_ids

    def get_snapshot(self, error_id: str) -> ErrorSnapshot:
        """Load and return a single snapshot by error_id.

        Raises:
            FileNotFoundError: If snapshot file does not exist.
            ValueError: If snapshot file is corrupted or invalid.
        """
        path = self.snapshot_dir / f"{error_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Snapshot not found: {error_id}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ErrorSnapshot.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Snapshot corrupted: {error_id}") from e

    def save_snapshot(self, snapshot: ErrorSnapshot) -> Path:
        """Write snapshot to JSON file. Returns path of saved file."""
        self.ensure_directory()
        path = self.snapshot_dir / f"{snapshot.error_id}.json"
        data = json.dumps(snapshot.model_dump(), indent=2)
        path.write_text(data, encoding="utf-8")
        return path

    def list_summaries(self) -> list[ErrorSummary]:
        """Return list of ErrorSummary for all valid snapshots, sorted by timestamp desc."""
        summaries: list[ErrorSummary] = []
        for path in self.snapshot_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                snapshot = ErrorSnapshot.model_validate(data)
                summaries.append(ErrorSummary.from_snapshot(snapshot))
            except (json.JSONDecodeError, ValidationError, OSError) as e:
                logger.warning("Skipping corrupted snapshot file %s: %s", path, e)
        summaries.sort(key=lambda s: s.timestamp, reverse=True)
        return summaries
