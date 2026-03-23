# Business Rules - Unit 2: Python Runtime Tracker

## BR-1: Tracker Activation

### BR-1.1: Auto-Activate on Import
- `import errordog.tracker` immediately installs the `sys.excepthook` override
- No explicit `install()` call required from user code

### BR-1.2: Preserve Original Excepthook
- Store reference to `sys.excepthook` before overriding
- After capturing snapshot, call the original excepthook
- User still sees the normal traceback output in stderr

### BR-1.3: Idempotent Installation
- Importing multiple times must not stack multiple hooks
- Guard against re-installation if already installed

---

## BR-2: Exception Capture Scope

### BR-2.1: Uncaught Exceptions Only
- Only capture exceptions that reach `sys.excepthook`
- Do NOT intercept exceptions inside `try/except` blocks
- `KeyboardInterrupt` and `SystemExit` should NOT be captured (not real errors)

---

## BR-3: Stack Frame Extraction

### BR-3.1: Frame Traversal
- Use the traceback object (`tb`) passed to excepthook
- Walk `tb.tb_next` chain to extract each frame
- For each frame, extract: `f_code.co_filename`, `tb.tb_lineno`, `f_code.co_name`, `f_locals`

### BR-3.2: Frame Limit
- Default maximum: 50 frames (`MAX_FRAMES`)
- If traceback has more frames, capture the innermost (most recent) 50
- Frames ordered innermost-first (crash frame at index 0) to match ESF format

### BR-3.3: Frame Ordering
- Traceback walks outermost to innermost
- Reverse the collected frames so `frames[0]` is the crash point

---

## BR-4: Variable Serialization

### BR-4.1: Locals Only
- Capture `f_locals` per frame (globals excluded per FR design decision)
- Result is `dict[str, str]` where values are `repr()` strings

### BR-4.2: Safe Serialization
- Wrap each `repr()` call in try/except
- If `repr()` fails, use `f"<unrepresentable: {type(obj).__name__}>"` as fallback
- Must never crash during serialization

### BR-4.3: Truncation
- Default max repr length: 1000 characters (`MAX_REPR_LENGTH`)
- If `repr(value)` exceeds limit, truncate to `repr_str[:MAX_REPR_LENGTH] + "..."`

---

## BR-5: Snapshot Generation & Storage

### BR-5.1: Snapshot Construction
- Generate `error_id` via `generate_error_id()`
- Generate `timestamp` as UTC ISO 8601
- Extract `exception_type` from `exc_type.__name__`
- Extract `exception_message` from `str(exc_value)`
- Build `frames` list from traceback extraction

### BR-5.2: Storage
- Use `SnapshotStore` (from Unit 1) with default directory
- Call `store.save_snapshot(snapshot)` to persist
- If save fails (permission error, disk full), log warning but do NOT crash the excepthook

---

## BR-6: Error Safety

### BR-6.1: Never Crash the Hook
- The entire excepthook override must be wrapped in try/except
- If any error occurs during snapshot capture/save, log warning and fall through to original excepthook
- The tracker must never make a bad situation worse
