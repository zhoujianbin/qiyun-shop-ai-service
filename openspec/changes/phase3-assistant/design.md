# Design — 三期智能客服

## Context

- 二期已交付：`knowledge_retrieval.search(db, query, *, filters, top_k, actor, identity_level)` 返回 `{hits, debug}`；`hits` 是稳定引用契约；阈值（向量 0.35 / 全文 0.15 / RRF k=60）**已在二期内部生效**。
- 一期已交付：客户/员工/游客三套登录（`shared.app_user.party`）、订单与售后、审计、outbox、幂等中间件。
- 探索结论见 `docs/三期/01_三期需求说明书.md` 与 `openspec/explore/phase3-notes.md`（D1–D26）。

## Goals / Non-Goals

**Goals**

- 答案**永远可追**：每条回答至少一条引用，或明确拒答/转人工。
- 供应商**可替换**、失败**可降级**、三期**不碰一期/二期的表与接口语义**。
- 首 token 可控：常见问题不付"额外一次 LLM 规划"的时延。

**Non-Goals**

- 不做通用工具注册表与写操作工具（四期）；订单类问题只答口径 + 固定事实快照。
- 不做本体、评测集、A/B、语音/图片消息。

## Decisions

### 决策 1：新建 `assistant` schema，6 张表（库内 55 → 61）

| 表 | 关键列 |
|---|---|
| `conversation` | `conversation_no`(seq("CV"))、`user_id`(NOT NULL)、`party`(CUSTOMER/GUEST)、`channel_account_id`、`title`、`status`(OPEN/CLOSED)、**`ai_paused`**、`message_count`、`last_message_at` |
| `message` | `conversation_id`、`seq`、`role`(USER/ASSISTANT/**AGENT**/SYSTEM)、`content`、`status`(STREAMING/DONE/FAILED/REFUSED)、**`client_msg_id`**、`model`、`prompt_tokens`、`completion_tokens`、`latency_ms`、`metadata jsonb`(`plan`/`feedback`) |
| `citation` | `message_id`、`chunk_id`、`document_id`、`version`、`title_path`、`line_start`、`line_end`、`snippet`、`rank`、**`entity_tags jsonb`** |
| `handoff` | `conversation_id`、`reason`(5 枚举)、`status`(OPEN/CLAIMED/CLOSED)、`assignee_id`、`claimed_at`、`closed_at`、`summary` |
| `identity_verification` | `conversation_id`、`order_no`、`phone_tail char(4)`、`order_id`、`customer_id`、`status`(VERIFIED/FAILED)、`attempts`、`expires_at` |
| `retrieval_trace` | `message_id`、`query`、`filters`、`intent`、`hit_count`、`hits`、`latency_ms`、`model`、`tokens` |

**约束**：`UNIQUE(conversation_id, seq)`；`UNIQUE(conversation_id, client_msg_id) WHERE NOT NULL`；`UNIQUE(message_id, rank)`；`UNIQUE(conversation_id) WHERE handoff.status IN ('OPEN','CLAIMED')`。

**为什么独立 citation 表**：四期评测要按引用逐条标注与聚合（"哪篇被引用最多/引用准确率"），jsonb 数组难 JOIN。

**为什么单独 schema**：会话高频写、可清理；与知识资产的备份/治理范围隔离。

### 决策 2：LLM 走 OpenAI 兼容 HTTP，供应商可替换

`app/integrations/llm.py` 暴露 `stream_chat(messages, **opts) -> Iterator[str]`：

- `LLM_PROVIDER=openai`：POST `{LLM_BASE_URL}/chat/completions`，`stream=true`，`httpx` 逐行解析 `data:`。
- `LLM_PROVIDER=fake`：确定性文本（测试与离线）。
- `APP_ENV=test` 自动 fake（与二期 embedding 一致）。

**已定**：DeepSeek（`https://api.deepseek.com`），模型 **`deepseek-flash`**。实测：首 token **255ms**，81 chunk / 1.3s；账号下另有 `deepseek-v4-pro`。

