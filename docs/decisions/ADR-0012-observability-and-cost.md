# ADR-0012: 可观测性与成本

**Status:** Accepted  
**Date:** 2026-08-19

## Context

Refinery 的失败可能来自来源、解析、模型、规则或存储；同时模型成本可能快速放大。需要轻量可观测性。

## Decision

MVP 使用结构化日志 + PipelineRun/StageRun 指标，不引入独立 observability platform。

每阶段记录 duration、status、retry_count、input/output count、provider/model、token usage、estimated_cost、error_code。应用日志使用 JSON 或结构化字段。提供简单 CLI/endpoint 汇总单次 pipeline 的时间和成本。

## Alternatives Considered

**Prometheus/Grafana/OTel 全家桶**：早期过重。

**只 print 日志**：难关联一次 pipeline。

## Consequences

本地开发可快速定位瓶颈并比较模型成本；未来可无缝把结构化指标接到标准 observability 系统。

## Implementation Rules

任何模型调用必须能归属到 StageRun；费用未知时记录 null 而不是伪造。
