# Requirements Verification Questions

Based on the `errordog_plan.md` document, the following questions will help clarify implementation details not covered in the plan.

Please answer each question by filling in the letter choice after the `[Answer]:` tag.

---

## Question 1
What Python version should be the minimum target?

A) Python 3.10+
B) Python 3.11+
C) Python 3.12+
D) Python 3.13+
E) Other (please describe after [Answer]: tag below)

[Answer]: E

## Question 2
Which package manager / build tool should be used for the project?

A) uv (fast, modern Python package manager)
B) Poetry (dependency management + packaging)
C) pip + pyproject.toml (standard tooling)
D) Other (please describe after [Answer]: tag below)

[Answer]: uv

## Question 3
Which MCP SDK should be used for the server implementation?

A) mcp (official Anthropic Python MCP SDK)
B) fastmcp (high-level wrapper around the official SDK)
C) Other (please describe after [Answer]: tag below)

[Answer]: fastmcp

## Question 4
What is the primary deployment model for Errordog?

A) Local-only developer tool (runs on developer's machine, single user)
B) Local-first with optional remote/shared mode
C) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
For Phase 3 (DAP Proxy), should we target a specific debugger backend initially?

A) debugpy only (Python debugging via VS Code / Neovim DAP)
B) debugpy + support for other DAP-compatible debuggers later
C) Generic DAP proxy from the start (any DAP backend)
D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 6
For Phase 4 (IDE Automation), which IDE integration should be the primary target?

A) Neovim only (via nvim-dap + RPC)
B) Neovim primary, VS Code secondary
C) Both Neovim and VS Code equally
D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 7
How should the phases be delivered? All 4 phases in one go, or incrementally?

A) Phase 1 + 2 first (Core MCP + Tracker), then Phase 3 + 4 later
B) All 4 phases together as a single delivery
C) One phase at a time, with review between each
D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 8: Security Extensions
Should security extension rules be enforced for this project?

A) Yes - enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)
B) No - skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)
C) Other (please describe after [Answer]: tag below)

[Answer]: B
