# Phase 1 Refinery Contracts

Phase 1A defines the typed boundaries of the Knowledge Refinery without
implementing semantic behavior. Every input and output is a frozen, slotted
dataclass containing stable IDs, so a stage can be rerun without passing
implicit global state.

## Canonical stage sequence

```text
evidence_extract
→ claim_extract
→ normalize
→ evidence_link
→ independence
→ contradiction
→ resolve
→ confidence
→ atom_build
```

The ownership boundary is:

| Stage | Output |
| --- | --- |
| evidence_extract | `Evidence` |
| claim_extract | `Claim` |
| normalize | `ClaimGroup` and membership |
| evidence_link | `EvidenceLink` |
| independence | `SourceDependency` |
| contradiction | `Contradiction` |
| resolve | `ResolutionDecision` and explicit decision inputs |
| confidence | `ConfidenceAssessment` and final `ResolvedClaim` |
| atom_build | `KnowledgeAtom` |

`StageContext` carries `pipeline_run_id`, `stage_run_id`, and the repository.
The repository remains the persistence boundary; contracts do not import an
LLM SDK, make network calls, or decide semantic truth.

## Persistence and provenance

All formal result objects are append-only. A final resolved claim links to one
decision and one confidence assessment, and the repository checks that the
group, canonical statement, status, and score agree. A provenance chain returns
both the candidate ClaimGroup members and the explicit resolver Claim/Evidence
inputs. Processing provenance includes the owning StageRun and PipelineRun for
each attributed object.

## Phase boundary

Phase 1A supplies contracts and persistence only. Deterministic fixture
processing, source-independence heuristics, contradiction resolution, and
confidence weighting are intentionally deferred to Phase 1B.
