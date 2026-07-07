# Development Workflow

> **Last Updated:** 2026-07-07

---

## Overview

Hyperion Climate Twin follows a layered implementation workflow. Each layer builds on the previous without modifying existing code.

```
Foundation → Memory → Climate Supervisor → Domain Supervisors → Specialized Agents → RL / Simulation / Copilot
```

---

## Implementation Rules

1. **Never modify existing layers** when implementing a new layer — only add new files.
2. **All agents** communicate through `MemoryManager` for memory operations.
3. **All user requests** pass through `ClimateSupervisor` first.
4. **Domain supervisors** manage only their own specialized agent registries.
5. **Specialized agents** inherit from `BaseAgent` and register with their domain supervisor.

---

## Local Development Setup

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.12+ |
| pip | Latest |
| Git | Any recent |

### Install

```bash
cd Hyperion
python -m pip install -r requirements.txt
python -m pip install pytest pytest-asyncio
```

### Run Tests

```bash
PYTHONPATH=. python -m pytest backend/tests -v
```

### Environment Variables

All configuration uses the `HYPERION_` prefix. See [configuration.md](../architecture/configuration.md).

```bash
export HYPERION_ENVIRONMENT=development
export HYPERION_LOG_LEVEL=DEBUG
```

---

## Branch Strategy (Recommended)

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready releases |
| `develop` | Integration branch |
| `feature/<name>` | Individual feature implementations |
| `docs/<name>` | Documentation-only changes |

---

## Code Review Checklist

- [ ] No modifications to prior layer source files (unless bugfix with ADR)
- [ ] All new public APIs have docstrings
- [ ] Strict typing throughout
- [ ] Tests added and passing
- [ ] Memory accessed only via `MemoryManager`
- [ ] Development log created
- [ ] CHANGELOG updated
- [ ] Component documentation created/updated

---

## Release Process

1. Verify all tests pass (current gate: 124+)
2. Update `CHANGELOG.md` with version bump
3. Update `docs/engineering/progress_tracker.md`
4. Tag release: `git tag v0.x.0`
5. Deploy (when deployment layer exists)
