# ADR-009: Explainability Framework

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Deciders** | Nexora Engineering |
| **Related** | [Explainability Framework](../xai/explainability_framework.md), [ADR-007](./ADR-007_decision_framework.md), [ADR-008](./ADR-008_rl_optimization_service.md) |

---

## Context

Hyperion agents produce heterogeneous artifacts—reasoning traces, tool outputs, validation results, reflection scores, decision rankings, and RL rejections. Without a unified explainability layer, each agent would embed ad hoc explanation fields in domain reports. Audit, compliance, human-in-the-loop approval, and public transparency require a consistent, machine-readable explanation schema.

Explainability must remain agent-agnostic (like ADR-007 and ADR-008) while consuming the unified decision contract and RL output. It must not fetch memory or graph data directly; agents pass evidence by reference.

---

## Decision

Introduce an **Explainability Framework** in `backend/xai/` centered on `ExplanationEngine`, which transforms pipeline artifacts into a standardized `ExplainabilityReport`.

### Core components

| Component | Module | Responsibility |
|-----------|--------|----------------|
| Orchestrator | `explanation_engine.py` | `explain()`, `explain_pipeline()`, `explain_decision()` |
| Report schema | `explanation_report.py` | `ExplanationInput`, `ExplainabilityReport`, sub-report Pydantic models |
| Models | `explanation_models.py` | `ExplanationType`, `EvidenceSource`, confidence/uncertainty dimensions |
| Reasoning trace | `reasoning_trace.py` | `ReasoningTraceBuilder` — narrative enrichment of `ReasoningResult` |
| Evidence | `evidence_engine.py` | Multi-source evidence collection and categorization |
| Confidence | `confidence_engine.py` | Five-dimension weighted confidence scoring |
| Uncertainty | `uncertainty_engine.py` | Four-dimension uncertainty assessment |
| Alternatives | `alternative_actions.py` | Chosen, alternative, and rejected action analysis |
| Counterfactuals | `counterfactual_engine.py` | What-if scenario generation |

### Explanation scopes

`ExplanationType` gates which sub-engines receive full vs. minimal input:

| Scope | Input artifacts |
|-------|-----------------|
| `REASONING` | Reasoning trace, evidence, confidence |
| `DECISION` | `DecisionRequest` + `DecisionResponse`, alternatives, counterfactuals |
| `RL` | Decision response with RL metadata; rejections and reward breakdown |
| `FULL_PIPELINE` | All artifacts from agent invoke through decision/RL |

### Integration pattern

- **Post-hoc invocation:** Explainability runs at agent boundaries after report generation—not as a LangGraph node in v1.0
- **Agent-agnostic core:** Zero imports from flood, heatwave, or water resource packages
- **Evidence by reference:** Agents pass `memory_references` and entity IDs; XAI does not resolve memory or graph stores
- **Graceful degradation:** Missing artifacts yield empty/default sections, not failures
- **Audit output:** `ExplainabilityReport.to_audit_trace()` produces compliance-ready reasoning traces

### Decision explainability

Full `explain_decision()` requires unified `DecisionRequest` and `DecisionResponse` (ADR-007). RL explainability requires `DecisionResponse` from `RLOptimizationService` (ADR-008).

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Per-agent explanation sections in domain reports | Fragmented schema; no unified audit or API surface |
| Inline explanation during reasoning | Couples explanation to agent logic; harder to test and evolve independently |
| LangGraph explain node in v1.0 | Adds graph complexity before agents stabilize artifact production |
| XAI fetches memory/graph directly | Violates boundary; creates hidden dependencies and complicates testing |
| Single confidence score | Insufficient for climate decisions; multi-dimensional scoring required |
| LLM-generated explanations only | Non-deterministic; unsuitable for audit; structured engines provide baseline |

---

## Pros

- Single `ExplainabilityReport` schema for all agents and API consumers
- Composable sub-engines independently testable and evolvable
- Scope-gated execution avoids unnecessary computation for partial explanations
- Weighted confidence (5 dims) and uncertainty (4 dims) with explicit rationales
- Alternative and counterfactual analysis supports human decision review
- `to_audit_trace()` enables compliance and regulatory reporting
- Graceful degradation allows incremental agent wiring

---

## Cons

- Agents do not auto-wire XAI in production yet; post-hoc pattern requires explicit integration
- Full decision explainability blocked until flood/water migrate to unified decision schema
- Post-hoc invocation adds latency at agent boundary (acceptable for audit use cases)
- Counterfactual quality depends on decision action diversity in `DecisionRequest`
- No direct knowledge graph integration; entity context must be passed in metadata
- LLM narrative enrichment not included in v1.0 structured engines

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Post-hoc vs. in-pipeline | Post-hoc v1.0 | Agents stabilize first; optional LangGraph node later |
| Centralized vs. per-agent | Centralized XAI | Audit and API require one schema |
| Evidence resolution | By reference | Keeps XAI stateless and testable |
| Completeness vs. resilience | Graceful degradation | Partial pipelines still produce useful reports |
| Structured vs. LLM explanations | Structured engines first | Deterministic audit baseline; LLM narrative as future layer |
| Scope granularity | Four explanation types | Balances compute cost with consumer needs |

---

## Consequences

- Agents must collect and pass artifacts (`ExplanationInput`) at invoke completion
- Unified decision migration (ADR-007) unlocks full `explain_decision()` for all hazards
- RL optimization (ADR-008) must embed reward breakdown in `DecisionResponse` metadata for RL scope
- API layer can expose `ExplainabilityReport` JSON and `to_audit_trace()` without domain adapters
- Tests live in `backend/tests/xai/`; no production agent imports yet

---

## Future Impact

- Optional LangGraph `explain` node for workflows requiring inline explanation before response delivery
- Knowledge graph `ReasoningInsight` objects (ADR-010) feed `EvidenceEngine` via agent-passed metadata
- LLM narrative layer atop structured reports for public-facing summaries
- Human-in-the-loop gates keyed on `is_high_confidence` and uncertainty thresholds
- Real-time explanation streaming for long-running multi-agent workflows
