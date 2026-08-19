# ADR-0006: Confidence 模型

**Status:** Accepted  
**Date:** 2026-08-19

## Context

一个单独的 0-1 数字容易制造虚假精确感。需要让 confidence 可解释、可测试、可调整，同时足够简单。

## Decision

第一版采用分量评分 + 可配置加权聚合，并显式应用 contradiction penalty 与 evidence floor。

核心分量为 source_quality、evidence_directness、source_independence、agreement、freshness、extraction_confidence。每个分量范围 0-1，并保存 reasons。最终 score = weighted mean - penalties，再裁剪到 0-1。若缺乏最低直接证据或存在 unresolved high-severity contradiction，可设置发布上限。

## Alternatives Considered

**完全由 LLM 给分**：不可重复、难解释。

**复杂 Bayesian/Truth Discovery**：未来可研究，但 MVP 成本过高。

## Consequences

分数可解释、可通过 fixture 回归测试。代价是初期权重具有启发式性质，需要随着数据积累校准。

## Implementation Rules

任何 confidence 返回都必须能同时返回 components 与 reasons。API 不得只暴露一个裸数字而无法解释来源。
