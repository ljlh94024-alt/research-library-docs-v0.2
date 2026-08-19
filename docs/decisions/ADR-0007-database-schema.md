# ADR-0007: MVP 数据库 Schema

**Status:** Accepted  
**Date:** 2026-08-19

## Context

领域对象已经确定，需要一版足以落地 MVP、又不把未来演化锁死的关系模型。

## Decision

使用显式主表与关系表，不使用单一 JSON document 表承载全部领域状态。JSON 仅用于 metadata、qualifiers、可变扩展字段。

核心表：sources、source_snapshots、evidence、claims、claim_groups、claim_group_members、evidence_links、source_dependencies、contradictions、resolved_claims、knowledge_atoms、pipeline_runs、stage_runs、human_overrides。所有表使用稳定字符串/UUID 主键；关键外键建索引；statement/text 可建立 FTS 辅助索引。

## Alternatives Considered

**单一 events 表**：查询与约束复杂。

**全部 JSON**：难保证 referential integrity，后续查询成本高。

## Consequences

关系清晰、可约束、便于 SQLite/PostgreSQL 迁移。代价是迁移脚本会更多，但这是核心知识系统可接受的成本。

## Implementation Rules

schema migration 必须版本化；不要依赖 ORM 自动“猜”生产迁移；软状态优先于物理删除。
