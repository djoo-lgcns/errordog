# Functional Design Plan - Unit 1: Core MCP Server & ESF

## Plan Steps

- [x] Detail ESF domain model (ErrorSnapshot, Frame entities and field constraints)
- [x] Define business rules for snapshot validation and serialization
- [x] Define business logic for SnapshotStore (file naming, directory management, error handling)
- [x] Define business logic for MCP tools (list_errors, get_error_details)
- [x] Generate business-logic-model.md
- [x] Generate business-rules.md
- [x] Generate domain-entities.md

---

## Design Questions

### Question 1
How should `error_id` be generated?

A) UUID v4 (random, e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
B) Timestamp-based ID (e.g., `err_20260310T131600_abcdef`)
C) Hash-based (hash of exception type + message + top frame)
D) Other (please describe after [Answer]: tag below)

[Answer]:B

### Question 2
Should `locals` and `globals` in each frame capture ALL variables or apply filtering?

A) Capture all variables (repr() everything, no filtering)
B) Capture all locals, but only relevant globals (exclude builtins, modules)
C) Capture all locals, skip globals entirely (globals are rarely useful for debugging)
D) Other (please describe after [Answer]: tag below)

[Answer]:C

### Question 3
What should `list_errors()` return for each snapshot?

A) Summary only: error_id, timestamp, exception_type, exception_message
B) Summary + first frame info (file_path, line_number, function_name)
C) Full snapshot data for each error
D) Other (please describe after [Answer]: tag below)

[Answer]:B

### Question 4
How should the system handle corrupted or invalid snapshot files in the storage directory?

A) Skip silently (log warning, exclude from results)
B) Return error entry with status "corrupted" in list
C) Raise error and fail the tool call
D) Other (please describe after [Answer]: tag below)

[Answer]:A
