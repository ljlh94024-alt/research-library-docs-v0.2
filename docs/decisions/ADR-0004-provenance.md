# ADR-0004: Provenance 数据模型

**Status:** Accepted  
**Date:** 2026-08-19

## Context

系统必须回答“这条知识为什么成立、来自哪里、由哪个模型和版本产生”。仅保存 URL 不足以审计。

## Decision

采用 Domain Provenance + Processing Provenance 两层。Domain 链为 KnowledgeAtom → ResolvedClaim → Claim → EvidenceLink → Evidence → SourceSnapshot → Source；Processing 链通过 PipelineRun 与 StageRun 表示。

PipelineRun 记录完整处理运行；StageRun 记录 stage_name/version、model/provider、prompt_id/version、input/output refs、状态、时间与错误。关键领域对象保存 created_by_stage_run_id。Provenance append-oriented，人工 override 也记录事件。

## Alternatives Considered

**只保存 URL**：无法解释使用了哪段文本、哪个 Snapshot、哪个 Claim 或哪个模型。

**通用 Graph/Event 模型**：灵活但 MVP 复杂度过高。

## Consequences

增加数据量，但换来审计、重算、debug、模型比较、引用、冲突解释与历史追踪。

## Implementation Rules

Evidence、Claim、ResolvedClaim、KnowledgeAtom 不得成为孤儿对象。无法回答 “Where did this come from?” 的 KnowledgeAtom 不得进入正式知识库。
