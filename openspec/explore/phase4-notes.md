# 四期探索笔记（本体 + 工具调用 + 评测集合）

> 性质：探索笔记，**不驱动实现**；实现以 OpenSpec change 为准。
> 上游：老板口径（"四期加入本体、工具调用、测评集合"）、`docs/三期/01_三期需求说明书.md` 附录 A、三期实际代码。
> 交付物（本轮之后）：`docs/四期/01_四期需求说明书.md`、`docs/四期/02_验收清单.md`。
> 本文件记录"为什么这么定"，与需求说明书互补。**本轮只做盘点与范围收敛，不写代码、不动一二三期。**
> 状态标记：`[实]` 已实测；`[待决]` 待老板/业务拍板；`[建议]` 主持人推荐但未确认。

---

## 0 事实基线（实测，优先于文档表述）

| # | 事实 | 出处 |
|---|---|---|
| F1 | **四期 change 尚不存在**：`openspec list --json` → `changes: []`，`openspec/changes/` 只有 `archive/`（6 个已归档）；8 个 capability spec 全部是一/二/三期产物 | `openspec list --json`、`openspec/changes/archive/` |
| F2 | 库内 **61 张表**，schema = `shared` / `commerce` / `knowledge` / `assistant`；**无 `ontology` schema**；迁移到 `0008`（8 个文件） | `db/schema.sql`（CREATE TABLE × 61）、`db/migrations/` |
| F3 | `assistant` 6 张表：conversation / message / citation / handoff / identity_verification / retrieval_trace。状态机：`conversation.status`=OPEN/CLOSED + `ai_paused`；`message.status`=STREAMING/DONE/FAILED/REFUSED；`handoff.status`=OPEN/CLAIMED/CLOSED（reason 5 值）；`identity_verification.status`=VERIFIED/FAILED | `db/migrations/0007_assistant_schema.sql` |
| F4 | **"LangGraph 图"实为手写循环**：`assistant_graph.py` 是 `plan/execute/replan/finalize/run` 五个函数 + while 循环，无 StateGraph、无 checkpointer、无 ToolNode；`MAX_STEPS=4 / MAX_PLAN_STEPS=2 / MAX_REPLANS=1 / 30s` | `app/services/assistant_graph.py:29-32,207,226,238,333,367` |
| F5 | `langgraph>=1.0` 在依赖里，但 **`app/` 无任何 langgraph import**（仅 `.venv` 与 requirements 命中） | `requirements.txt:26`；`grep -rn langgraph app/` 为空 |
| F6 | 工具骨架已留位但未接通：`ToolSpec{name,description,input_schema,run,read_only,requires_identity,scope}` + `TOOLS` 注册表**只有 1 个 `search_knowledge`**；`execute()` 是硬编码直调，`input_schema` **从未被消费**，模型看不到工具名 | `app/services/assistant_graph.py:109-117,194-204,226-235` |
| F7 | SSE 事件序列 `meta → ping* → delta* → citations → done \| error`；首 token 只有 `started` 起点（:169），落库只有**整段** `latency_ms`，**TTFT 未单独记录**；断线不补发、重连拉历史；模型异常 → `MODEL_ERROR` 转人工 + 消息置 FAILED | `app/api/v1/assistant.py:169,203-231,240-286` |
| F8 | `citation` 已具备 `chunk_id/document_id/version/title_path/line_start/line_end/snippet/rank/entity_tags`；但 `entity_tags` 由**正则**从 snippet 抽 `product_line`/`rule_id`，是占位不是本体查询结果 | `0007…sql`；`assistant_graph.py:283-304` |
| F9 | 身份核验 = 订单号 + **收货手机后四位**（`order.receiver_phone[-4:]`），TTL 30 分钟，3 次失败锁库并转人工 `IDENTITY_FAILED`，统一失败话术。**`active_verification()` 定义了但全库无调用点** —— 核验结果目前没被任何图节点/工具复用 | `app/services/assistant_handoff.py:16,18,40-49,52-89` |
| F10 | 权限码：`ai:*` 5 个（chat read/write、handoff read/write、trace read）；**`tool:*` 0 个**，唯一记录是二期笔记里"ai:*/tool:* 只写文档" | `db/migrations/0008`；`openspec/explore/phase2-decisions.md:169` |
| F11 | outbox 已有 `ai.handoff.created/claimed/closed`；**无 `ai.tool.*`** | `assistant_handoff.py:154,191,211` |
| F12 | 幂等中间件强制 `Idempotency-Key`（缺则 400）；SSE 路径 `/api/v1/ai/conversations` 已豁免，改由 `client_msg_id` + 唯一索引保证 | `app/core/middleware.py:20-29,66-74`；`0007` |
| F13 | **一期服务自己 commit**（`order.cancel`、`aftersales.create` 末尾都 `db.commit()`）→ 工具执行无法与"待确认动作/消息落库"共事务 | `app/services/order.py:264`、`aftersales.py:115` |
| F14 | 一期权限码 `shop:*` 已覆盖 product/order/aftersales/invoice/refund/fulfillment/customer 读写 → AI 工具要决定"复用 shop:* 还是另立 tool:*" | `scripts/bootstrap.py:20-33` |
| F15 | **工具名真源已在库外**：`intent_taxonomy.yaml` 14 个意图 × `tools`（order_query / payment_query / shipment_query / after_sales_query / installation_query / security_audit / repair_query …）+ `required_entities`；`product_warranty.yaml` 给 product→component→months。二期明确这些 yaml **不入库**，并写明"`intent_taxonomy.tools` 已是四期工具名" | `knowledge_raw/13_结构化规则/intent_taxonomy.yaml`、`product_warranty.yaml`；`phase2-decisions.md:40` |
| F16 | 评测基础设施**为零**：无 `eval/` 目录、无评测表、无录制回放；现有 34 个 pytest 文件 + `FakeProvider`（同输入同输出的确定性替身） | `ls eval` 无；`tests/`；`app/integrations/llm.py:29-54` |
| F17 | 前端契约是**封闭联合类型**：`StreamEvent` 6 种事件；新增任何 SSE 事件都要改类型 + `openapi.yaml` + 过 `check_frontend_contract.py` | `web/src/types/assistant.ts:66-75`；`docs/三期/02_验收清单.md` A2 |

