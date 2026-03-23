# Domain Entities - Unit 1: Core MCP Server & ESF

## Entity: Frame

Represents a single stack frame at the time of the exception.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | `str` | Yes | Absolute path to the source file |
| `line_number` | `int` | Yes | Line number where execution was at time of error |
| `function_name` | `str` | Yes | Name of the function/method |
| `locals` | `dict[str, str]` | Yes | Local variables as `name -> repr(value)` |

**Notes**:
- `globals` are excluded (rarely useful for debugging, adds noise)
- `locals` values are always `repr()` strings for safe serialization
- Frames are ordered innermost-first (crash frame at index 0)

---

## Entity: ErrorSnapshot

Represents a complete error capture at a point in time.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error_id` | `str` | Yes | Timestamp-based ID: `err_{YYYYMMDD}T{HHMMSS}_{6hex}` |
| `timestamp` | `str` | Yes | ISO 8601 datetime (e.g., `2026-03-10T13:16:00Z`) |
| `exception_type` | `str` | Yes | Exception class name (e.g., `ValueError`) |
| `exception_message` | `str` | Yes | Exception message string |
| `frames` | `list[Frame]` | Yes | Call stack frames, innermost first |

---

## Entity: ErrorSummary

Lightweight representation returned by `list_errors()`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error_id` | `str` | Yes | Same as ErrorSnapshot.error_id |
| `timestamp` | `str` | Yes | Same as ErrorSnapshot.timestamp |
| `exception_type` | `str` | Yes | Same as ErrorSnapshot.exception_type |
| `exception_message` | `str` | Yes | Same as ErrorSnapshot.exception_message |
| `file_path` | `str` | Yes | From first frame (crash location) |
| `line_number` | `int` | Yes | From first frame (crash location) |
| `function_name` | `str` | Yes | From first frame (crash location) |

---

## Entity Relationships

```
ErrorSnapshot 1 ---contains---> * Frame
ErrorSnapshot 1 ---derives----> 1 ErrorSummary (computed, not stored)
```

## error_id Format

**Pattern**: `err_{YYYYMMDD}T{HHMMSS}_{6_random_hex}`

**Examples**:
- `err_20260310T131600_a3f2b1`
- `err_20260311T090045_7c8d2e`

**Generation logic**:
1. Take current UTC datetime
2. Format as `YYYYMMDD` + `T` + `HHMMSS`
3. Append `_` + 6 random hex characters (for uniqueness within same second)
4. Prefix with `err_`

**File naming**: `{error_id}.json` (e.g., `err_20260310T131600_a3f2b1.json`)
