# Documentation Growth Protocol

> **Purpose:** Ensure documentation automatically grows after every future implementation.

---

## When to Update Documentation

Documentation updates are **mandatory** after every implementation prompt that adds or modifies application code. Documentation-only prompts (like this one) update the `docs/` tree directly.

---

## Checklist After Every Implementation

### 1. Development Log (Required)

Create the next numbered file in `docs/development_logs/`:

```
docs/development_logs/NNN_<component_name>.md
```

Use the template in [development_log_template.md](./development_log_template.md).

### 2. Component Documentation (Required if new module)

Create or update the component doc:

```
docs/<layer>/<component>.md
```

Example: `docs/agents/flood_agent.md` when flood agent is implemented.

### 3. Architecture Decision Record (Required if architectural choice made)

Create:

```
docs/decisions/ADR-NNN_<title>.md
```

### 4. Changelog (Required)

Add entry under `[Unreleased]` or new version in `CHANGELOG.md`.

### 5. Progress Tracker (Required)

Update `docs/engineering/progress_tracker.md` — move items from Not Started → In Progress → Completed.

### 6. Test Documentation (Required if tests added)

Update `docs/testing/unit_test_summary.md` with new test counts and results tables.

### 7. Diagrams (Required if flow changed)

Update or add Mermaid diagrams in `docs/diagrams/`.

### 8. Debugging History (Required if bugs encountered)

Add entries to `docs/testing/debugging_history.md`.

---

## Numbering Convention

| Series | Location | Example |
|--------|----------|---------|
| Development logs | `docs/development_logs/` | `004_flood_agent.md` |
| ADRs | `docs/decisions/` | `ADR-006_flood_agent_design.md` |
| Component docs | `docs/<layer>/` | `docs/agents/flood_agent.md` |

---

## Review Cadence

| Review | Frequency | Owner |
|--------|-----------|-------|
| Development log accuracy | After each implementation | Implementing engineer |
| Progress tracker | Weekly | Tech lead |
| ADR validity | Quarterly | Architecture board |
| Full doc audit | Before each milestone release | Documentation engineer |

---

## Quality Gate

No implementation is considered **complete** until:

1. All tests pass (`124+` and growing)
2. Development log exists with full test tables
3. Component documentation updated
4. `CHANGELOG.md` updated
5. Progress tracker reflects new status
