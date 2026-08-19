# PROJECT.md

## Research Library / 研究资料库

### 1. 项目定位

本项目是一个面向其他 AI 项目、Agent 和研究任务提供资料与知识底座的基础工程。

它不是普通的 RAG 文档库，也不是单纯的向量数据库。核心目标是把互联网、论文、代码仓库、文档等原始资料，经过一系列可追溯、可验证、可更新的处理，转化为结构化的 Knowledge Atom（知识原子），供上层 AI 稳定调用。

整体形态：

```text
上层项目 / AI / Agent
        ↓
Research Library API
        ↓
中控 Orchestrator
   ┌────┼────┐
   ↓    ↓    ↓
Source  Knowledge  Retrieval /
Layer   Refinery   Serving Layer
```

### 2. 核心原则

#### 2.1 原始资料不等于知识

系统必须明确区分 Source、Evidence、Claim、Resolved Claim 与 Knowledge Atom。抓到网页或论文，不代表系统已经“知道”其中的信息。

#### 2.2 所有知识必须可追溯

任何 Knowledge Atom 都必须能够向下追溯：

```text
Knowledge Atom → Resolved Claim → Claim → Evidence → SourceSnapshot → Source
```

禁止生成无法解释来源的“孤儿知识”。

#### 2.3 保留原始证据

系统应保存不可变或版本化的 SourceSnapshot，以便未来重新提取、验证模型错误、检查来源变更、重建知识和审计。

#### 2.4 来源数量不等于独立证据数量

多个网站可能来自同一新闻稿、同一论文或相互转载。系统必须尽可能判断 Source Independence，避免把一份原始证据通过转载放大成“多份共识”。

#### 2.5 冲突不能被摘要掩盖

不同来源出现矛盾时，不允许简单平均或任意选择一方。冲突必须显式进入 Contradiction Detection → Claim Resolution → Confidence。

#### 2.6 中小项目优先

项目当前优先简单、可运行、可替换、可测试、可观察。避免过早引入分布式系统、Kubernetes、复杂微服务、重型知识图谱平台和多数据库拼装。

### 3. 核心流水线

```text
Raw Source
  ↓
SourceSnapshot
  ↓
Evidence Candidate
  ↓
Claim Extraction
  ↓
Claim Normalization
  ↓
Evidence Linking
  ↓
Source Independence
  ↓
Contradiction Detection
  ↓
Claim Resolution
  ↓
Confidence
  ↓
Knowledge Atom
```

这是项目最核心的 Knowledge Refinery。

### 4. 核心数据对象

- **Source**：逻辑来源，例如 URL、GitHub Repository、Paper、PDF、Book、API、Dataset。
- **SourceSnapshot**：某个时间点获取到的来源内容，必须有 source_id、retrieved_at、content_hash、content_ref 和 metadata。
- **EvidenceCandidate / Evidence**：Snapshot 中可能具有事实意义的片段，保留 locator、原文和上下文。
- **Claim**：Evidence 中抽取出的独立事实陈述。
- **NormalizedClaim / ClaimGroup**：将不同表达统一到可比较的语义对象。
- **EvidenceLink**：描述 Claim 与 Evidence 的 supports、contradicts、qualifies、mentions 等关系。
- **SourceIndependence**：记录 dependency_group、independence_score、可能父来源和理由。
- **Contradiction**：显式记录两个或多个 Claim 的冲突。
- **ResolvedClaim**：经过证据评估后的当前最佳结论，保留状态、置信度、支持/反对证据和时间范围。
- **KnowledgeAtom**：最终向上层提供的最小知识单元，必须能回溯到证据链。

### 5. 中控 Orchestrator

中控 AI 负责理解研究任务、拆解任务、选择数据源、调用底层 Agent、控制流程、判断是否需要更多证据、质量控制、冲突升级与最终输出。

核心原则：**AI 负责判断，代码负责约束，数据负责留痕。** 关键状态不能只存在模型上下文中。

### 6. Agent 类型

第一阶段控制为四类：Source Agent、Extraction Agent、Refinery Agent、Retrieval Agent。暂时不要继续拆成十几个微型 Agent。

### 7. 存储策略

开发早期使用 SQLite + 本地 filesystem。稳定后迁移到 PostgreSQL + 文件/对象存储，并按需引入 pgvector。Embedding 是检索手段，不是知识主存储。

### 8. 检索模型

查询优先走结构化条件 + 全文检索 + 可选向量召回，优先返回 Knowledge Atom，必要时再下钻到 Evidence 与 SourceSnapshot。

### 9. Provenance

Provenance 是一级功能。至少支持 Knowledge Atom → Claim → Evidence → Snapshot → Source 的下钻，以及 Source → Snapshot → Evidence → Claim → Atom 的反向查询。

### 10. 更新机制

同一 Source 可以有多个 Snapshot。新 Snapshot 不删除旧知识，而应触发 change detection → claim re-evaluation → knowledge update。旧 Atom 可进入 superseded、invalid、historical 等状态。

### 11. Confidence

Confidence 不由 LLM 单独拍一个数字。第一版综合 source_quality、evidence_strength、independent_source_count、contradiction_level、freshness、extraction_confidence，并保留可解释的分量。

### 12. 第一阶段不做

不做大规模 Knowledge Graph、自动 Truth Discovery 算法全集、分布式爬虫集群、多租户 SaaS、图数据库、数十个 Agent、自动训练模型、复杂本体系统和全自动世界知识同步。

### 13. MVP

MVP 必须完整跑通：输入 URL/文档 → Snapshot → Evidence → Claim → Normalize → Link Evidence → 简单冲突检测 → Confidence → Knowledge Atom → API 查询 → Atom + Evidence + Source。

### 14. 推荐仓库结构

```text
research-library/
├── AGENTS.md
├── PROJECT.md
├── README.md
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── operations/
│   └── roadmap/
├── src/
│   └── research_library/
│       ├── domain/
│       ├── ingestion/
│       ├── refinery/
│       ├── retrieval/
│       ├── orchestrator/
│       ├── storage/
│       ├── llm/
│       └── api/
├── tests/
├── data/
│   ├── snapshots/
│   ├── fixtures/
│   └── temp/
└── scripts/
```

### 15. Phase 0 架构冻结

进入第一阶段实现前，Codex/开发 Agent 还必须阅读根目录 `PHASE0_START_HERE.md`、`docs/architecture/phase-0-freeze.md`、`docs/decisions/ADR-0014-repository-layout.md`、`docs/decisions/ADR-0015-python-foundation.md` 与 `docs/roadmap/phase-0-acceptance.md`。

Phase 0 期间，目录结构、基础依赖、Snapshot 路径、Domain/Storage 分层和 Provenance 最小链路视为冻结；若实现必须改变这些约束，应先提出 ADR，不得静默调整。

### 16. 当前最高优先级

Domain Model → SourceSnapshot → Evidence → Claim → Knowledge Refinery Pipeline → Knowledge Atom → Provenance → Retrieval API → Orchestrator → 外部集成。

项目是否成功，主要取决于 Knowledge Refinery，而不是爬虫数量或向量检索效果。
