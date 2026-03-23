# Unit of Work Plan

## Plan Steps

- [x] Define 4 units of work (one per phase)
- [x] Define unit dependencies (sequential: Phase 1 -> 2 -> 3 -> 4)
- [x] Map requirements to units
- [x] Generate unit-of-work.md
- [x] Generate unit-of-work-dependency.md
- [x] Generate unit-of-work-story-map.md (requirements mapping, since user stories were skipped)
- [x] Document code organization strategy (greenfield)
- [x] Validate unit boundaries and dependencies

---

## Decomposition Strategy

Units map directly to the 4 project phases as defined in `errordog_plan.md` and confirmed by the user's delivery preference (one phase at a time with review):

| Unit | Phase | Key Deliverable |
|------|-------|-----------------|
| Unit 1 | Phase 1: Core MCP Server & ESF | MCP server + ESF schema |
| Unit 2 | Phase 2: Python Runtime Tracker | Exception hook + snapshot capture |
| Unit 3 | Phase 3: Hybrid DAP Server | DAP proxy + mock mode |
| Unit 4 | Phase 4: AI Hypothesis Testing | evaluate, test gen, IDE automation |

**No questions required** - decomposition is fully determined by the phased delivery model.
