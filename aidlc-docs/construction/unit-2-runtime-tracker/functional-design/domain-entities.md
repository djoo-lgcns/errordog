# Domain Entities - Unit 2: Python Runtime Tracker

## No New Entities

Unit 2 reuses the ESF entities defined in Unit 1:
- `Frame` (from `errordog.models`)
- `ErrorSnapshot` (from `errordog.models`)
- `generate_error_id()` (from `errordog.models`)
- `SnapshotStore` (from `errordog.store`)

## Tracker Configuration Constants

| Constant | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_FRAMES` | `int` | `50` | Maximum number of stack frames to capture |
| `MAX_REPR_LENGTH` | `int` | `1000` | Maximum character length per variable repr() |

These are module-level constants in `tracker.py`, not Pydantic models.
