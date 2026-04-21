"""ESF (Errordog Snapshot Format) domain models."""

import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Frame(BaseModel):
    """A single stack frame captured at the time of an exception."""

    file_path: str
    line_number: int = Field(ge=1)
    function_name: str
    locals: dict[str, str] = Field(default_factory=dict)


class ErrorSnapshot(BaseModel):
    """Complete error capture in Errordog Snapshot Format (ESF)."""

    error_id: str
    timestamp: str
    exception_type: str
    exception_message: str
    frames: list[Frame] = Field(min_length=1)
    cwd: str | None = None  # working directory at capture time
    dump_path: str | None = None  # coredumpy dump file path (full state)


class ErrorSummary(BaseModel):
    """Lightweight snapshot summary returned by list_errors()."""

    error_id: str
    timestamp: str
    exception_type: str
    exception_message: str
    file_path: str
    line_number: int
    function_name: str

    @classmethod
    def from_snapshot(cls, snapshot: ErrorSnapshot) -> "ErrorSummary":
        """Create a summary from a full snapshot, extracting top frame info."""
        top_frame = snapshot.frames[0]
        return cls(
            error_id=snapshot.error_id,
            timestamp=snapshot.timestamp,
            exception_type=snapshot.exception_type,
            exception_message=snapshot.exception_message,
            file_path=top_frame.file_path,
            line_number=top_frame.line_number,
            function_name=top_frame.function_name,
        )


def generate_error_id() -> str:
    """Generate a timestamp-based error ID.

    Format: err_{YYYYMMDD}T{HHMMSS}_{6_random_hex}
    Example: err_20260310T131600_a3f2b1
    """
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%dT%H%M%S")
    hex_part = os.urandom(3).hex()
    return f"err_{date_part}_{hex_part}"
