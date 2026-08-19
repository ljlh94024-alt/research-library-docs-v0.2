# ADR-0011: 测试策略

**Status:** Accepted  
**Date:** 2026-08-19

## Context

Refinery 同时包含纯规则、数据库、模型调用与时间/冲突逻辑，若只做端到端测试会很难定位问题。

## Decision

采用测试金字塔：Domain 单元测试最多；Repository/Pipeline 集成测试次之；少量端到端 fixture 测试验证完整闭环；真实模型测试放在可选 smoke suite。

所有 LLM 阶段使用 FakeLLMClient 提供确定响应。必须维护五类基准 fixture：独立一致、多转载同源、直接冲突、历史更新、限定条件。关键 score 与状态使用 golden assertions。SQLite 测试使用临时数据库和临时 snapshot 目录。

## Alternatives Considered

**全部真实 API 测试**：慢、贵、不稳定。

**只测最终回答**：无法保证 provenance 和中间状态。

## Consequences

测试可以快速运行并保护 Domain 规则。少量真实模型 smoke 仍用于发现 provider/structured-output 兼容问题。

## Implementation Rules

CI 默认不得需要真实 API key；任何 bug 修复都应补回归 fixture 或测试。
