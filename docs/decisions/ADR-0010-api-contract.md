# ADR-0010: 对外 API Contract

**Status:** Accepted  
**Date:** 2026-08-19

## Context

上层项目需要稳定访问 KnowledgeAtom、Evidence 与 Provenance，但 API 不应泄漏数据库内部结构。

## Decision

MVP 提供最小 REST/CLI contract：查询 atoms、读取 atom、读取 provenance、提交 source、触发 ingest/refine、查看 pipeline run。

建议端点：`POST /sources`、`POST /sources/{id}/snapshots`、`POST /pipeline/runs`、`GET /runs/{id}`、`GET /atoms`、`GET /atoms/{id}`、`GET /atoms/{id}/provenance`、`GET /claims/{id}`。响应使用稳定 DTO；分页使用 cursor 或简单 limit/offset；错误返回机器可读 code。

## Alternatives Considered

**直接给上层数据库访问**：耦合 schema，难治理。

**GraphQL from Day One**：对 MVP 价值有限。

## Consequences

接口小而稳定，便于其他 Agent 调用。未来可以增加 MCP/插件层而不改变核心 Domain。

## Implementation Rules

API 默认不返回完整原始文档；敏感/大体积证据按需展开；conflicting 状态必须显式返回。