**关键细节**：`deepseek-flash` 是推理型模型，`delta` 同时含 `content` 与 `reasoning_content`。集成层 MUST 只转发 `content`；推理内容**不落库、不下发、不进 SSE**；`completion_tokens` 含推理 token，计费按总量。

### 决策 3：plan-and-execute（3 节点 + 1 回路）

```
plan ──► execute ──► finalize
            │  ▲
            └──┘ replan（仅"零命中→改写重试"，最多 1 次）
```

| 项 | 定值 |
|---|---|
| 计划长度 | **≤ 2 步**（search → answer 或 verify → answer） |
| 计划表示 | 严格 JSON + Pydantic 校验；非法即弃用并退化为固定两步 |
| 闸门 | 最大 **4 步**、最多 **1 次 replan**、单次问答总超时 **30s** |
| 意图 | 4 类；**规则词表优先，未命中才调 LLM planner**（保护首 token） |
| LangGraph 用法 | 只用 StateGraph + 条件边；**不用 checkpointer / 不用人工中断 / 不持久化图状态** |
| 工具接口 | `ToolSpec{name, description, input_schema, run, read_only, requires_identity, scope}`；三期只注册 `search_knowledge`(read_only=true) |

**四期接口**：加工具 = 新增 ToolSpec + planner prompt 多一行描述；图与 state 不变。

**备选**：手写 while 循环（少一依赖，四期分支会失控）；全套 LangGraph（checkpointer/interrupt，本期无需求）。

**风险**：`langgraph` 在 **Python 3.13** 的可用性未验证——实施第一步先装并跑最小图；装不上退回手写循环，specs 与任务不变。

### 决策 4：SSE over POST + fetch

`POST /api/v1/ai/conversations/{id}/messages:stream`，事件序列固定：

```
event: meta      data: {"conversation_id":3,"message_id":12,"seq":5}
event: ping      data: {}                       # 每 15s
event: delta     data: {"text":"根据"}           # 只含 content
event: citations data: {"hits":[...]}
event: done      data: {"status":"DONE","tokens":{"prompt":420,"completion":180},"latency_ms":1800}
event: error     data: {"code":"...","message":"...","details":null,"request_id":"..."}
```

| 约束 | 说明 |
|---|---|
| 传输 | POST + `fetch` 读 `ReadableStream`（`EventSource` 不能带 header，token 不进 query） |
| 鉴权 | `Authorization: Bearer`（沿用 `get_current_user`） |
| 中间件 | **SSE 路径必须加入 `EXEMPT_PREFIXES`**：中间件在 event-stream 上提前 return，不会写 `COMPLETED`，会给每个流留一条永久 `IN_PROGRESS` 幂等记录 |
| 幂等 | 由 `client_msg_id` 在业务层保证 |
| 落库 | 先落 USER + **占位 ASSISTANT(STREAMING)**，流结束更新 DONE/FAILED/REFUSED；超 2 分钟仍 STREAMING 由清理任务置 FAILED |
| 头 | `Cache-Control: no-cache`、`X-Accel-Buffering: no` |
| 断线 | 不补发（不用 `Last-Event-ID`）；重连拉历史 |

**备选**：GET + EventSource（token 泄露到日志）；WebSocket（本期无双向需求）。

### 决策 5：引用只来自 `hits`，并带确定性实体标签

- 服务端把 `hits` 映射成 `citation` 行，**不解析模型输出**。
- `entity_tags` 只抽两类确定性实体：`product_line`（型号码正则）、`rule_id`（`KB-RULE-*` 正则）；无则空数组。**不回填二期 `chunk.metadata`**。
- 引用结构：`{document_id, version, title_path, line_start, line_end, snippet}`。

### 决策 6：拒答与护栏

| 情形 | 行为 |
|---|---|
| 检索为空 | **不调模型**；先**反问澄清一次**；仍空 → 固定拒答 + 建议转人工 |
| 有命中但相关度一般 | 正常回答，前缀「以下为一般口径，具体以你的订单为准」 |
| 属实时事实类且未核验 | 只答口径，**不给数值** |
| 命中 escalation 规则 | 规则来源：读 `knowledge.rule` 中 `source_kind='escalation'` 的 `triggers` 词表，**并配一张中文别名表**（triggers 是英文标识符，用户提问是中文，不配别名永远命中不了）做关键词匹配；命中即取该规则 `forbid` 作为安全提示，**禁止给操作指令** |
| 模型超时/失败 | 返回错误事件 + `request_id`，消息状态 FAILED |

