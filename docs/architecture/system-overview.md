# 系统架构总览

## 1. 目标

系统把“资料获取”与“知识形成”分离。Source Layer 负责得到稳定的来源快照；Knowledge Refinery 负责把快照转换为可验证知识；Retrieval / Serving Layer 负责将 KnowledgeAtom 与证据链提供给上层项目。

## 2. 逻辑架构

```text
                 External Sources
                       ↓
                 Source Adapters
                       ↓
                 SourceSnapshot
                       ↓
              Knowledge Refinery
                       ↓
                 KnowledgeAtom
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   Retrieval API   Orchestrator   Provenance API
        ↓              ↓              ↓
      Agents         Projects        Audit/UI
```

## 3. 模块边界

- `domain/`：纯领域对象与状态规则，不依赖 HTTP、数据库或厂商 SDK。
- `ingestion/`：来源获取、内容归一、Snapshot 写入。
- `refinery/`：Evidence、Claim、Normalization、Independence、Contradiction、Resolution、Confidence。
- `retrieval/`：结构化查询、全文查询、可选向量召回、证据下钻。
- `orchestrator/`：面向研究任务的流程调度，不承载核心事实规则。
- `storage/`：Repository 与具体 SQLite/PostgreSQL 实现。
- `llm/`：模型 provider、router、usage、structured output。
- `api/`：对外 HTTP/CLI 接口。

## 4. 关键架构约束

1. Domain 不依赖 Storage 实现。
2. LLM provider 不泄漏到 Refinery 业务层。
3. Snapshot 不可变。
4. KnowledgeAtom 必须有 provenance。
5. Pipeline 各阶段输入输出结构化对象。
6. 失败可以重跑，重跑不应破坏历史。

## 5. 单体模块化优先

MVP 运行在一个进程中。模块通过 Python 接口调用，不拆微服务。只有出现真实的并发、隔离或伸缩需求后才考虑外部队列和独立服务。
