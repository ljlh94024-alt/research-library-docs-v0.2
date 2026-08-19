# Phase 0 验收标准

**Status:** Active  
**Date:** 2026-08-19

## 1. 验收目标

Phase 0 证明的是：

> 这个仓库已经具备实现 Knowledge Refinery 的可靠工程地基。

它不证明真实模型抽取质量，也不证明真实网页 ingestion。

## 2. 必须通过的 Gate

### Gate A：Package / Config

- [ ] `src/research_library/` 可正常 import；
- [ ] Python 版本约束与 ADR-0015 一致；
- [ ] `.env.example` 不含真实 secret；
- [ ] settings 有合理默认值，可在无 API key 条件下运行测试。

### Gate B：Domain

至少可创建并验证：

- [ ] Source；
- [ ] SourceSnapshot；
- [ ] Evidence；
- [ ] Claim；
- [ ] ClaimGroup；
- [ ] EvidenceLink；
- [ ] Contradiction；
- [ ] ResolvedClaim；
- [ ] KnowledgeAtom；
- [ ] PipelineRun；
- [ ] StageRun。

并满足：

- [ ] Domain 不依赖 SQLAlchemy/HTTP/provider SDK；
- [ ] 时间采用 UTC aware datetime；
- [ ] 核心持久化对象具有稳定应用 ID。

### Gate C：Snapshot

- [ ] 内容保存到配置的 Snapshot root；
- [ ] `content_ref` 是可迁移的相对路径；
- [ ] SHA-256 可复算并与记录一致；
- [ ] 同一 Snapshot 不通过普通 update 原地替换原始内容；
- [ ] 测试使用临时目录。

### Gate D：Database / Repository

- [ ] migration 能从空 SQLite 建立 Phase 0 schema；
- [ ] Repository contract 与 SQLite implementation 分离；
- [ ] 能保存/读取核心 Domain 记录；
- [ ] SQLite 特有对象不会泄漏到 Domain；
- [ ] JSON 只承担 metadata/qualifier/extension，不代替核心关系表。

### Gate E：Provenance

至少一个集成测试必须构造并持久化：

```text
Source
→ SourceSnapshot
→ Evidence
→ Claim
→ ClaimGroup
→ ResolvedClaim
→ KnowledgeAtom
```

然后从 `KnowledgeAtom` 起重新查询到 `Source`。

验收：

- [ ] 不是只靠测试内存对象拼接；
- [ ] 数据至少经过 Repository round-trip；
- [ ] Evidence 与 Claim 的关系显式保存；
- [ ] 不存在只有 Atom→URL 的简化替代。

### Gate F：LLM abstraction

- [ ] `LLMClient` contract 存在；
- [ ] request/response 是内部类型；
- [ ] `FakeLLMClient` 可返回确定 fixture；
- [ ] 默认测试完全不联网；
- [ ] Domain/Refinery 不直接 import 厂商 SDK。

### Gate G：Pipeline run skeleton

- [ ] 可创建 `PipelineRun`；
- [ ] 可创建至少一个 `StageRun`；
- [ ] Stage 有 started/succeeded/failed 等基本状态；
- [ ] run/stage 可持久化；
- [ ] 第二次运行不会物理删除第一次运行历史；
- [ ] 可记录 pipeline/stage version；
- [ ] Fake stage 的失败可以被记录，而不是吞掉异常状态。

### Gate H：Tests

默认：

```bash
pytest
```

必须：

- [ ] 不要求网络；
- [ ] 不要求 API key；
- [ ] 不依赖本机固定绝对路径；
- [ ] 不污染正式 data 目录；
- [ ] 可重复执行。

若启用 Ruff：

```bash
ruff check .
```

也应通过。

## 3. Phase 0 不验收的内容

以下失败/缺失不阻止 Phase 0 通过，因为属于后续阶段：

- 真实 URL ingestion；
- PDF/网页解析质量；
- LLM Claim Extraction；
- Source Independence 算法；
- Contradiction Detection 算法；
- Confidence 真实公式；
- Retrieval API server；
- Orchestrator 自动研究；
- Embedding/vector search。

不要为追求这些内容延迟 Phase 0。

## 4. Phase 0 通过后的交付状态

通过后仓库应可以回答：

1. 一个 Snapshot 在哪里、哈希是什么？
2. 一个 KnowledgeAtom 是通过哪些 Domain 对象追溯到哪个 Source 的？
3. 哪个 PipelineRun/StageRun 产生了关键对象？
4. 如何在无真实模型、无网络环境重跑测试？
5. 如何新增 Phase 1 的 Refinery stage 而不改写 Domain/Storage 基础边界？

若以上问题仍只能靠开发者口头解释，Phase 0 尚未完成。
