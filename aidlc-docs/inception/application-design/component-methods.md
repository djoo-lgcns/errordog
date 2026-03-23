# Component Methods - Phase 1: Core MCP Server & ESF

> Method signatures and high-level purpose. Detailed business rules in Functional Design.

## C1: ESF Models (`errordog/models.py`)

### Pydantic Models

```python
class Frame(BaseModel):
    file_path: str
    line_number: int
    function_name: str
    locals: dict[str, str]    # variable_name -> repr() value
    globals: dict[str, str]   # variable_name -> repr() value

class ErrorSnapshot(BaseModel):
    error_id: str             # unique identifier (UUID)
    timestamp: str            # ISO 8601 format
    exception_type: str       # e.g., "ValueError"
    exception_message: str    # e.g., "invalid literal for int()"
    frames: list[Frame]       # call stack, innermost first
```

No additional methods beyond Pydantic's built-in `model_validate()`, `model_dump()`, `model_dump_json()`.

---

## C2: Snapshot Store (`errordog/store.py`)

### Class: `SnapshotStore`

```python
class SnapshotStore:
    def __init__(self, snapshot_dir: Path | None = None) -> None:
        """Initialize store with snapshot directory. Defaults to ~/.errordog/snapshots/."""

    def ensure_directory(self) -> None:
        """Create snapshot directory if it doesn't exist."""

    def list_snapshots(self) -> list[str]:
        """Return list of error_id strings from stored snapshot files."""

    def get_snapshot(self, error_id: str) -> ErrorSnapshot:
        """Load and return a single snapshot by error_id. Raises if not found."""

    def save_snapshot(self, snapshot: ErrorSnapshot) -> Path:
        """Write snapshot to file. Returns path of saved file."""
```

---

## C3: MCP Server (`errordog/server.py`)

### MCP Tools (registered via FastMCP)

```python
@mcp.tool()
def list_errors() -> list[dict]:
    """Return list of stored error snapshots with summary info (error_id, timestamp, exception_type, exception_message)."""

@mcp.tool()
def get_error_details(error_id: str) -> dict:
    """Return full ESF JSON data for a specific error snapshot."""
```

### Server Setup

```python
def create_server(snapshot_dir: Path | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance with tools registered."""
```

---

## C4: CLI Entry Point (`errordog/__main__.py`)

```python
def main() -> None:
    """Entry point: create server and run it."""
```

Invoked via: `python -m errordog`
