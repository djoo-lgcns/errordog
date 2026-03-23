# Units of Work

## Decomposition Strategy

The system is decomposed into 4 sequential units, each corresponding to a project phase. Each unit builds on the prior unit and delivers standalone value.

---

## Unit 1: Core MCP Server & ESF

- **Phase**: Phase 1
- **Scope**: ESF schema definition, file-based snapshot storage, FastMCP server with tools
- **Components**: `models.py`, `store.py`, `server.py`, `__main__.py`
- **Deliverables**:
  - Pydantic models for ESF (ErrorSnapshot, Frame)
  - SnapshotStore for file-based persistence
  - MCP tools: `list_errors()`, `get_error_details(error_id)`
  - CLI entry point (`python -m errordog`)
- **Success Criteria**: Dummy JSON snapshots can be created and retrieved via MCP tools

---

## Unit 2: Python Runtime Tracker

- **Phase**: Phase 2
- **Scope**: Automatic exception capture via sys.excepthook, stack/memory extraction, ESF file generation
- **Components**: `tracker.py` (new module added to errordog package)
- **Deliverables**:
  - `sys.excepthook` override for uncaught exception capture
  - Stack frame traversal with `traceback` + `inspect`
  - Safe serialization of `f_locals` / `f_globals` (repr() fallback)
  - Automatic ESF file writing to `~/.errordog/snapshots/`
- **Success Criteria**: Intentional error script produces snapshot visible via MCP server

---

## Unit 3: Hybrid DAP Server

- **Phase**: Phase 3
- **Scope**: DAP proxy router, debugging state caching, mock mode for post-mortem analysis
- **Components**: New DAP-related modules (to be designed when Phase 3 begins)
- **Deliverables**:
  - Socket server accepting IDE connections
  - Bidirectional JSON-RPC message forwarding to debugpy
  - StoppedEvent interception and state caching
  - Mock mode: load ESF file, respond to stackTrace/variables requests
- **Success Criteria**: debugpy + Neovim with proxy works; mock mode visualizes dead process state

---

## Unit 4: AI Hypothesis Testing & Auto-Test Generation

- **Phase**: Phase 4
- **Scope**: Expression evaluation, test generation, IDE automation
- **Components**: New tool modules (to be designed when Phase 4 begins)
- **Deliverables**:
  - MCP tool: `evaluate_expression(expression, frame_id)`
  - MCP tool: `generate_reproduction_test(error_id)`
  - MCP tool: `reproduce_error_in_ide(error_id)` (Neovim RPC)
- **Success Criteria**: AI can evaluate expressions, generate pytest scripts, trigger IDE attach

---

## Code Organization Strategy (Greenfield)

```
debugger-v4/                     # workspace root
+-- pyproject.toml               # uv project config
+-- src/
|   +-- errordog/
|       +-- __init__.py
|       +-- __main__.py          # CLI entry point
|       +-- models.py            # ESF Pydantic models (Unit 1)
|       +-- store.py             # Snapshot storage (Unit 1)
|       +-- server.py            # MCP server + tools (Unit 1)
|       +-- tracker.py           # Exception hook (Unit 2)
|       +-- dap/                 # DAP proxy (Unit 3, TBD)
|       +-- tools/               # AI tools (Unit 4, TBD)
+-- tests/
|   +-- test_models.py
|   +-- test_store.py
|   +-- test_server.py
+-- aidlc-docs/                  # AI-DLC documentation only
```

New modules and subpackages will be added as each unit begins.
