# 文档清单

## 根目录

- `PROJECT.md` — 项目定位、核心原则、MVP 和总体优先级。
- `AGENTS.md` — AI 编码 Agent 的全局行为规则。
- `PHASE0_START_HERE.md` — **当前 Codex 开工入口；Phase 0 先读此文件。**
- `README.md` — 项目入口说明。

## Architecture

- `docs/architecture/system-overview.md`
- `docs/architecture/knowledge-refinery.md`
- `docs/architecture/data-and-provenance-flow.md`
- `docs/architecture/orchestrator-and-agents.md`
- `docs/architecture/retrieval-and-serving.md`
- `docs/architecture/update-and-versioning.md`
- `docs/architecture/phase-0-freeze.md` — **Phase 0 当前冻结边界。**

## ADR

- `docs/decisions/ADR-0001-domain-model.md`
- `docs/decisions/ADR-0002-storage.md`
- `docs/decisions/ADR-0003-llm-provider.md`
- `docs/decisions/ADR-0004-provenance.md`
- `docs/decisions/ADR-0005-pipeline-execution.md`
- `docs/decisions/ADR-0006-confidence-model.md`
- `docs/decisions/ADR-0007-database-schema.md`
- `docs/decisions/ADR-0008-source-independence.md`
- `docs/decisions/ADR-0009-contradiction-resolution.md`
- `docs/decisions/ADR-0010-api-contract.md`
- `docs/decisions/ADR-0011-testing-strategy.md`
- `docs/decisions/ADR-0012-observability-and-cost.md`
- `docs/decisions/ADR-0013-ingestion-boundaries.md`
- `docs/decisions/ADR-0014-repository-layout.md` — **统一 `src/research_library/` 与 `data/snapshots/`。**
- `docs/decisions/ADR-0015-python-foundation.md` — **冻结 Phase 0 最小 Python 技术栈。**
- `docs/decisions/ADR-0016-phase0-persistence-hardening.md` — **持久化完整性与版本演进规则。**
- `docs/decisions/ADR-0017-phase1-refinery-domain.md` — **Phase 1A Refinery Domain、决策、置信度与发布状态。**
- `docs/decisions/ADR-0019-phase1c-structured-llm.md` — **Phase 1C 结构化 LLM 边界、审计与非目标。**

## Versions

- `docs/versions/phase-0-final-hardening.md` — **Phase 0 持久化完整性加固版本说明。**

## Reviews

- `docs/reviews/phase-0-freeze-review.md` — **PR #1 冻结前二次审计、修复与复核记录。**
- `docs/reviews/phase-1-entry-notes.md` — **Phase 1 入口观察项；本版本不实现。**

## Roadmap

- `docs/roadmap/mvp-plan.md`
- `docs/roadmap/non-goals.md`
- `docs/roadmap/phase-0-acceptance.md` — **Phase 0 验收 Gate。**
- `docs/roadmap/phase-1-plan.md` — **Phase 1A/1B/1C/1D 分阶段计划与冻结 fixture 预期。**

## Phase 1 Architecture

- `docs/architecture/phase-1-refinery-contracts.md` — **Phase 1A 九阶段 typed contracts 与 ownership。**
- `docs/architecture/phase-1c-llm-boundary.md` — **Phase 1C stage-aware semantic seam、trace 与审计流。**

## Operations

- `docs/operations/local-development.md`