### 决策 7：身份核验与固定事实快照

- 凭据：订单号 + 收货手机后四位，比对 `commerce.orders.receiver_phone`。
- 通过后 30 分钟有效，`identity_verification` 记录；会话级**只读**放宽。
- **核验后可给固定事实快照**（`order_fact_snapshot(db, order_id)`，写死的只读函数，**不是工具框架**）：订单号、订单状态、实付金额、下单时间、物流状态+运单号、售后进度。
- **红线**：永不展示完整手机号、完整地址、支付卡号、身份证、其他订单、设备密码/开锁凭证。
- 失败话术统一（不区分"订单不存在"与"手机不符"）；连续 3 次失败强制转人工。

### 决策 8：转人工（认领制）

`reason`：`USER_REQUEST`、`HIGH_RISK_RULE`、`IDENTITY_FAILED`、`NO_HIT`、`MODEL_ERROR`。

- 进 `OPEN` 队列 → 客服认领 `CLAIMED`（**同时置 `conversation.ai_paused=true`，AI 停止自动回答**）→ 客服回话写 `message(role=AGENT)` → 关单必填 `summary` → `CLOSED`。
- 「退回给 AI」：handoff 关闭 + `ai_paused=false`。
- **不自动建售后工单**（会话与工单解耦；多数会话无订单）。
- 事件：`ai.handoff.created` / `ai.handoff.claimed` / `ai.handoff.closed`；审计同步写。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 模型编造引用 | 引用由服务端从 `hits` 生成；无命中不调模型 |
| SSE 泄漏幂等记录 | SSE 路径加入 `EXEMPT_PREFIXES`（这是硬要求，不是优化） |
| 推理内容外泄 | 集成层只转发 `content`，单测断言流里无 reasoning |
| 会话数据增长快 | `retrieval_trace`/`citation` 按 message 级联删除；保留期由 `assistant_cleanup.py` 控制 |
| `updated_at` 被触发器维护，不能当"最后活动时间" | 清理判据改用 `coalesce(last_message_at, created_at)`；僵尸消息判据仍用 `message.updated_at`（停滞即不再更新） |
| 核验被暴力尝试 | 连续 3 次失败转人工 + `attempts` 记录；失败话术不可枚举 |
| `langgraph` 在 Py3.13 装不上 | 第一步验证；失败退回手写循环（specs/任务不变） |
| 首 token 因 planner 变慢 | 意图规则优先，只有未命中才调 LLM planner |

## Migration Plan

1. `db/schema.sql` 增 `CREATE SCHEMA assistant` + **6 张表**；`db/migrations/0007_assistant_schema.sql` 增量（幂等）。
2. 重跑 `gen_models.py`；表数 **55 → 61**。
3. 追加 5 个 `ai:*` 权限码 + 2 个新角色（`AI_AGENT`/`AI_SUPERVISOR`）+ `CS_SUPERVISOR` 加 `ai:handoff:read`。
4. 配置 `LLM_*`；无配置时 provider=fake。
5. 回滚：删 `assistant` schema + 收回 `ai:*` 授权。

## Open Questions

1. ~~LLM 供应商~~ **已定** DeepSeek `deepseek-flash`。
2. ~~客户入口形态~~ **已定**：独立页 `/assistant` + `CustomerShell` 入口按钮（浮窗只做入口，不复制对话逻辑）。
3. ~~客服工作台归属~~ **已定**：现有 `/admin` 下新增 `/admin/assistant`。
4. **会话保留期**：当前取 90 天（清理任务可调），待运维确认。
5. **成本监控口径**：按 `message.prompt_tokens/completion_tokens` 汇总；单价以供应商账单为准，不在代码里写死。