### 0.1 一个必须先解决的硬约束（规划即踩坑）

`assistant.handoff` 的 `reason` 是 **CHECK 枚举 5 值**（USER_REQUEST / HIGH_RISK_RULE / IDENTITY_FAILED / NO_HIT / MODEL_ERROR）。
四期若想新增 `TOOL_FAILED` / `ACTION_REJECTED` 作为转人工原因，**就是 ALTER 已有 CHECK 约束 = 改三期表结构**，与"不改一二三期表"规约冲突。
可选出路（`[待决]`）：① 复用 `MODEL_ERROR`，失败原因写 `summary`；② 新建 `assistant.handoff_reason` 维度表并放宽约束（仍是 ALTER）；③ 四期新增独立表记录工具失败，转人工仍用现有 5 值。

---

## 1 三期可复用 / 缺口清单

| 域 | 三期现状 | 判定 | 四期动作 | 代价 |
|---|---|---|---|---|
| 会话/消息/引用/转人工/核验/留痕 6 表 | 字段完整、状态机明确 | **可复用** | 不改结构 | 0 |
| `message.metadata`(jsonb) | 已存 plan/intent/degraded/feedback | **可复用** | 工具调用记录可先塞这里 | 0（但难 JOIN，见下） |
| `citation.entity_tags` | 正则占位 | **扩展** | 改由本体查询回填；表结构不动 | 小 |
| `retrieval_trace` | query/filters/intent/hits/latency/model/tokens | **扩展** | 工具调用是否入本表 `[待决]`；倾向**新增 `assistant.tool_call`** | 新表 |
| `ToolSpec` + `TOOLS` | 1 个只读工具、字段齐 | **复用骨架** | 加注册表（DB）+ JSON Schema 生成 + 工具节点 | 中 |
| `active_verification()` | 定义无调用点 | **缺口** | 工具门禁必须接它（否则核验白做） | 小 |
| 身份核验 | 订单号+后四位、30min、3 次锁 | **可复用** | 作为 `requires_identity` 工具的统一前置 | 0 |
| `handoff.reason` 5 值 | 见 §0.1 | **缺口（规约冲突）** | 见 §0.1 三条出路 | 需决策 |
| `ai:*` 5 码 / `tool:*` 0 码 | — | **缺口** | 新增 `tool:read`/`tool:write`/`tool:admin`（追加式） | 小 |
| `ai.handoff.*` 事件 | 有 | **复用** | 新增 `ai.tool.invoked/failed`、`ai.action.confirmed` | 小 |
| 一期服务（order/aftersales/invoice/refund/fulfillment/catalog/customer） | 逻辑完整、自带审计+outbox，但**自己 commit** | **复用为工具实现体** | 不直连 DB；接受"两次事务"边界 | 见 F13 |
| SSE 6 事件 | 前端封闭联合类型 | **扩展** | 新增 `tool_call`/`action` 事件；**不改老事件** | 前端改动 |
| 本体相关 | **完全空白**（无 schema、无表、无 chunk 映射、无 entity_ids） | **新建** | ontology schema 4 表 + chunk↔entity 映射 | 大 |
| 评测 | **完全空白** | **新建** | `eval/` 目录 + 用例格式 + runner + 门禁 | 中 |

**一句话结论**：三期把"接工具"的**插槽**留好了（`ToolSpec`、`entity_tags`、核验 TTL、trace 十字段），但**插槽没通电**（`input_schema` 未消费、`active_verification` 无调用点、正则冒充本体）；本体与评测是**从零开始**。

---

## 2 范围三分类（初稿，`[待决]`）

### 2.1 必须做（6 条）

