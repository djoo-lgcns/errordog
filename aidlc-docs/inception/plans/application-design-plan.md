# Application Design Plan

## Plan Steps

- [x] Define component boundaries and responsibilities
- [x] Define component interfaces (method signatures)
- [x] Define service layer and orchestration
- [x] Define component dependencies and communication patterns
- [x] Generate components.md
- [x] Generate component-methods.md
- [x] Generate services.md
- [x] Generate component-dependency.md
- [x] Generate consolidated application-design.md
- [x] Validate design completeness and consistency

---

## Design Questions (Phase 1: Core MCP Server & ESF)

Later phase design decisions will be addressed when those phases begin. Please answer by filling in the letter choice after each `[Answer]:` tag.

### Question 1
How should the initial Python package be structured for Phase 1?

A) Single package with flat modules (`errordog/server.py`, `errordog/snapshot.py`, etc.)
B) Single package with nested subpackages (`errordog/core/`, `errordog/mcp/`, etc.)
C) Other (please describe after [Answer]: tag below)

[Answer]:A

### Question 2
Should the ESF schema be validated at runtime (e.g., with Pydantic models)?

A) Yes - use Pydantic models for ESF schema validation and serialization
B) No - use plain dicts/dataclasses, keep it lightweight
C) Other (please describe after [Answer]: tag below)

[Answer]:A

### Question 3
How should the MCP server be started?

A) CLI entry point (`errordog serve` or `python -m errordog`)
B) Direct module execution only (`python -m errordog.server`)
C) Both CLI entry point and module execution
D) Other (please describe after [Answer]: tag below)

[Answer]:A
