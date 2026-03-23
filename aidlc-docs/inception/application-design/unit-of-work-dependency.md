# Unit of Work Dependencies

## Dependency Matrix

| Unit | Depends On | Depended On By |
|------|-----------|----------------|
| Unit 1: Core MCP & ESF | (none) | Unit 2, Unit 3, Unit 4 |
| Unit 2: Runtime Tracker | Unit 1 (ESF models, store) | Unit 3, Unit 4 |
| Unit 3: DAP Server | Unit 1 (ESF models, store), Unit 2 (tracker for live capture) | Unit 4 |
| Unit 4: AI Tools | Unit 1 (MCP server, models), Unit 3 (DAP proxy for evaluate) | (none) |

## Dependency Graph

```
Unit 1: Core MCP & ESF
    |
    v
Unit 2: Runtime Tracker
    |
    v
Unit 3: Hybrid DAP Server
    |
    v
Unit 4: AI Hypothesis Testing
```

## Execution Order

Strictly sequential. Each unit must be completed and reviewed before the next begins.

1. **Unit 1** - Foundation: ESF format + MCP server (no dependencies)
2. **Unit 2** - Builds on Unit 1: uses ESF models and store to write snapshots
3. **Unit 3** - Builds on Unit 1+2: uses ESF for mock mode, tracker for live context
4. **Unit 4** - Builds on all: uses MCP server, DAP proxy, ESF data

## Integration Points

| From | To | Integration |
|------|----|-------------|
| Unit 2 -> Unit 1 | Tracker writes ESF files that MCP server reads | File-based (shared `~/.errordog/snapshots/`) |
| Unit 3 -> Unit 1 | Mock mode loads ESF files via store | In-process import of `SnapshotStore` |
| Unit 3 -> Unit 2 | Live proxy captures state alongside tracker | TBD at Phase 3 design |
| Unit 4 -> Unit 3 | evaluate_expression uses DAP proxy | TBD at Phase 4 design |
| Unit 4 -> Unit 1 | Test generation reads ESF data via store | In-process import of `SnapshotStore` |
