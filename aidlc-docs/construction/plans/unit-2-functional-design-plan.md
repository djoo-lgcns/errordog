# Functional Design Plan - Unit 2: Python Runtime Tracker

## Plan Steps

- [x] Detail tracker activation mechanism (sys.excepthook override)
- [x] Define stack frame traversal and data extraction logic
- [x] Define safe serialization rules for local variables
- [x] Define ESF snapshot generation and storage flow
- [x] Generate business-logic-model.md
- [x] Generate business-rules.md
- [x] Generate domain-entities.md

---

## Design Questions

### Question 1
How should the tracker be activated in user code?

A) Manual call: user adds `errordog.tracker.install()` at the top of their script
B) Auto-activate on import: `import errordog.tracker` installs the hook immediately
C) Both: auto-activate on import, with `install()` / `uninstall()` for explicit control
D) Other (please describe after [Answer]: tag below)

[Answer]:B

### Question 2
Should the tracker capture exceptions inside `try/except` blocks, or only truly uncaught exceptions?

A) Only uncaught exceptions (sys.excepthook only - simplest, least intrusive)
B) Both uncaught + optionally caught exceptions (provide a decorator or context manager)
C) Other (please describe after [Answer]: tag below)

[Answer]:A

### Question 3
How many stack frames should be captured?

A) All frames in the traceback (full call stack)
B) Configurable limit with a default (e.g., max 50 frames)
C) Other (please describe after [Answer]: tag below)

[Answer]:B

### Question 4
Should the tracker handle serialization size limits for `f_locals`?

A) No limits - repr() everything regardless of size
B) Truncate repr() output per variable (e.g., max 1000 chars per value)
C) Truncate + skip large collections (e.g., skip if repr > 10KB)
D) Other (please describe after [Answer]: tag below)

[Answer]:B

### Question 5
Should the tracker preserve the original `sys.excepthook` behavior (e.g., still print traceback to stderr)?

A) Yes - capture snapshot AND call the original excepthook (user still sees the traceback)
B) No - replace entirely (snapshot only, suppress default traceback)
C) Configurable (default: preserve original behavior)
D) Other (please describe after [Answer]: tag below)

[Answer]:A
