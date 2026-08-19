# ADR-0003: LLM Provider 抽象

**Status:** Accepted  
**Date:** 2026-08-19

## Context

Refinery 会依赖模型完成 Evidence 判断、Claim extraction、Normalization、Contradiction verification 与 Resolution explanation，但系统需要支持 OpenAI、OpenAI-compatible、local/cheap/strong models，不能把业务代码绑定到一家 SDK。

## Decision

统一通过内部 LLMClient 与 EmbeddingClient 接口。业务层只依赖内部请求/响应对象，Provider 层处理网络、鉴权、重试、解析与 usage。

结构化输出优先。模型按角色配置 fast、extractor、normalizer、reasoner、resolver、embedding；ModelRouter 只做 task_type → model role → provider/model 的简单映射。每次调用记录 provider、model、prompt_id、prompt_version、token usage、latency 与 request_id。测试提供 FakeLLMClient。

## Alternatives Considered

**到处直接调用厂商 SDK**：难替换、难测试、难统一成本统计。

**大型 Agent Framework**：当前需求明确，简单 interface 足够。

## Consequences

可以用便宜模型做 extraction，把强模型留给 difficult resolution，从而控制成本。多 provider 切换不会污染 Domain。

## Implementation Rules

LLM 输出默认为 candidate 而不是 truth；所有长期 Prompt 必须版本化；Domain 层不得处理 HTTP/SDK 异常。
