# ADR-0018: Phase 1B Deterministic Refinery

## Status

Accepted for Phase 1B review.

## Decision

Phase 1B uses a provider-neutral `SemanticBackend` protocol and an offline
`FixtureSemanticBackend`. The backend returns immutable evidence candidates,
claim candidates, evidence-relation decisions, and dependency signals. The
refinery stages consume those candidates and persisted domain rows; they do not
read fixture expected outcomes or fixture grouping annotations.

The canonical pipeline remains:

```text
evidence_extract -> claim_extract -> normalize -> evidence_link
-> independence -> contradiction -> resolve -> confidence -> atom_build
```

Normalization uses Unicode NFKC, collapsed whitespace, casefolded subject and
predicate, normalized qualifiers, and temporal scope. Object/value is excluded
from the default comparison key. Independence is computed from persisted
`SourceDependency` decisions. Resolution ranks candidate values by effective
independent `SUPPORTS` units; ties or incompatible values are not silently
chosen.

Confidence policy version `deterministic-confidence-v1` uses weights
`0.15/0.20/0.25/0.20/0.10/0.10` for source quality, directness, independence,
agreement, freshness, and extraction confidence. Freshness is calculated from
the fixture reference time. Contradiction penalties are `0/0.3/0.6/1.0` for
none/LOW/MEDIUM/HIGH. A missing floor adds a `0.65` cap; status caps are
CONFLICTING `0.30`, INSUFFICIENT_EVIDENCE `0.40`, UNRESOLVED `0.50`, and
HISTORICAL_CHANGE `0.70`. An atom is ACTIVE only for RESOLVED, floor-met, and
confidence-at-least-`0.75` results.

## Inputs, manifests, and history

Source and SourceSnapshot records are seeded by the fixture ingestion harness
before PipelineRun creation. `evidence_extract` consumes existing snapshot
IDs and owns only Evidence outputs. Every stage writes both input and output
`StageManifest` values to the filesystem `StageManifestStore`. Manifest files
are canonical UTF-8 JSON addressed by SHA-256 and verified on read.

Normal `run()` calls create a new PipelineRun, StageRun set, and formal output
artifact IDs. An explicit recovery key creates a deterministic run identity for
retrying the same interrupted write. Old runs and snapshots remain append-only
and readable. Phase 1B adds no schema or migration and has no real provider,
network, API, embedding, or vector database boundary.

Phase 1C may replace `SemanticBackend` later; it is not started by this ADR.
