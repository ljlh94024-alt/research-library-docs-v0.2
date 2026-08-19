# Phase 1 Refinery Contracts

Phase 1A defines the typed boundaries of the Knowledge Refinery. Phase 1B
implements deterministic semantic behavior over those boundaries; no external
provider is part of this phase. Every input and output is a frozen, slotted
dataclass containing copied immutable ID tuples, so a stage can be rerun without
passing implicit global state or retaining mutable caller collections.

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

The storage boundary validates that an attributed result in a `phase1*`
pipeline was created by the matching canonical `StageRun`. Resolution and
confidence-only outputs apply the same owner check whenever a stage run is
provided. A null stage reference remains legal for legacy/manual provenance.

`StageContext` carries `pipeline_run_id`, `stage_run_id`, and the repository.
The repository remains the persistence boundary; contracts do not import an
LLM SDK, make network calls, or decide semantic truth.

## Persistence and provenance

All formal result objects are append-only. A final resolved claim links to one
decision and one confidence assessment, and the repository checks that the
group, canonical statement, status, and score agree. A provenance chain returns
both the candidate ClaimGroup members and the explicit resolver Claim/Evidence
inputs. Each `ClaimGroupMembership` carries nullable legacy-compatible creation
and stage-attribution fields; attributed normalize memberships are included in
processing provenance with their owning StageRun and PipelineRun. Processing
provenance includes the owning StageRun and PipelineRun for every other
attributed object as well.

`RefineryStage` is the structural execution protocol: a stage exposes `name`,
`version`, and a typed `run(StageContext, input) -> output`. Collection fields
reject bare strings and blank IDs, allow empty results, and copy all accepted
iterables into tuples during construction.

The repository also supports querying `SourceDependency` by either `source_id`
or `dependency_group`, independently or together.

## Phase 1B deterministic implementation

`FixtureSemanticBackend` supplies five frozen golden fixtures entirely from
local data. `DeterministicRefinery` executes the nine stages in the canonical
order with stable pipeline, stage, and artifact IDs. Each stage records a
content-addressed `StageManifest`; replaying the same fixture and pipeline
version reuses the same IDs and terminal lifecycle records without creating a
second history row.

Phase 1B policies are explicit and versioned: normalization creates canonical
claim groups, independence collapses shared-origin reposts, contradiction
detects incompatible claims, resolution emits canonical statuses and explicit
inputs, confidence records explainable component scores and publication caps,
and atom build applies the ACTIVE/WITHHELD publication gate. Snapshot content
remains append-only, so historical results remain readable after later
snapshots.

The deterministic backend does not import an LLM SDK, call a network or API,
create embeddings, or use a vector database. A future structured provider seam
belongs to Phase 1C and is not started here.
