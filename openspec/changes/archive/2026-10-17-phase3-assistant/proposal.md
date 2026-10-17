# Proposal — 三期：智能客服入口与 RAG 问答

## Why

二期把知识变成了「可发布、可检索、可追溯」的资产，但还没有任何**对话入口**：客户仍然只能翻文档或打人工，客服主管也拿不到"这条回答引用了哪一版哪一行"的证据。三期要交付老板口径里的"智能客服入口 + RAG + 类似微信对话框 + 流式回答"。

三期的价值不在"能聊天"，而在**答案可被追问、可被追责**：每条回答必须能回指二期已发布的切片（document_id + version + 行号），不能回指就拒答或转人工。

## What Changes

- **新增 `assistant` schema**：`conversation`、`message`、`citation`、`handoff`、`identity_verification`、`retrieval_trace` 六张表；不改 `knowledge`/`commerce`/`shared` 任何既有表。
- **对话入口**：客户侧 SSE 流式问答接口 + 会话列表；同一会话可多轮，上下文按"最近 N 轮 + 检索结果"组装。
- **RAG 编排（LangGraph 轻图）**：意图识别 → 检索（调二期 `knowledge_retrieval.search`）→ 身份核验分支 → 生成（带引用）→ 输出护栏。
- **引用与拒答**：回答正文附结构化引用；检索为空或低于阈值时**不得编造**，走拒答话术或转人工。
- **身份核验**：订单号 + 收货手机后四位；核验通过后签发**会话级**可见范围（只能看该客户的订单）。
- **转人工**：高风险规则命中、用户主动要求、核验连续失败、低置信度 → 生成 handoff，客服在工作台接单。
- **客服工作台**：会话列表 + 对话窗口（微信样式：气泡、时间、输入区）+ 引用侧栏 + 转人工处理。
- **可观测**：每次问答写 `retrieval_trace`（query、命中、引用、耗时、模型、token），回答级可复盘。
- **权限码**：`ai:chat:{read,write}`、`ai:handoff:{read,write}`、`ai:trace:read`；仍为三段式。
- **契约**：新增 OpenAPI 路径；SSE 事件格式写入 `docs/三期对话协议.md`（本期不引入 AsyncAPI 工具链）。

**明确不做（属四期）**：本体、工具调用（查订单/查商品）、多步工作流编排、离线评测集与回归门禁。三期只做"知识问答 + 受控转人工"；订单状态类问题**只回答知识与规则，不查实时订单**。

## Capabilities

### New Capabilities

- `assistant-conversation`: 会话与消息的生命周期、SSE 流式输出、会话归属与权限、上下文窗口与限流。
- `assistant-answer`: 意图识别、检索编排、带引用的答案生成、拒答边界、回答护栏、问答链路留痕。
- `assistant-handoff`: 身份核验（订单号 + 手机后四位）、会话级可见范围、转人工触发条件与交接记录。
- `assistant-console`: 客服工作台与客户对话窗口的界面行为——消息气泡、流式渲染、引用展示、转人工处理。

### Modified Capabilities

（无。二期四个 capability 的 requirement 不变；三期只调用 `knowledge_retrieval.search()`。）

## Impact

**后端**
- 新增：`app/services/assistant_*.py`（conversation / graph / llm / guard / handoff）、`app/api/v1/assistant.py`、`app/schemas/assistant.py`、`app/integrations/llm.py`
- 新增依赖：`langgraph`（编排）；LLM 走 **OpenAI 兼容 HTTP**（复用已有 `httpx`，不引入厂商 SDK）
- 配置：`LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`、`LLM_PROVIDER=fake|openai`（测试默认 fake）

**数据**
- 新 schema `assistant` 6 张表；表数 55 → 61；`db/schema.sql` + `db/migrations/0007` 增量 + `gen_models.py` 重跑

**前端**
- 新增客服工作台（会话列表 + 对话窗口 + 引用侧栏）与客户侧对话页
- 新增依赖：无（SSE 用原生 `EventSource`/fetch 流读取）

**契约与测试**
- 新增 OpenAPI 路径与 SSE 事件协议文档；`check_frontend_contract.py` 必须 problems=0
- 测试：图节点单测（fake LLM + fake 检索）、SSE 端到端、身份核验、转人工、契约

**风险**
- LLM 供应商未定 → 用 OpenAI 兼容协议 + `fake` provider，使选择可延后而不改架构
- 流式与幂等中间件冲突 → SSE 路径加入豁免（一期中间件已跳过 `text/event-stream`，需确认前置校验）
