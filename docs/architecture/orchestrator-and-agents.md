# Orchestrator 与 Agent 边界

## 1. 目标

Orchestrator 是研究任务控制层，不是知识事实层。它负责决定做什么、何时补证据、何时停止，而核心数据判断留在可测试的 Refinery 模块中。

## 2. 第一阶段 Agent

- **Source Agent**：发现/获取来源，创建 Source 与 Snapshot。
- **Extraction Agent**：从 Snapshot 产生 Evidence 与 Claim。
- **Refinery Agent**：Normalization、Linking、Independence、Contradiction、Resolution、Confidence。
- **Retrieval Agent**：按任务查询 Atom 与 Evidence，返回 provenance。

## 3. Orchestrator 职责

输入研究任务后：解析目标 → 生成检索计划 → 调用 Source Agent → 检查证据覆盖 → 触发 Refinery → 评估是否需要更多证据 → 调用 Retrieval → 形成上层答复。

## 4. Stop Condition

MVP 不做复杂自主循环。停止条件由显式规则控制，例如达到最低独立证据数、没有 unresolved high-severity contradiction、预算到达上限、来源覆盖达到目标或人工终止。

## 5. 失败处理

单个来源失败不应中止整个任务。StageRun 记录失败；Orchestrator 根据错误类型重试、跳过或降级。不可把异常吞掉后继续生成“正常结论”。

## 6. 不做的事

Orchestrator 不直接写数据库领域表、不在 prompt 中维护唯一状态、不绕过 ConfidenceEngine、不因为“模型很确定”而跳过 EvidenceLink。
