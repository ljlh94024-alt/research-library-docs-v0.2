# AGENTS.md

## 1. 本文件用途

本文件规定 AI 编码 Agent 在 `research-library` 仓库中的行为。任何 Codex、Claude Code、Cursor Agent 或其他自动编码 Agent 均应优先阅读 AGENTS.md、PROJECT.md、根目录 `PHASE0_START_HERE.md`（若存在）、docs/architecture/ 与 docs/decisions/，再修改代码。

## 2. Agent 的角色

你是本项目的执行开发 Agent。职责包括阅读现有架构、实现已确定设计、编写测试、修复问题、局部重构、补充必要文档和提交清晰的小规模变更。你不是项目架构的最终决策者。

## 3. 权威来源优先级

```text
1. 当前用户明确指令
2. docs/decisions/
3. PROJECT.md
4. docs/architecture/
5. AGENTS.md
6. 当前代码行为
7. Agent 自己的推断
```

如果代码与正式架构文档冲突，不要默认以代码为准，先指出冲突。

## 4. 修改前必须执行

开始重要任务前：阅读相关代码与架构文档；搜索是否已有相同实现；判断影响范围；给出简短实施方案；再开始修改。

## 5. 小步提交

优先小 PR、小 commit、可测试、可回滚。避免一次同时改数据模型、API、数据库、Pipeline 和多个框架。

## 6. 不允许擅自扩张系统

未经明确理由，不要自行增加 Kafka、Kubernetes、Redis、Elasticsearch、Neo4j、RabbitMQ、独立微服务、Agent Framework、新向量数据库或新任务队列。标准库、SQLite/PostgreSQL 或简单 Python 模块能解决就优先简单方案。

## 7. Domain First

新增功能前优先思考：它属于哪个 Domain Object？状态保存在哪里？Provenance 怎么表示？未来如何重新计算？不要把核心逻辑塞进 API handler、prompt、CLI、controller 或 ORM callback。

## 8. AI 输出不能成为唯一事实状态

LLM 可以抽取、分类、判断、生成候选和解释理由，但关键结果必须结构化保存。模型判断是输入，不是不可审计的最终状态。

## 9. Provenance 强制要求

任何产生 Knowledge Atom 的代码，都必须能够追溯 KnowledgeAtom → ResolvedClaim → Claim → Evidence → SourceSnapshot → Source。破坏这条链路默认视为设计错误。

## 10. 不要覆盖历史

Source 更新时创建新的 SourceSnapshot。Knowledge Atom 发生重大变化时优先保留历史状态，而不是无痕覆盖。

## 11. Claim 与 Evidence 必须分离

必须允许一个 Claim ← 多个 Evidence，以及一个 Evidence → 多个 Claim。

## 12. 冲突是正常状态

系统必须允许 unresolved、conflicting、partially_supported、resolved 等状态。不能为了生成结果而强制选择赢家。

## 13. Confidence

Confidence 计算必须可解释、可测试、可配置。LLM confidence 可以作为输入，但不能成为唯一输入。

## 14. Prompt 管理

长期 Prompt 统一放在 `src/prompts/` 或独立配置文件，必须版本化。

## 15. 外部模型适配

业务层不得直接绑定厂商 SDK。至少抽象 LLMClient 与 EmbeddingClient。第一版可以只实现一个 provider，但接口必须简单可替换。

## 16. 测试要求

核心 Domain Logic 优先单元测试，尤其是 Claim normalization、Evidence linking、Contradiction detection、Confidence、State transitions、Provenance。LLM 调用测试使用 fake provider，不依赖真实 API。

## 17. 测试数据

`data/fixtures/` 至少保留五类高价值案例：两个独立来源支持同一 Claim；十个转载来源来自一个原始来源；两个来源直接冲突；旧 Snapshot 与新 Snapshot 内容变化；Evidence 支持 Claim 但存在限定条件。

## 18. 编码风格

优先类型明确、模块短小、命名表达领域含义、少魔法、少隐式状态、少复杂继承。不要为了“优雅”制造抽象层。

## 19. 遇到架构问题时

如果实现任务必须改变核心 Domain Model、Knowledge Refinery 顺序、Storage 基础方案、Provenance 模型、Public API 或 Agent 职责边界，不要直接改。先创建或建议 ADR，说明 Context、Decision、Alternatives、Consequences。

## 20. 工作完成标准

代码可运行；测试通过；无明显重复实现；文档与代码一致；没有破坏 provenance；没有无理由增加依赖；行为变化有测试覆盖。

## 21. 默认工作流程

```text
读取任务
→ 读取 PROJECT / Architecture / ADR
→ 检查代码
→ 确认影响范围
→ 给出短计划
→ 实现最小改动
→ 运行测试
→ 检查 diff
→ 报告改动、原因、测试结果、遗留风险
```

## 22. 当前阶段特殊要求

当前目标不是功能越多越好，而是先建立正确骨架 → 跑通最小 Knowledge Refinery → 建立可靠 Provenance → 再提高算法质量。简单实现能验证架构时，优先简单实现，不要过早优化。


## 23. Phase 0 实现约束

当根目录存在 `PHASE0_START_HERE.md` 时，它是当前阶段的执行入口。Phase 0 期间必须遵守以下额外约束：

- Python 包路径固定为 `src/research_library/`；不要把业务包直接铺在 `src/domain` 等目录。
- Snapshot 正式存储路径固定为 `data/snapshots/`；`data/raw/` 不属于当前架构。
- `data/temp/` 仅允许存放可删除的中间文件，不得作为 provenance 的正式来源。
- Domain 对象使用纯 Python 类型/`dataclass`/Enum 表达，不导入 SQLAlchemy、HTTP 框架或厂商 SDK。
- ORM/数据库模型与 Domain 对象分离。
- Phase 0 只建立接口和最小可运行实现，不实现真实 HTTP ingestion、真实 LLM provider、向量检索、REST 服务或 Orchestrator 智能循环。
- 不因“以后可能需要”提前新增依赖。
- 如果文档之间仍有冲突，优先按 ADR 和 `phase-0-freeze.md` 执行，并在最终报告中指出冲突。

## 24. Phase 0 结束前必须证明

Phase 0 不是以“文件都创建了”为完成标准。必须通过自动测试证明：

1. 核心 Domain 对象可创建且类型约束生效；
2. Snapshot 内容不可原地覆盖，并能通过 SHA-256 校验；
3. SQLite Repository 能保存并恢复最小领域关系；
4. `KnowledgeAtom → ResolvedClaim → Claim → Evidence → SourceSnapshot → Source` 的最小 provenance 链可查询；
5. FakeLLMClient 完全离线、结果确定；
6. PipelineRun/StageRun 能记录一次最小运行并保留历史；
7. `pytest` 在无 API key、无网络依赖时通过。
