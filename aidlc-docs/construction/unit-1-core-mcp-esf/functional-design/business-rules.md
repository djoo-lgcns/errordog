# Business Rules - Unit 1: Core MCP Server & ESF

## BR-1: ESF Validation Rules

### BR-1.1: error_id Format
- Must match pattern: `err_\d{8}T\d{6}_[0-9a-f]{6}`
- Must be unique across all stored snapshots

### BR-1.2: timestamp Format
- Must be valid ISO 8601 datetime string
- Must include timezone (UTC preferred)

### BR-1.3: Frame Constraints
- `file_path` must be a non-empty string
- `line_number` must be a positive integer (>= 1)
- `function_name` must be a non-empty string
- `locals` must be a dict with string keys and string values

### BR-1.4: ErrorSnapshot Constraints
- `frames` must contain at least 1 frame
- `exception_type` must be a non-empty string
- `exception_message` can be empty string (some exceptions have no message)

---

## BR-2: Snapshot Storage Rules

### BR-2.1: Storage Directory
- Default path: `~/.errordog/snapshots/`
- Directory must be created automatically if it doesn't exist
- Custom path can be provided at initialization

### BR-2.2: File Naming
- File name: `{error_id}.json`
- One snapshot per file
- JSON format with UTF-8 encoding

### BR-2.3: File Discovery
- Only `.json` files in the snapshot directory are considered
- Subdirectories are ignored (flat structure)
- Files that fail Pydantic validation are skipped with a warning log

### BR-2.4: Corrupted File Handling
- If a `.json` file cannot be parsed or fails validation: skip silently
- Log a warning message with the file path and error reason
- Exclude from `list_snapshots()` and `get_snapshot()` results
- Never delete or modify corrupted files (user may want to inspect)

---

## BR-3: MCP Tool Rules

### BR-3.1: list_errors()
- Returns list of ErrorSummary dicts (not full snapshots)
- Each entry includes: error_id, timestamp, exception_type, exception_message, file_path, line_number, function_name
- Top frame info (file_path, line_number, function_name) extracted from `frames[0]`
- Sorted by timestamp descending (most recent first)
- Returns empty list if no valid snapshots exist

### BR-3.2: get_error_details(error_id)
- Returns full ErrorSnapshot as dict
- If error_id not found: return descriptive error message (not exception)
- Lookup by matching `{error_id}.json` filename in snapshot directory

---

## BR-4: Serialization Rules

### BR-4.1: Local Variables
- All values serialized via `repr()` to produce safe string representations
- Non-serializable objects must not cause snapshot creation to fail
- Result is always `dict[str, str]`

### BR-4.2: JSON Output
- Use `model_dump()` for Pydantic-to-dict conversion
- Use standard `json` module for file I/O
- Indent JSON with 2 spaces for human readability
