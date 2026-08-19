# 本地开发约定

## 推荐环境

Python 3.12+；SQLite；本地 filesystem；pytest。第一阶段尽量减少系统依赖。

## 建议目录

```text
src/research_library/
  domain/
  ingestion/
  refinery/
  retrieval/
  orchestrator/
  storage/
  llm/
  api/
tests/
data/fixtures/
data/snapshots/
```

## 配置

配置通过 `.env` / 环境变量 + typed settings 读取。仓库只提交 `.env.example`，不提交真实 API key。

建议变量：DATABASE_URL、SNAPSHOT_ROOT、LLM_BASE_URL、LLM_API_KEY、LLM_MODEL_EXTRACTOR、LLM_MODEL_REASONER、LOG_LEVEL。

## 本地运行顺序

1. 创建虚拟环境并安装依赖。
2. 初始化 SQLite migration。
3. 运行 `pytest`。
4. 运行 fixture pipeline。
5. 再配置真实模型与来源 adapter。

## 安全底线

任何 secret 不进入日志、StageRun metadata、fixture 或 git。原始 Snapshot 可能含敏感信息，默认仅存本地受控目录，不自动上传第三方。
