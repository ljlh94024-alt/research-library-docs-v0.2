# Phase 0 Freeze Review & Repair

**Review target:** Draft PR #1
**Base SHA:** `01e0ce8da792361614a4baf87110d81ea0ea09f1`
**Original PR head:** `827b33151d28d1c8a8e491bb333475b46cde5ebc`
**Final repaired SHA:** recorded in the final handoff after push
**Scope:** Phase 0 freeze candidate only

## Findings and resolutions

| Finding | Resolution |
| --- | --- |
| F-001 real legacy migration mismatch | `0001_phase0` now explicitly includes the six historical nullable String processing columns without FKs. `0002` adds only their FKs and adds the three genuinely new columns. An independent `01e0ce8` fixture, parity test, stamp upgrade, and downgrade parity test protect the boundary. |
| F-002 mutable provenance rewrite | Source, Contradiction, PipelineRun, and StageRun now separate immutable identity/provenance fields from allowed lifecycle fields. Terminal states allow exact replay only. |
| F-003 nullable processing provenance | `ProcessingGap(reason="not_recorded")` records legal NULL attribution; missing non-NULL StageRun or PipelineRun remains a hard integrity error. |
| F-004 Snapshot transaction boundary | Snapshot insert and persisted-row read occur inside one transaction. Commit-uncertain failures never trigger filesystem cleanup. |
| F-005 legacy test circularity | Tests build the legacy schema independently and stamp it as `0001_phase0` before upgrading to head. |
| F-006 CI duplication/coverage | CI runs for pull requests, `main` pushes, and manual dispatch; it now includes compileall and PR diff checking. |

## Last-mile findings and resolutions

| Finding | Resolution |
| --- | --- |
| F-007 SQLite populated legacy migration under FK enforcement | Repository-managed and standalone Alembic upgrades now use a controlled SQLite migration window with FK enforcement temporarily disabled, `PRAGMA foreign_key_check` before commit, rollback on violations, and FK restoration to ON. Populated and corrupt legacy databases cover both paths. |
| F-008 terminal Pipeline/Stage lifecycle closure | New runs and stages must start in `STARTED`; terminal pipelines cannot receive new stages; pipeline terminal transitions validate child stage states; Domain objects reject incoherent timestamps and error fields. |
| F-009 Repository protocol parity | `Repository` now exposes `get_resolved_claim`, `create_snapshot`, and `read_snapshot` with concrete-compatible signatures. |
| F-010 direct Snapshot integrity | Public snapshot saves verify filesystem existence and SHA-256 before DB persistence, including exact replay; missing content is reported as `SnapshotIntegrityError`. |

## Review evidence

- Migration fresh, real legacy stamp upgrade, numeric conversion, downgrade parity,
  and re-upgrade are covered offline.
- Lifecycle identity protection, legal transitions, terminal rewind rejection,
  append-only entities, and processing provenance full/partial/corrupt cases are covered.
- Snapshot source/stage prevalidation, rollback cleanup, existing-file preservation,
  divergent replay, hash verification, and no post-commit database read are covered.
- Populated legacy upgrades through Repository and standalone Alembic paths,
  invalid legacy rollback, terminal lifecycle closure, Domain state coherence,
  Repository protocol parity, and direct Snapshot boundary checks are covered.
- Final last-mile local suite currently passes 66 tests; the final pushed head
  and GitHub CI result are recorded in the handoff report.
- No runtime or development dependencies were added.
- No Phase 1 capability is included.

## Freeze recommendation

Candidate for supervisor review after the final local and GitHub CI gates pass.
This review does not merge the PR, mark it ready, create a tag, or declare the
Phase 0 freeze complete.
