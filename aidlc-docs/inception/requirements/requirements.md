# Errordog - Requirements Document

## Intent Analysis

- **User Request**: Build "Errordog", a hybrid debugging and test automation server for AI agents and developers
- **Request Type**: New Project (Greenfield)
- **Scope**: System-wide (4 major components across 4 phases)
- **Complexity**: Complex (multiple protocols: MCP, DAP, JSON-RPC; multiple integration targets)

---

## Functional Requirements

### Phase 1: Core MCP Server & Snapshot Format (ESF)

#### FR-1.1: ESF (Errordog Snapshot Format)
- JSON schema for error snapshots
- Required fields: `error_id`, `timestamp`, `exception_type`, `exception_message`, `frames`
- Frame structure: `file_path`, `line_number`, `function_name`, `locals`, `globals`

#### FR-1.2: MCP Server Scaffolding
- Python-based MCP server using **fastmcp** SDK
- Snapshot storage directory: `~/.errordog/snapshots/`
- File-based persistence for snapshots

#### FR-1.3: MCP Tools
- `list_errors()`: Return list of stored snapshot files
- `get_error_details(error_id)`: Return full JSON data for a specific snapshot

#### FR-1.4: Success Criteria
- Dummy JSON snapshot files can be created and retrieved via MCP tools

---

### Phase 2: Python Runtime Tracker (Agent)

#### FR-2.1: Exception Hook
- `errordog_tracker` module with `sys.excepthook` override
- Capture uncaught exceptions automatically

#### FR-2.2: Stack & Memory Extraction
- Traverse crash-time frames using `traceback` and `inspect` modules
- Safely serialize `f_locals` and `f_globals` per frame
- Use `repr()` for non-serializable objects

#### FR-2.3: ESF File Storage
- Convert extracted data to ESF JSON format
- Save to `~/.errordog/snapshots/`

#### FR-2.4: Success Criteria
- Intentional error script produces snapshot visible via MCP server

---

### Phase 3: Hybrid DAP Server (Proxy & Mock)

#### FR-3.1: DAP Proxy Router
- Socket server accepting IDE (Client) connections
- Forward bidirectional JSON-RPC messages to target debugger
- Initial target: **debugpy**, extensible to other DAP backends

#### FR-3.2: Debugging State Caching
- Intercept `StoppedEvent` and similar DAP events
- Cache current `threadId`, `frameId` in internal memory

#### FR-3.3: Mock Mode (Post-Mortem)
- On `attach` request with `error_id`, load ESF file
- Respond to `stackTrace`, `variables` requests from loaded snapshot data

#### FR-3.4: Success Criteria
- debugpy + Neovim with Errordog proxy: breakpoints work normally
- Mock mode: IDE visualizes a dead process state from ESF snapshot

---

### Phase 4: AI Hypothesis Testing & Auto-Test Generation

#### FR-4.1: State Evaluation MCP Tool
- `evaluate_expression(expression, frame_id)`: Execute Python expression in stopped state (live or mock) and return result

#### FR-4.2: Automated Test Generator
- `generate_reproduction_test(error_id)`: Analyze ESF data, generate pytest script that reproduces the crash with mocked entry-point parameters

#### FR-4.3: IDE Automation
- `reproduce_error_in_ide(error_id)`: Send Neovim RPC command to auto-attach to Errordog Mock mode
- Primary target: **Neovim** (nvim-dap + RPC)
- Secondary target: **VS Code** (future)

#### FR-4.4: Success Criteria
- AI can load snapshot, evaluate expressions, and produce a root cause report
- AI can generate a runnable pytest that reproduces the error

---

## Non-Functional Requirements

### NFR-1: Technology Stack
- **Language**: Python 3.13+
- **Package Manager**: uv
- **MCP SDK**: fastmcp
- **Testing**: pytest
- **DAP Backend (initial)**: debugpy
- **IDE (primary)**: Neovim (nvim-dap)
- **IDE (secondary)**: VS Code (future)

### NFR-2: Deployment Model
- Local-first developer tool (runs on developer's machine)
- Optional remote/shared mode for future expansion

### NFR-3: Delivery Approach
- One phase at a time with review between each phase
- Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

### NFR-4: Serialization Safety
- Non-serializable objects must be handled gracefully via `repr()`
- No crashes during snapshot capture

### NFR-5: Extensibility
- DAP proxy must be designed to support additional debugger backends beyond debugpy
- IDE automation should be abstracted for future VS Code support

### NFR-6: Security
- Security extension rules **disabled** (prototype/experimental project)
- Basic safety measures still apply (no hardcoded secrets, safe serialization)

---

## Architectural Considerations

- **ESF Format** is the central data structure shared across all phases
- **MCP Server** is the integration point for AI agents (Claude Code)
- **DAP Server** operates in two modes: Proxy (live) and Mock (post-mortem)
- **Phase independence**: Each phase builds on prior phases but delivers standalone value