| # | 条目 | 理由 | 若不做的后果 |
|---|---|---|---|
| M1 | `ontology` schema 4 表（entity/relation/alias/entity_tag）+ 审核态 + 追加式迁移 | 老板点名"本体"；关系表 + 递归 CTE 是零新存储的唯一选择 | 四期标题落空 |
| M2 | 本体→检索集成（chunk 挂 entity_ids、一跳扩展） | 否则本体只是"文档里的表"，不改善回答 | 本体成摆设，无法验收 |
| M3 | 工具注册表 + 5–6 个**只读**工具（查询类）+ JSON Schema | 老板点名"查订单、查商品" | 标题落空 |
| M4 | 写操作安全模型：待确认动作表 + 二次确认 + 幂等 + 审计 + 上限 | 无此则写工具一律不敢开 | 工具退化为只读 |
| M5 | 核验↔工具门禁打通（`requires_identity` 前置） | 已有核验 TTL 但无消费者；不接就白做 | 越权查单风险 |
| M6 | 评测集 60–120 条 + 确定性断言 runner + "零退化"告警 | 老板点名"测评集合"；且是四期唯一能证明"没变差"的手段 | 无法证明工具没打坏 RAG |

配套但同批交付：`tool:*` 3 个权限码、`ai.tool.*` outbox 事件、SSE 新增 `tool_call`/`action` 事件与前端确认卡片。

### 2.2 可以延后（4 条）

| # | 条目 | 延后理由 | 影响 |
|---|---|---|---|
| D1 | LLM 从知识库文档自动抽实体（含人工审核队列） | 先用 `intent_taxonomy.yaml`/`product_warranty.yaml`/`product_catalog.yaml` 人工/半自动导入即可覆盖 5 产品线 | 本体覆盖面窄，但可控、可测 |
| D2 | 本体多跳（深度 ≥2）与路径解释 | 一跳已能覆盖"型号→部件→保修" | 复杂故障链路问答效果打折 |
| D3 | 写工具扩到 3 个以上（改地址、开发票、改约安装） | 每个写工具都要单独定确认文案、上限、revert | 四期只落地 1–2 个写工具 |
| D4 | LLM-as-judge 指标 | 确定性断言优先；judge 引入不稳定与成本 | 主观质量维度缺失（用人工抽检补） |
| （备选同步延后）| 本体可视化图谱页面 | 无浏览需求就是纯成本 | 运营只能看列表 |

### 2.3 明确不做（5 条）

| # | 条目 | 理由 | 影响 |
|---|---|---|---|
| X1 | 引入图数据库（Neo4j 等） | 技术栈必须与现有匹配；证据规模（5 产品线、百级实体）用不上图库 | 深度遍历要自己写递归 CTE |
| X2 | 模型**无确认**直接执行写操作 | 误改单不可接受 | 每笔写操作多一轮交互 |
| X3 | 金额类写操作（退款/开票执行） | 一期 `refund.execute` 是资金动作，风控与对账成本远超本期收益 | "帮我退款"只能转人工 |
| X4 | 跨租户/跨渠道共享本体 | 单租户单渠道（`settings.tenant_id`），做多租等于凭空造需求 | 无 |
| X5 | 游客/未登录可调用任何业务工具 | 无可追责主体，与三期 D2 一致 | 游客只能问知识 |

---

## 3 本轮需先定的 3 个模糊点（`[待决]`）

| # | 模糊点 | 为什么必须先定 | 选项 |
|---|---|---|---|
| Q1 | **写工具能不能真实改单** | 决定 M4 的形态（确认单表/权限码/上限）、评测里 `must_call_tool` 是否含写、以及交付排期。选错会让 1/3 工作量返工 | A 只读+转人工 / B 仅"无金额低压"写（取消未发货单、提交售后） / C 全量写 |
| Q2 | **本体首要用途** | 决定 chunk 要不要挂 entity_ids（改二期表？→ 只能新增映射表）、工具 schema 里实体字段怎么来、以及 M2 的验收口径 | A 只给检索（实体过滤+一跳扩展）/ B 只给工具（实体消歧、参数解析）/ C 两者都要 |
| Q3 | **评测是门禁还是报表** | 决定要不要录制回放、CI 是否跑真模型、门禁阈值怎么定、目录与 runner 形态 | A CI 确定性门禁（fake/回放，零退化阻断）/ B 夜间报表（人不看阻塞）/ C 两者（CI 门禁 + 夜间真模型） |

---

## 4 下一轮议程（待 Q1 拍板后推进）

1. (a) 本体表示定稿 + 域与实体/关系清单（目标条数）
2. (b)(c) 本体域范围、抽取方式、chunk 映射与维护责任人
3. (d) 工具清单定稿（名称/入参/权限码/幂等/确认/对应一期函数）
4. (e)(f)(g) 写操作安全模型、核验门禁、失败与降级话术矩阵
5. (h)(i) 评测格式、来源、规模、目录、指标与门禁
6. (j) 与三期图的集成点、`retrieval_trace` 扩字段方式、`handoff.reason` 出路
7. 收口 → 建议拆 3 个 change（本体映射 / 工具与工作流 / 评测闭环），转 `/openspec-propose`

---

## 5 变更记录

| 日期 | 内容 |
|---|---|
| 本轮 | 建立事实基线 F1–F17、可复用/缺口清单、范围三分类初稿、3 个待决模糊点。未写任何代码、未动任何已有 change。 |
