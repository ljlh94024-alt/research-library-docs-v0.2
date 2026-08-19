# MVP 实施计划

## 目标

用最少依赖证明完整闭环，而不是先追求算法质量。

## Phase 0：工程骨架

建立包结构、配置、Domain dataclass/model、Repository interface、SQLite migration、snapshot filesystem、FakeLLMClient、基础测试。

完成标准：以 `docs/roadmap/phase-0-acceptance.md` 的 Gate 为准；`pytest` 必须离线可运行，并真实验证 Domain、Snapshot、Repository、Provenance、FakeLLM 与 PipelineRun/StageRun 骨架。

## Phase 1：固定 Fixture 闭环

用 `data/fixtures/` 的本地材料跑通：Snapshot → Evidence → Claim → Normalization → EvidenceLink → Resolution → Confidence → Atom。

完成标准：同一 fixture 可重复运行；Atom 能下钻到原始 SourceSnapshot；PipelineRun/StageRun 完整。

## Phase 2：真实来源 Ingestion

增加 local file 与 HTTP page/document adapter。先不做大规模爬虫。

完成标准：一个 URL/文件可以创建不可变 Snapshot，并进入 Phase 1 的 Refinery。

## Phase 3：独立性与冲突

实现 dependency_group、简单 contradiction candidate、LLM verifier、ResolvedClaim 状态和 confidence penalties。

完成标准：五类基准 fixture 均得到预期状态。

## Phase 4：Retrieval API

实现 Atom 查询、Provenance 查询、PipelineRun 查询和最小 ingest endpoint。

完成标准：上层 Agent 无需直接访问数据库即可查询知识与证据。

## Phase 5：Orchestrator

实现有限状态的研究任务调度：收集来源 → 检查覆盖 → refine → 判断是否继续取证 → 返回结果。

完成标准：不依赖无限 agent loop；预算和 stop condition 可配置。

## 暂缓

复杂 UI、图数据库、独立 vector DB、分布式队列、多租户、知识图谱本体、全网持续爬取、自动训练模型。
