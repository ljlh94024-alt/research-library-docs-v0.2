# ADR-0013: Ingestion 边界与 Source Adapter

**Status:** Accepted  
**Date:** 2026-08-19

## Context

来源种类会持续增加。如果把网页、PDF、GitHub、API 的抓取细节直接散落在 Refinery 中，会造成强耦合。

## Decision

引入 SourceAdapter 接口，Ingestion 只负责“从逻辑 Source 得到标准化 Snapshot”，不负责 Claim 推理。

SourceAdapter 输出 normalized content + raw artifact refs + metadata + locator mapping。第一批只实现 local file、HTTP page/document、GitHub text/file 等少量适配器。抓取失败与内容解析失败分别记录错误。

## Alternatives Considered

**每种来源单独一套 Pipeline**：重复核心 Refinery。

**统一转纯文本后丢弃结构**：损失 locator 和表格/页面信息。

## Consequences

后续增加来源只影响 ingestion 层；Refinery 复用统一 Snapshot/Evidence 模型。

## Implementation Rules

Adapter 不得直接写 KnowledgeAtom；必须保留 raw artifact 与可定位结构；robots/auth/licensing 由调用环境遵守。
