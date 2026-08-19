# ADR-0005: Pipeline 执行模型

**Status:** Accepted  
**Date:** 2026-08-19

## Context

Refinery 包含多个可失败、可重跑、需要版本化的阶段。MVP 需要既简单又可观测的执行方式。

## Decision

采用进程内同步/异步混合的 PipelineRunner，不引入外部消息队列。一次任务创建 PipelineRun，每个阶段创建 StageRun。阶段接口采用结构化输入输出，可单独重跑。

阶段顺序默认固定：evidence_extract → claim_extract → normalize → evidence_link → independence → contradiction → resolve → confidence → atom_build。允许阶段实现内部并发，但提交领域状态时保持明确事务边界。失败分为 retryable、input_invalid、model_error、internal_error；重试策略由 runner 统一处理。

## Alternatives Considered

**Celery/Kafka/RabbitMQ**：当前规模不需要。

**纯 prompt chain**：缺少状态、审计、重跑与测试边界。

## Consequences

实现简单，适合本地 Codex 与单机开发；未来可把 StageRun 作为迁移到队列的天然任务边界。

## Implementation Rules

阶段不得通过隐式全局状态传递数据；StageRun 必须记录输入输出引用；重跑不得删除旧结果。
