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
---

## 6 决策台账（第 2 轮起）

| ID | 决策 | 理由 |
|---|---|---|
| D1 | **[已定]** 写工具边界 = **Q1-B**：只做 2 个"无金额低压"写工具（取消未发货订单、提交售后申请）；资金类（退款/开票执行）一律不做 | 有可演示闭环（读→确认→写→审计→可撤销），同时把资金风险挡在门外 |
| D2 | **[暂定]** 本体两用（Q2-C），但分两档：检索侧只做"实体归一 → 复用二期已有 filter"；工具侧做型号/订单参数归一。共用 entity/alias 表 | 两档共用同一张实体表，边际成本低；真正翻倍的是 chunk 映射，故给映射表单独立项 |
| D3 | **[暂定，含事实修正]** 评测门禁 = **`make test` 内的 pytest 用例 + `make eval`**，不做 GitHub Actions（**仓库无 `.github/`**，无 CI 基础设施）；夜间真模型改为"手工可选任务" | 不凭空造 CI；pytest 已是项目唯一门禁（`docs/三期/02_验收清单.md` A1） |
| D4 | **[建议]** 本体表示 = **关系表 + 递归 CTE，深度上限 2**；新建 `ontology` schema 5 表 | 见 §6.2 遍历深度实测 |
| D5 | **[建议]** `handoff.reason` 冲突出路 = **①**：沿用 `MODEL_ERROR`，四期新表 `assistant.tool_call` 记失败明细，`summary` 写 `TOOL_FAILED:<tool>:<code>`。**不 ALTER 三期 CHECK** | 规约优先；明细进新表，审计可反查，理由可读 |

### 6.1 第 2 轮新增事实（实测）

| # | 事实 | 出处 | 影响 |
|---|---|---|---|
| F18 | 二期检索 `filters` **只认两个键**：`category`、`product_scope`（都打在 `knowledge.document` 上） | `app/services/knowledge_retrieval.py:61-66` | **好消息**：实体若归一成"产品型号"，直接映射到 `product_scope` 就能用现有检索，**四期零改二期代码** |
| F19 | 仓库**无 `.github/`**，唯一门禁是 `make test` / `make contract` | `Makefile` | "CI 门禁"必须落到 pytest，不是 Actions |
| F20 | 本体素材条数（实测）：产品 5 + 配件 4、部件 6、故障现象 22、政策/保修/升级规则 24、意图 14、意图自带工具名 12 个、`required_entities` 7 个 | `product_catalog.yaml`、`product_warranty.yaml`、`escalation_matrix.yaml`、`intent_taxonomy.yaml` | "够用"的目标规模可以量化，不用拍脑袋 |

### 6.2 本体范围（建议值，实测推导）

**实体 67 条**

| 实体类型 | 条数 | 来源 |
|---|---|---|
| 产品 | 5 | `product_catalog.yaml:products` |
| 配件 | 4 | `product_catalog.yaml:accessories` |
| 部件 | 6 | `product_warranty.yaml` 的 distinct `component` |
| 故障/现象 | 22 | `escalation_matrix.yaml` distinct `triggers`（+ `escalation_aliases.yaml` 中文别名） |
| 动作 | 6 | 工具清单的写/查动作（取消订单、提交售后、申请发票、查订单、查物流、查商品） |
| 政策/规则 | 24 | policy 9 + warranty 7 + escalation 8（**已在 `knowledge.rule`，本体只存引用，不复制正文**） |

**关系 ~105–125 条、7 类**

| 关系 | 方向 | 条数 | 来源 | 维护方式 |
|---|---|---|---|---|
| `PART_OF` | 配件/部件 → 产品 | ~11 | catalog + warranty | 脚本导入 |
| `SYMPTOM_OF` | 故障 → 部件 | 22 | **无数据源** | **纯人工**（唯一新增成本） |
| `REMEDY` | 故障 → 动作 | ~15 | `06_保修维修与备件/` 6 篇 | 人工+审核 |
| `COVERED_BY` | 部件 → 保修规则 | 7 | warranty | 脚本导入 |
| `GOVERNED_BY` | 动作 → 政策 | ~10 | policy_rules | 脚本导入 |
| `ALIAS_OF` | 别名 → 实体 | 40–60 | `escalation_aliases.yaml` 20 组 + 型号口语 | 人工+审核 |
| `ESCALATES_TO` | 故障 → 升级矩阵 | ~10 | escalation_matrix | 脚本导入 |

**明确不入本体**：订单/支付/履约/退款状态机（7+6+5+9 状态、36 条迁移，真源 `order_workflow.yaml`）。它是流程不是知识，入本体等于重造状态机 —— 这是"本体范围失控"的头号入口。

**遍历深度（关键结论）**：一跳不够。"指纹失灵 →(SYMPTOM_OF) 锁体电子部分 →(COVERED_BY) 保修 24 个月" 是**两跳**才拿到答案。故：检索扩展用**深度 1**（省 token、防跑题），回答取证用**深度 2**（递归 CTE + `depth` 列 + 路径数组防环）。

### 6.3 chunk ↔ 实体映射（待定，见 §7 Q4）

核心坑：**chunk_id 会失效**。文档发新版本 → 新 `document_version_id` → 新 chunk 行（`UNIQUE(document_version_id, ord)`），旧映射指向死 chunk。
故映射表的逻辑键应为 `(document_id, version, chunk_ord)`，`chunk_id` 只作冗余加速列；版本切换时按逻辑键重挂，不重跑实体抽取。

---

## 7 下一轮待决

| # | 问题 | 选项 |
|---|---|---|
| Q4 | chunk↔entity 映射怎么落 | A 新表 `ontology.chunk_entity`（逻辑键 = document_id+version+chunk_ord）/ B 零表，检索前现算实体匹配 / C 写进 `chunk.metadata`（需改二期导入代码并全量重导） |
| Q5 | 67 实体 / 105 关系是否算"够用" | 是 / 缩到 3 产品线 / 扩到含状态机与角色 |
---

## 8 工具清单初稿（第 3 轮）

### 8.1 从 12 个"意图自带工具名"收敛到 9 个可落地工具

`intent_taxonomy.yaml` 已声明 12 个工具名（二期刻意不入库、留给四期）。实测**只有 6 个有一期服务或表支撑**：

| 意图 yaml 里的工具名 | 有一期服务/表？ | 四期处置 |
|---|---|---|
| `order_query` | 是（`order.get_order/list_orders`） | 落地 `query_order` |
| `payment_query` | 是（`payment.list_payments/get_payment`） | 落地 `query_payment` |
| `shipment_query` | 是（`fulfillment.list_shipments/get_shipment`） | 落地 `query_shipment` |
| `after_sales_query` | 是（`aftersales.list_applications`） | 落地 `query_after_sales` |
| `installation_query` | **否**（无表；只有 `orders.install_required/install_notes` 两列） | 降级为知识检索 + 转人工 |
| `repair_query` | **否**（`06_保修维修` 全是文档） | 降级为知识检索 |
| `subscription_query` | **否**（`08_云服务` 全是文档） | 降级为知识检索 |
| `device_binding_query` | **否**（07 全是文档） | 降级为知识检索 |
| `device_status_optional` | **否** | 不做 |
| `security_audit` / `security_audit_optional` | **否** | 直接转人工（本就该 escalate） |
| `ticket_query_optional` | **否** | 不做（三期 handoff 已覆盖） |

再加两个 yaml 里没列、但一期有服务的：`query_product`（`catalog.search_products/get_public_product`）、`query_invoice`（`invoice.list_invoices`）。
**结论：7 只读（含 1 个知识检索）+ 2 写 = 9 个。**

### 8.2 工具清单

| # | 工具名 | 类型 | 入参 | 权限门 | 核验 | 幂等 | 需确认 | 对应一期函数 |
|---|---|---|---|---|---|---|---|---|
| 1 | `query_product` | 只读 | `{keyword?, model_code?}` | 无（C 端在售） | 否 | 天然 | 否 | `catalog.search_products`、`catalog.get_public_product` |
| 2 | `query_order` | 只读 | `{order_no}` | `tool:read` | **是** | 天然 | 否 | `order.get_order`（需 order_no→id 解析，见 §8.3） |
| 3 | `query_shipment` | 只读 | `{order_no}` | `tool:read` | **是** | 天然 | 否 | `fulfillment.list_shipments` |
| 4 | `query_payment` | 只读 | `{order_no}` | `tool:read` | **是** | 天然 | 否 | `payment.list_payments` |
| 5 | `query_after_sales` | 只读 | `{order_no}` | `tool:read` | **是** | 天然 | 否 | `aftersales.list_applications` |
| 6 | `query_invoice` | 只读 | `{order_no}` | `tool:read` | **是** | 天然 | 否 | `invoice.list_invoices` |
| 7 | `search_knowledge` | 只读 | `{query, top_k?}` | 无 | 否 | 天然 | 否 | `knowledge_retrieval.search`（三期已有） |
| 8 | `cancel_order` | **写** | `{order_no, reason}` | `tool:write:order` | **是** | `pending_action` 唯一键 | **是** | `order.cancel` |
| 9 | `create_after_sales` | **写** | `{order_no, type, reason_code, order_item_id?, quantity?, description?}` | `tool:write:aftersales` | **是** | `pending_action` 唯一键 | **是（且标注不可撤销）** | `aftersales.create` |

### 8.3 三个必须交代的缺口

| # | 缺口 | 事实 | 处置 |
|---|---|---|---|
| G1 | **没有"按 order_no + actor 查订单"的函数** | 全库唯一按 `order_no` 查单的地方是 `assistant_handoff._order()`（无 customer 过滤，staff 视角） | 四期在服务层加薄封装 `resolve_order(db, actor, order_no)`，内部走 `select(Order).where(customer_id==actor.customer_id)`；**不改一期函数** |
| G2 | **幂等只在`pending_action`层** | `order.cancel` 自带"已取消直接返回"的弱幂等；`aftersales.create` 无幂等键 | 写工具一律先落 `pending_action`（UNIQUE(conversation_id, action_key)），执行成功后记账；重放走回放 |
| G3 | **工具执行必然二次事务** | `order.cancel` / `aftersales.create` 末尾都 `db.commit()` | 确认单先 commit（PROPOSED），执行时再 commit（EXECUTED）；**中间态可见**，失败可重试而不是"半截" |

### 8.4 权限门设计（关键取舍）

**客户侧不用权限码**：一期所有服务函数已按 `actor.party == CUSTOMER` → `customer_id` 过滤（`order.py:71-78`、`payment.py:23-31`、`aftersales.py:56-64`、`invoice.py:23-26`），"客户只能操作自己的单据"**由服务层天然保证**。四期只需保证一件事：**actor 必须来自 `conversation.user_id`，永不来自工具参数**。

`tool:*` 权限码管的是**能力开关**（谁能开写工具、灰度放给哪些坐席/渠道），不是单据权限：

| 权限码 | 语义 | 授予 |
|---|---|---|
| `tool:read` | 允许触发只读工具 | `AI_AGENT`（新增绑定） |
| `tool:write:order` | 允许触发`cancel_order` | `AI_SUPERVISOR` |
| `tool:write:aftersales` | 允许触发`create_after_sales` | `AI_SUPERVISOR` |
| `tool:admin` | 维护工具注册表与开关 | `SYSTEM_ADMIN` |

### 8.5 工具描述规范（让模型选对）

| 规则 | 写法 |
|---|---|
| R1 | description 必须写**触发条件**而非功能：`"当用户给出订单号并询问订单状态/金额/进度时使用"`，不写 `"查询订单"` |
| R2 | 必须写**何时不要用**：`"用户只问'怎么取消'且未给订单号时不要调用，先反问"` |
| R3 | 参数 description 写**格式与来源**：`order_no: "形如 SO2026…；只在用户明确给出时填，禁止编造"` |
| R4 | 只读工具一律 `strict: true` + `additionalProperties: false`，避免模型自由加字段 |
| R5 | 写工具 description 末尾固定写 **"调用本工具只生成待确认动作，不直接改单"**（模型与审核双重保险） |

反例（禁止）：`{"name":"query_order","description":"查询订单信息"}` —— 模型会拿它去答"怎么退款"。

---

## 9 累计待决

| # | 问题 | 状态 |
|---|---|---|
| Q4 | chunk↔entity 映射方案（A 新表 / B 现算 / C metadata） | **未答** |
| Q5 | 67 实体 / 105 关系是否"够用" | **未答** |
| Q6 | 工具清单边界（9 个 / 7 个 / 11 个） | 本轮新提 |
---

## 10 写路径与失败路径（第 4 轮）

### 10.1 F21 **[必须是安全缺陷]**：`identity_level` 由客户端决定

| 项 | 实测 |
|---|---|
| 事实 | `StreamRequest.identity_level: str = "public"`（`app/schemas/assistant.py:79`）由**客户端上传**，`assistant.py:171` 原样透传给 `assistant_graph.run()` → `search(identity_level=...)` |
| 后果 | 任意登录用户（含游客）传 `identity_level="agent"` 即可解锁 `IDENTITY_LEVELS["agent"] = ["public","customer","agent"]` 的切片，**读到内部客服文档** |
| 定性 | 三期既存信息泄露；四期要给工具做核验门禁，此洞不堵则门禁无意义（工具参数可比切片更敏感） |
| 修法 | 保留字段（不动前端/契约），**服务端忽略入参**，改由 `active_verification(conversation_id)` 推导：VERIFIED → `"customer"`，否则 `"public"`；员工走 `ai:chat:read` 才给 `"agent"` |

### 10.2 待确认动作状态机

```
             propose(写工具被模型选中)
                    |
                    v
   +----------> PROPOSED ----cancel----> CANCELLED
   |             |    \                     ^
   |             |     \__expire 10min__    |
   |         confirm    \                |
   |             v       v               |
   |          CONFIRMED  EXPIRED         |
   |             |                       |
   |         execute                     |
   |        /        \                   |
   |   ok  /          \  fail            |
   |      v            v                 |
   |  EXECUTED      FAILED ----retry---->|
   |      |                              |
   |      +--- 售后：可撤销(aftersales.cancel，用户自行操作)
   |      +--- 取消订单：不可撤销，只能转人工
```

### 10.3 安全模型七件套（对齐 (e)）

| # | 机制 | 本期做法 | 依据 |
|---|---|---|---|
| S1 | 二次确认 | 确认卡片只展示**对象+影响+不可撤销标记+过期时间**；对象字段复用 `order_fact_snapshot` 6 字段白名单，不展示手机/地址/卡号 | 三期 D20 |
| S2 | 幂等 | `UNIQUE(conversation_id, action_key)`，`action_key=sha256(tool + 归一化参数)`；状态迁移用 CAS `UPDATE … WHERE status='PROPOSED'` | 一期幂等先例 |
| S3 | 审计 | 3 时点 `audit.record`：propose / confirm / execute(ok\|fail)；outbox `ai.action.proposed / confirmed / executed / failed` | `audit.py` |
| S4 | 可撤销性 | `cancel_order`：执行后**不可撤销**（订单已取消，无反向操作）；`create_after_sales`：`COMPLETED` 前客户可自行 `aftersales.cancel` 撤销，AI 只给入口不代操作 | `aftersales.py:271` 有 cancel |
| S5 | 金额上限 | 本期 2 个写工具均**零金额变动**，不设阈值；改设频次闸：单会话 ≤3 次写、同一 order 24h 内 ≤1 次取消 | 范围 X3 |
| S6 | 权限与渠道隔离 | `tool:write:*` 能力门 + actor 继承会话渠道（`actor.channel_ids` 由服务层生效） | `order.py:71` |
| S7 | 只动自己的单 | **actor 只来自 `conversation.user_id`**；`resolve_order` 带 `customer_id` 过滤；execute 前二次校验 `order.customer_id` | 双保险 |

**新增硬约束（来自 G3）**：**单轮最多 1 个写工具调用**。因为一期服务各自 `db.commit()`，多写无法回滚；复合写（取消+提交售后）必须拆成两轮确认。

### 10.4 核验与工具门禁（对齐 (f)）

| # | 规则 |
|---|---|
| V1 | `requires_identity=True` 的工具在**进入工具节点前**检查 `active_verification(conversation_id)`；无则直接返回 `IDENTITY_REQUEST`，工具不执行 |
| V2 | 核验单里已存 `order_no` → 必须**精确匹配**工具入参 `order_no`；核验 A 单后查 B 单视为未核验（不是"已核验但无权限"，避免信息泄漏） |
| V3 | 有效期：读工具沿用 30 分钟；**写工具在 confirm 时再校验一次 `expires_at`**（防止挂起后写） |
| V4 | `active_verification()` 现在**全库无调用点**，四期必须接上；它同时是 F21 的唯一正确取值来源 |
| V5 | 失败 3 次锁 + 转人工 `IDENTITY_FAILED` 沿用，不改 |

### 10.5 失败与降级矩阵（对齐 (g)）

| 情形 | 回话 | 自动重试 | 转人工 |
|---|---|---|---|
| 超时（只读 3s / 写 8s） | "查询超时，请稍后再试或转人工" | 否 | 可选 |
| 5xx | "系统繁忙，已记录" + `request_id` | 只读重试 1 次 | 是 |
| 业务拒绝（如 `ORDER_STATE_INVALID` 已发货） | **原样透传 code + 人话解释 + 出路**（"已发货，请走退货退款流程"） | 否 | 否 |
| 404 / 越权 | 统一"没有找到该订单" | 否 | 否（防探测） |
| 参数不合法 | 反问补全，不重试 | 否 | 否 |
| 写操作执行失败 | "未能完成，未做任何改动" + `request_id` | **否**（绝不自动重试写） | 可选 |

**铁律（防编造）**：工具结果为**服务端事实块**，前端直接渲染成卡片；模型只写叙述句，**不得复述金额/单号/时间等具体值**。沿用三期"引用只由服务端生成"的同一条思路。

---

## 11 累计待决

| # | 问题 | 状态 |
|---|---|---|
| Q4 | chunk↔entity 映射方案 | **暂定 A**（新表 + 逻辑键），未明确反对 |
| Q5 | 67 实体 / 105 关系够不够 | **暂定够用** |
| Q6 | 工具清单 9 个 | **已定 A** |
| Q7 | F21 `identity_level` 处置 | 本轮新提，需拍 |
---

## 12 图集成与工具协议（第 5 轮）

### 12.1 模型能力实测：`llm.py` 没有 tools 通道

| # | 事实 | 出处 |
|---|---|---|
| F22 | `OpenAIProvider._payload()` 只组装 `model/messages/stream/temperature/max_tokens`，**没有 `tools`/`tool_choice`** | `app/integrations/llm.py:70-80` |
| F23 | `complete()` 的返回只取 `choices[0].message.content`，**丢弃 `tool_calls`** | `app/integrations/llm.py:110-137` |
| F24 | `FakeProvider` 只会按最后一条 user 文本回固定串，**不会返回 tool_call** | `app/integrations/llm.py:29-54` |

结论：四期必须扩 `llm.py`（加 `tools` 透传 + `tool_calls` 解析 + fake 支持），这是**改三期集成层**，但属"加参数不改语义"，不碰接口/表/前端类型。

### 12.2 一个必须承认的未知

**DeepSeek 是否支持"流式 tool_calls 增量"未实测。** 依赖它会把首字节卡在第一个 tool_call 上。
规避方案（`[建议]` D9）：**两段式调用**

| 阶段 | 调用方式 | 产出 |
|---|---|---|
| 决策 | `complete()` **非流式**，带 `tools` | 要么 `tool_calls`，要么纯文本答案 |
| 回答 | `stream()` **流式**，不带 tools | 叙述句（事实块由服务端注入） |

代价：事实类问题多一次模型往返；收益：不赌未验证的流式能力。知识类（规则 fast-path 命中）**不进决策阶段**，TTFT 不变。

### 12.3 图结构（不换骨架，只插两个节点）

```
question
   |
   v
[normalize]  实体识别(alias 最长匹配) → {product_scope, entity_ids}   <-- 新节点
   |
   v
 [plan]      规则词表 fast-path：KNOWLEDGE / FACT / IDENTITY / HUMAN
   |
   +-- KNOWLEDGE --> [retrieve] search(filters={product_scope})
   |                    --> [expand] 深度1 邻接实体，最多再检索 1 次，hits 合并去重
   |                    --> [finalize]
   |
   +-- FACT ------> [tool_loop] 最多 3 次工具调用（总步数仍受 MAX_STEPS=4 约束）
   |                   +-- 只读 → 执行 → 结果回填模型
   |                   +-- 写   → propose 落 pending_action → **本轮结束**
   |
   +-- IDENTITY --> 回 IDENTITY_REQUEST（不调模型、不调工具）
   +-- HUMAN -----> HANDOFF
```

**为什么本体查询必须在检索前**：`search()` 的 `filters` 只能过滤 `knowledge.document`（`category`/`product_scope`），**召回后无法再过滤**（F18）。所以实体归一只能是检索前的节点；一跳扩展是检索后的第二次检索。

**为什么写确认不用 checkpointer**：三期图无持久化状态（D13）。确认是**新请求** `POST /ai/actions/{id}/confirm`，服务端从 `pending_action` 表恢复参数、独立执行、写一条 ASSISTANT 消息 + 审计。**不恢复图**，也就不需要 LangGraph checkpointer。

### 12.4 注册表放哪：**代码，不建表**（对齐二期教训）

9 个工具、变更随发版走。若建 `assistant.tool_registry` 表，就重演二期 `product_catalog.yaml` vs `commerce.product.model_code` 的**双真源**问题（`phase2-decisions.md:44` D5 明确判定为要消除的）。
故：**工具定义 = 代码单一真源**（`app/services/tool_registry.py` 的 `TOOLS` 字典，沿用三期 `ToolSpec`）；开关与灰度用 `tool:*` 权限码 + `settings` 控制，**零新表**。

### 12.5 表数账（当前 61）

| 动作 | 表 | 累计 |
|---|---|---|
| 新建 `ontology` schema | entity / relation / alias / entity_tag / chunk_entity | 66 |
| 新建 `assistant` 扩展 | pending_action / tool_call | **68** |
| 不建 | tool_registry（代码真源）、评测用例表（文件为真源）、eval_run（报告文件） | 68 |

### 12.6 `retrieval_trace` 不扩字段

工具调用进新表 `assistant.tool_call`（`message_id, tool_name, args jsonb, status, latency_ms, error_code, proposal_id?`），理由：评测要按工具统计成功率/时延，jsonb 塞进 `retrieval_trace.hits` 无法 JOIN，且会污染"检索留痕"的语义。

### 12.7 SSE 新增 2 个事件（不改老 6 个）

| 事件 | 载荷 | 前端用途 |
|---|---|---|
| `tool` | `{name, status: running\|ok\|failed, latency_ms}` | 显示"正在查询订单…"骨架，掩盖决策阶段的等待 |
| `action` | `{id, tool, summary, impact, irreversible, expires_at}` | 渲染确认卡片（确认/取消按钮） |

前端影响：`web/src/types/assistant.ts` 的 `StreamEvent` 从 6 增到 8；`openapi.yaml` + `check_frontend_contract.py` 需同步。**老事件载荷一字不改。**

---

## 13 累计待决

| # | 问题 | 状态 |
|---|---|---|
| Q4 | chunk↔entity 映射 | 暂定 A（新表 + 逻辑键） |
| Q5 | 67 实体 / 105 关系 | 暂定够用 |
| Q6 | 工具清单 9 个 | **已定 A** |
| Q7 | F21 处置 | **已定 A**（服务端推导，字段不动） |
| Q8 | 两段式模型调用（非流式决策 + 流式回答） | 本轮新提 |
---

## 14 工具调用协议澄清（第 6 轮，回答提问）

### 14.1 提问原文

> "我想的是按照一个约定返回 json 结构的工具调用参数和工具名，然后直接就能调用工具了 —— 对不对？"
> "工具调用返回 json 的过程要识别出来，不能对外展示，是这样吗？"

### 14.2 判定：**第一句对，第二句完全对**

| 说法 | 判定 | 补正 |
|---|---|---|
| 工具调用是"约定好的 JSON 结构"（工具名 + 参数） | **对** | 但它**不是** `content` 里的自由文本，而是独立字段 `message.tool_calls`，配套 `finish_reason="tool_calls"`。所以**不需要正则去 content 里抠 JSON** |
| 拿到就能直接调工具 | **对一半** | 还差 4 步：`arguments` 是 **JSON 字符串**不是对象（要 `json.loads`）；要过 JSON Schema + 业务校验；结果要以 `role:"tool"` + `tool_call_id` **回填成新消息再请求一次**；模型可能返回多个 tool_calls |
| 解析过程不能对外展示 | **完全对** | 与三期"只转发 `content`、丢弃 `reasoning_content`"是**同一条规则** |

### 14.3 真实往返（4 步）

```
POST /chat/completions  messages=[..., user:"我的订单到哪了"]
  |
  v
resp.choices[0].message = { role:"assistant", content: null,
                            tool_calls:[{id:"call_1", type:"function",
                              function:{name:"query_shipment",
                                        arguments:"{\"order_no\":\"SO2026...\"}"}}] }
  |  arguments 是【字符串】，且是【模型生成的、不可信】
  v
服务端：json.loads → JSON Schema 校验 → 业务校验(actor/核验) → 调 fulfillment.list_shipments
  |
  v
POST /chat/completions  messages=[...,
      {role:"assistant", content:null, tool_calls:[...]},        <-- 原样回填
      {role:"tool", tool_call_id:"call_1", content:"{...}"}]    <-- 结果回填
  |
  v
最终回答（content）
```

### 14.4 "流式"到底卡在哪

| 模式 | 工具调用长什么样 | 复杂度 |
|---|---|---|
| `stream:false` | 一次性完整 JSON，`message.tool_calls` 直接可用 | 低 |
| `stream:true` | SSE 分块，`delta.tool_calls[i].function.arguments` 是**逐 token 片段**，要自己累积 buffer 拼完整；`id`/`name` 只在首块出现，`finish_reason` 到了才知道结束 | 高（buffer 拼接 + 多分支） |

**决定性事实（F25）**：三期 `llm.py` 的 `stream()` 只 `yield delta.content`（`llm.py:105-107`），**`delta.tool_calls` 被静默丢弃**。
→ 今天若直接开 `tools` 走流式，模型返回 tool_call 时会表现为**空回答**（一个字都没有），且不报错。这是必须改 `llm.py` 的硬理由，不是偏好。

全库 `grep finish_reason|tool_calls`（除 `.venv`）**零命中** —— 这两个字段当前完全没被读取。

### 14.5 "不能对外展示"的三条理由（都对）

| # | 理由 |
|---|---|
| 1 | **体验**：用户不该看到 `{"name":"query_order","arguments":"{\"order_no\":..."}` |
| 2 | **安全**：参数里含订单号、手机后四位等敏感值；暴露工具名与参数结构等于泄露能力清单，便于被诱导调用 |
| 3 | **一致性**：三期已确立"只有 `content` 才下发"的边界，tool_calls 属决策过程，遵循同一规则 |

但要区分：**不展示原始 JSON ≠ 不展示任何痕迹**。只出 `tool` 事件的"正在查询订单…"是好事（透明、掩盖等待）。

### 14.6 比"不展示"更要紧的：args 是**不可信输入**

模型不是攻击者，但用户输入可诱导模型生成恶意参数（"帮我查订单 SO2026-别人的号"）。
所以工具层必须：① JSON Schema `additionalProperties:false` 严格校验；② `resolve_order(db, actor, order_no)` 带 `customer_id` 过滤；③ **actor 永远来自 `conversation.user_id`，绝不能来自 args**。

### 14.7 新发现的硬约束（F26）

`assistant.message.role` 的 CHECK 只允许 `('USER','ASSISTANT','AGENT','SYSTEM')`（`0007…sql`）。
→ **`role:"tool"` 的消息无法落 message 表**（加值 = ALTER 三期 CHECK）。
→ 工具结果只能：进 `assistant.tool_call` + 作为**事实块注入第二轮 prompt**，不落消息表。这反过来印证了 §10.5 的"服务端事实块"设计。
---

## 15 流式 tool_calls 实测（第 7 轮，已跑真模型）

### 15.1 实测结论（deepseek-flash，各 2 次，`.env` 真 key）

| 模式 | 首个决策到达 | 首个可见文字 | 总耗时 | content |
|---|---|---|---|---|
| 非流式 + tools | 1115 / 1160 ms（**全部等待**） | — | 1115 / 1160 ms | `''` |
| **流式 + tools** | **690 / 915 ms** | 无 / 867 ms | — | **可能先说一句** |
| 流式，不带 tools（知识类） | 失败 | 失败 | — | 空，`finish_reason=length` |

**流式比非流式快约 400ms**：非流式必须生成完整响应才返回，流式在 `finish_reason` 到达前已把 tool_call 发出。

### 15.2 流式 tool_calls 的真实结构

```
块1   : delta.tool_calls[{index:0, id:"call_00_…", function:{name:"query_shipment", arguments:""}}]
        ↑ id 与 name 只出现这一次
块2..N: delta.tool_calls[{index:0, id:null, name:null, function:{arguments:"{"}}]
        后续逐 token 片段：'{' '"' 'order' '_no' '"' ':' …
末块  : choices[0].finish_reason = "tool_calls"
```

拼接骨架（进 `llm.py`）：

```python
buf = {}   # index -> {"id","name","arguments"}
if d.get("tool_calls"):
    for tc in d["tool_calls"]:
        slot = buf.setdefault(tc["index"], {"id": None, "name": None, "arguments": ""})
        if tc.get("id"): slot["id"] = tc["id"]
        fn = tc.get("function") or {}
        if fn.get("name"): slot["name"] = fn["name"]
        slot["arguments"] += fn.get("arguments") or ""
if ch.get("finish_reason") == "tool_calls":   # 只有到这一步 arguments 才完整
    calls = [json.loads(s["arguments"]) for s in buf.values()]
```

### 15.3 两个意外（必须写进实现约束）

| # | 现象 | 约束 |
|---|---|---|
| O1 | **流式会"先说一句再调工具"，且不稳定**：一次 690ms 直接出 tool_call，一次 867ms 先说"我先帮您查一下这个订单的物流状态。"再在 915ms 出 tool_call | 模型可能在工具执行前说出**结论句**（"您的订单已签收"）→ 幻觉。需 B2 的叙述缓冲 |
| O2 | **`max_tokens` 与推理 token 共享预算**：给 200 时知识类请求返回 `finish_reason=length` 且 content 为空 | `finish_reason=length` 必须**判为失败**，不能当"模型没话说"；项目现值 `llm_max_tokens=800` 可用，工具决策轮需单独配置 ≥600 |

### 15.4 决策 D6：**单段流式 + 首轮叙述缓冲（B2）**

| 项 | 定值 |
|---|---|
| 形态 | 单段流式；带 `tools` 的轮次里，`content` 先缓冲不下发 |
| `finish_reason` 分支 | `tool_calls` → 发 `tool` 事件、执行、缓冲叙述随结果一起下发；纯 `content` → 全量下发 |
| 多轮工具 | 最多 3 次；每轮仍需带 `tools`（否则无法连续调用） |
| 代价 | 约 0–200ms（叙述本应等结果再出），换掉"先下结论再查"的幻觉通道 |

### 15.5 必须改的三期代码（唯一破契约点）

| 文件 | 改动 | 影响面 |
|---|---|---|
| `app/integrations/llm.py:81-108` | `stream()` 从 `Iterator[str]` 改为 yield `("content", text)` / `("tool_call", {...})` | 内部函数签名，非 HTTP 接口 |
| `app/api/v1/assistant.py:200` | `yield from llm.stream_chat(...)` 改为 for 循环分发 | 同上 |
| `app/integrations/llm.py:29-54` | `FakeProvider` 增脚本化模式（见 §16.6） | 测试替身 |

`openapi.yaml`、前端类型、DB 均不动 → 不违反"不改接口字段"。

---

## 16 评测设计（第 7 轮，对齐 (h)/(i)）

### 16.1 最要紧的一条：**必须分三层，不能混算**

| 层 | 测什么 | 模型 | 门禁 |
|---|---|---|---|
| **L1 服务端链路** | 参数校验 / actor 过滤 / 核验门禁 / 确认状态机 / 幂等 / 审计 / 引用生成 / 事件顺序 | `FakeProvider` 脚本化 | **100% 阻断（`make test`）** |
| **L2 模型选择** | 工具选对率 / 拒答边界 / 是否编造 | 真 `deepseek-flash` | 记录**不阻断**（夜间/手工） |
| **L3 主观质量** | 是否有用、语气、是否啰嗦 | 人工抽检 10% | 报告 |

混算 = 评测假阳性的根源：fake 永远回固定串，"必须有引用"这种断言必然过，看着绿其实什么都没测。

### 16.2 用例格式：**YAML**（不是 JSONL）

理由：用例里是中文长文本，业务要参与审核 → 可读性优先；且团队已重度使用 YAML（`knowledge_raw/` 全 yaml）。
目录：`eval/cases/{knowledge,tool_read,tool_write,identity,refuse}.yaml`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | `EV-001` |
| `category` | enum | knowledge / tool_read / tool_write / identity / refuse / safety |
| `question` | str | 用户原话 |
| `setup` | map | `identity: verified\|none`、`order_no`、`seed_order_state` |
| `must_call_tool` / `must_not_call_tool` | list | L1 断言 |
| `must_cite` | bool | 引用数 ≥1 |
| `must_cite_doc` | list | 期望 `document_id` ∈ 集合 |
| `must_refuse` / `must_handoff` / `must_confirm` | bool | 边界断言 |
| `forbidden_patterns` | list(regex) | 禁止串（金额/手机/其他单号） |
| `expected_entities` | list | 本体归一期望（如 `QL-L3P`） |
| `layer` | enum | `L1` / `L2` |
| `notes` | str | 出处（SCN-xxx / KB-xxx） |

### 16.3 来源：**知识库已内置 20 个场景，不用凭空造**

| 来源 | 条数 | 说明 |
|---|---|---|
| `knowledge_raw/12_场景案例/` | 20 篇（SCN-001…SCN-020） | 每篇转 2–3 条用例 → **40–60 条**，其中 **SCN-017（查他人订单）、SCN-018（提示词注入要求泄密）是现成红队用例** |
| `09_客服SOP/` | 9 篇 | 拒答/升级边界 |
| 历史会话采样 | 10 条 | 三期会话量可能不足，缺则用 seed 造 |
| 合成 | 10 条 | 同义改写、口语化、错别字 |

**关键**：`SCN-018` 的原文已写明"禁止调用跨用户工具"、`SCN-017` 依据 `KB-SAFE-001` —— 评测用例与知识库是同一份真源，不是两套规范。

### 16.4 规模：起步 60，上限 120

| 类别 | 起步 | 上限 |
|---|---|---|
| knowledge（含本体归一） | 20 | 40 |
| tool_read | 15 | 30 |
| tool_write（含确认/幂等/不可撤销） | 10 | 20 |
| identity（未核验/跨单/过期/3 次锁） | 5 | 10 |
| refuse + safety（含 SCN-017/018） | 10 | 20 |
| **合计** | **60** | **120** |

### 16.5 Runner：**用 pytest，零新工具**

| 动作 | 落点 |
|---|---|
| 用例真源 | `eval/cases/*.yaml` |
| 用例 schema 校验 | `tests/test_eval_contract.py`（字段齐、id 唯一、category 合法） |
| L1 用例执行 | `tests/test_eval_l1.py`，`parametrize` 读 yaml |
| L2 用例执行 | `tests/test_eval_l2.py`，`@pytest.mark.eval_live`，`pytest.ini` 加 `addopts = -m "not slow and not eval_live"` |
| 报告 | `make eval-report` → `var/eval_report.{json,md}`（**`var/` 已被 .gitignore 忽略**，天然不入库） |

### 16.6 `FakeProvider` 必须脚本化（否则 tool 用例在 CI 跑不了）

现状：fake 只按最后一条 user 文本回固定串（`llm.py:44-54`），**不会返回 tool_call** → 所有工具类用例在 L1 层面无法执行。
要求：fake 增 `scripted` 模式，由用例的 `must_call_tool` 反推返回对应的 `tool_calls`，参数从 `setup` 取。
**注意**：这样测的是"服务端拿到 tool_call 之后的链路"，**不是模型选对率** —— 这正是 §16.1 分层的意义。

### 16.7 门禁阈值：**零退化（每例必过）**

不用 baseline 比较。规模只有 60 条，硬 100% 可行且含义明确："任何一条从过变成不过，就是退化"。
L2 不设阈值，只记录；连续 3 次 L2 指标下降 → 人工排查。

### 16.8 假阳性三防

| # | 防线 |
|---|---|
| 1 | L1 / L2 报告**分表列**，不混算总分 |
| 2 | `must_cite` 只断言"引用行数 ≥1 且 `document_id` ∈ 期望集"，**不断言"引用正确"**（那需要人工判定） |
| 3 | `forbidden_patterns` 宁严勿宽：金额（`\d+\.\d{2}元`）、手机（`1\d{10}`）、他人单号 |

---

## 17 累计待决

| # | 问题 | 状态 |
|---|---|---|
| Q4 | chunk↔entity 映射 = 新表 + 逻辑键 | 暂定 A |
| Q5 | 67 实体 / 105 关系 | 暂定够用 |
| Q6 | 工具清单 9 个 | **已定 A** |
| Q7 | F21 服务端推导 | **已定 A** |
| Q8 | 单段流式 + 叙述缓冲 | **已定 B2** |
| Q9 | 评测起步 60 条 / YAML / pytest runner | 本轮新提 |

---

## 18 范围三分类（终稿）

### 18.1 必须做（7 条）

| # | 条目 | 理由 | 不做的影响 |
|---|---|---|---|
| M1 | `ontology` schema 5 表（entity / relation / alias / entity_tag / chunk_entity）+ 审核态 + 追加式迁移 | 老板点名"本体"；关系表 + 递归 CTE 是零新存储的唯一解 | 四期标题落空 |
| M2 | 本体→检索集成：`normalize` 节点 + 深度 1 扩展，实体归一直接映射到二期已有 `filters.product_scope` | **零改二期代码**（F18），是性价比最高的集成点 | 本体只是"文档里的表"，不改善回答 |
| M3 | 9 个工具 + 严格 JSON Schema + `ToolSpec` 单真源注册表 | 老板点名"查订单、查商品" | 标题落空 |
| M4 | 写操作安全模型：`pending_action` + 二次确认 + CAS 幂等 + 3 时点审计 + 频次闸 + **单轮仅 1 写** | 没它写工具不敢开 | 工具退化为只读 |
| M5 | 核验↔工具门禁：接上 `active_verification()` + **修复 F21** | 现有核验 0 调用点；F21 不修则门禁无效 | 越权读取内部文档 |
| M6 | 单段流式 + 叙述缓冲（B2）+ `tool`/`action` SSE 事件（老 6 个不动） | 已实测流式快 400ms；且现有 `stream()` 会静默丢弃 tool_calls | 工具调用表现为空回答 |
| M7 | 评测 60 条（YAML）+ L1/L2 分层 + 零退化门禁 + `make eval-report` | 唯一能证明"工具没打坏 RAG"的手段 | 无法量化四期收益 |

### 18.2 可以延后（5 条）

| # | 条目 | 理由 | 影响 |
|---|---|---|---|
| D1 | LLM 从文档抽实体（含审核队列） | `product_catalog`/`product_warranty`/`escalation_matrix` 已覆盖约 80% | 本体覆盖窄但可控 |
| D2 | 本体多跳（深度 ≥2）与路径解释 | 检索侧深度 1 足够；深度 2 仅用于回答取证 | 复杂链路问答效果打折 |
| D3 | 写工具扩到 3 个以上（改地址、开发票、撤销售后） | 每个写工具要单独定文案/上限 | 只落地 2 个写工具 |
| D4 | LLM-as-judge | 不稳定 + 成本 + 无基线 | L3 主观维度靠人工抽检 |
| D5 | 本体可视化图谱页 | 无浏览需求就是纯成本 | 运营只看列表 |

### 18.3 明确不做（6 条）

| # | 条目 | 理由 | 影响 |
|---|---|---|---|
| X1 | 图数据库（Neo4j 等） | 规模（5 产品线、百级实体）用不上；违反"不引新运行时" | 深度遍历自写递归 CTE |
| X2 | 模型**无确认**执行写操作 | 误改单不可接受 | 多一轮交互 |
| X3 | 金额类写操作（退款/开票执行） | 资金动作的风控与对账成本远超收益 | "帮我退款"转人工 |
| X4 | 状态机 / 角色 / 渠道入本体 | 真源在 `order_workflow.yaml` / `role_permissions.yaml`；入本体 = 重造状态机 + 双真源 | 无 |
| X5 | 跨租户/跨渠道共享本体 | 单租户单渠道（`settings.tenant_id`） | 无 |
| X6 | 游客/未登录调用业务工具 | 无可追责主体 | 游客只能问知识 |

---

## 19 验收标准草案（可测，仿 `docs/三期/02_验收清单.md` 分组）

### A 通用门禁
| # | 判据 |
|---|---|
| A1 | `python -m pytest -q` → 0 failed，总数 ≥ 现有 + 60（评测用例） |
| A2 | `python scripts/check_frontend_contract.py` → `problems=0` |
| A3 | `cd web && npx tsc --noEmit && npm run build` → 0 error |
| A4 | 空库 `create_db.py` → `apply_migrations.py` → 表数 **68**；再执行一次全部 skipped |
| A5 | `git grep -nE 'sk-[A-Za-z0-9]{20,}'` 无命中；`.env` 未被跟踪 |

### B 数据与迁移
| # | 判据 |
|---|---|
| B1 | `ontology` schema 5 表存在；`assistant` 由 6 → 8 表 |
| B2 | 总表数 68（61 + 5 + 2） |
| B3 | `pending_action` 有 `UNIQUE(conversation_id, action_key)`；同 key 重放返回同一行 |
| B4 | `tool_call` 可按 `message_id` 反查；`status` 有 CHECK 枚举 |
| B5 | `tool:*` 4 个权限码存在，`AI_AGENT` 有 `tool:read`，`AI_SUPERVISOR` 有 2 个 `tool:write:*` |
| B6 | 一二三期表结构零变更（`grep 'ALTER TABLE' db/migrations/00*四期*` 只涉及新表） |

### C 本体
| # | 判据 |
|---|---|
| C1 | 导入脚本跑出 67 实体 / ≥100 关系；重复执行幂等 |
| C2 | 递归 CTE 深度 2 返回"指纹失灵 → 锁体电子 → 保修 24 个月"，且带 `depth` 与路径防环 |
| C3 | 别名最长匹配："指纹锁失灵"→ `QL-L3P`；"门锁"不误判到摄像头 |
| C4 | `chunk_entity` 逻辑键为 `(document_id, version, chunk_ord)`；发新版后按逻辑键重挂，**不重跑抽取** |
| C5 | `normalize` 节点命中实体时，`search()` 收到的 `filters.product_scope` 正确；未命中时 filters 为空且不改检索行为 |
| C6 | 二期 `knowledge_retrieval.py` **零改动**（`git diff` 无该文件） |

### D 工具
| # | 判据 |
|---|---|
| D1 | 9 个工具在 `TOOLS` 注册表内，`description` 均含"何时不要用"，写工具含"只生成待确认动作" |
| D2 | 参数校验：缺 `order_no` / 多余字段 → 拒绝执行，不调一期函数 |
| D3 | `arguments` 为字符串时先 `json.loads`；非法 JSON → 判失败不抛 500 |
| D4 | `actor` 只来自 `conversation.user_id`；构造伪造 args 无法越权（`SCN-017` 用例） |
| D5 | `resolve_order` 带 `customer_id` 过滤；他人订单号返回"未找到" |
| D6 | 单轮写工具调用 > 1 时被拒 |

### E 写安全
| # | 判据 |
|---|---|
| E1 | 写工具只生成 `PROPOSED`，`order.status` 未变 |
| E2 | 确认后执行一次；重复 confirm 返回同一结果（CAS + 幂等键） |
| E3 | `audit_log` 有 propose / confirm / execute 三条；`outbox_event` 有 `ai.action.*` |
| E4 | 10 分钟未确认 → `EXPIRED`，执行接口拒绝 |
| E5 | 确认卡片不含完整手机/地址/卡号（正则断言） |
| E6 | 单会话第 4 次写 → 拒绝；同一 order 24h 第二次取消 → 拒绝 |
| E7 | 写执行失败时消息明确"未做任何改动"，且不自动重试 |

### F 核验与 F21
| # | 判据 |
|---|---|
| F1 | 未核验调 `query_order` → 返回 `IDENTITY_REQUEST`，工具零执行（fake 调用次数 = 0） |
| F2 | 核验 A 单后查 B 单 → 视为未核验 |
| F3 | 核验过期后工具拒绝 |
| F4 | **客户端传 `identity_level="agent"` 不再解锁 agent 级切片**（F21 回归用例） |
| F5 | 员工带 `ai:chat:read` 仍可拿 agent 级 |

### G 流式与降级
| # | 判据 |
|---|---|
| G1 | 事件序列 `meta → (ping)* → (tool)* → (delta)* → (action\|citations) → done`，老 6 个事件载荷不变 |
| G2 | `tool_calls` 原始 JSON **不出现在任何 SSE 事件**里 |
| G3 | 带 tools 轮次：`finish_reason=tool_calls` 时缓冲的叙述不早于 `tool` 事件下发 |
| G4 | `finish_reason=length` → 判失败（非"空回答"） |
| G5 | 业务拒绝透传 code + 人话；404/越权统一"未找到" |
| G6 | 事实类问题回答不含模型自造的金额/单号（`forbidden_patterns` 命中 = 0） |

### H 评测
| # | 判据 |
|---|---|
| H1 | `eval/cases/*.yaml` ≥ 60 条，schema 校验通过，id 唯一 |
| H2 | L1 用例 100% 通过，进 `make test` |
| H3 | `make eval-report` 产出 `var/eval_report.md`，且 `git status` 干净（`var/` 已忽略） |
| H4 | L1/L2 报告分表，无"总分"字段 |
| H5 | 任一条用例人为改坏 → `make test` 失败（验证门禁真的生效） |

---

## 20 风险清单

| # | 风险 | 触发条件 | 缓解 |
|---|---|---|---|
| R1 | 本体范围失控 | 把状态机/角色/渠道塞进本体 | X4 写死；实体清单进 change 的 spec，新增需走变更 |
| R2 | LLM 抽取错误 | 启用 D1 时 | 本期不启用；alias 也走审核态 `PENDING/APPROVED` |
| R3 | 写操作误执行 | 模型编参数；用户注入诱导跨单 | Schema 严格 + `resolve_order` 过滤 + 二次确认 + `SCN-017/018` 用例 |
| R4 | 评测假阳性 | 混算 L1/L2；fake 断言当质量指标 | §16.1 分层 + 分表报告 + H4 |
| R5 | 模型成本与时延 | 多轮工具；reasoning tokens 计费 | 单轮 ≤3 次工具；决策轮 `max_tokens` 单配 ≥600；事实类走规则 fast-path |
| R6 | **F21 不修** | 只做新功能不碰三期 | M5 明确含修复；F4 为回归判据 |
| R7 | `max_tokens` 与推理 token 冲突 | 决策轮给太小 | G4 判失败；约束见 §15.3 O2 |
| R8 | `order_no` 解析缺失导致跨用户 | 直接复用 `assistant_handoff._order()` | 必须新建 `resolve_order` 带 actor 过滤（G1 缺口） |

---

## 21 change 拆分建议（3 个，按依赖排序）

| # | change | 覆盖 | 表数 | 依赖 | 独立可验收点 |
|---|---|---|---|---|---|
| 1 | `phase4-ontology` | ontology 5 表 + 导入脚本 + 审核态 + `normalize` 节点 + `chunk_entity` 回填 + 检索集成（深度 1）+ 深度 2 CTE 供取证 | 61 → 66 | 无 | C1–C6；`git diff` 证明二期检索零改动 |
| 2 | `phase4-tools` | `llm.py` 流式改造 + fake 脚本化 + 9 工具注册表 + `pending_action`/`tool_call` 2 表 + 确认/取消接口 + `tool:*`/`ai.tool.*` + `tool`/`action` SSE + **F21 修复** + `resolve_order` | 66 → 68 | 1（工具参数归一用 alias） | D1–D6、E1–E7、F1–F5、G1–G6 |
| 3 | `phase4-eval` | `eval/cases` 60 条 + `test_eval_contract` + L1/L2 runner + `pytest.ini` marker + `make eval`/`eval-report` + 零退化门禁 | 68（零新表） | 1、2 | H1–H5 |

并行度：change 3 的**用例编写**可与 2 并行，**执行**必须等 2。

---

## 22 澄清问题清单（7 组，每题 A/B/C + 选错的后果）

### 22.1 业务
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 业1 | 写工具灰度范围 | 全量客户 | 白名单渠道/客户 | 仅内部坐席先跑 | 选 A 若出错影响面大；选 C 则"工具调用"无客户可见交付 |
| 业2 | 本体维护责任人 | 内容运营 | 客服主管 | 研发代管 | 责任人不清 → 本体半年后腐化 |
| 业3 | 评测报告是否对外汇报 | 月度给老板 | 仅内部技术 | 不报 | 选 C 则四期收益无法呈现 |
| 业4 | 客诉/工单是否纳入本期 | 不做 | 只读工单查询 | 做全流程 | 一期无工单表，选 C 需造表 |

### 22.2 数据
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 数1 | 实体主键形态 | `text` code（`QL-L3P`） | `bigint` + code 列 | 复用 `commerce.product.id` | 选 C 会把本体绑死在一期表，改一次商品就崩 |
| 数2 | `chunk_entity` 回填范围 | 全量 158 篇 | 仅 5 产品线主档 | 仅 SCN 场景 | 选 B/C 则大量知识问答无实体增强 |
| 数3 | `alias` 是否收错别字 | 收 | 不收 | 收但标 `LOW` | 不收则口语提问命中率低 |
| 数4 | `tool_call.args` 是否存原文 | 存（含订单号） | 脱敏后存 | 不存只存摘要 | 存原文 = PII 扩散；不存则无法复现问题 |

### 22.3 流程
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 流1 | 确认超时后 | 直接取消 | 转人工 | 延长到 30 分钟 | 选 C 则挂起单堆积 |
| 流2 | 只读工具失败是否转人工 | 不转 | 转 | 仅 5xx 转 | 全转会让队列被超时噪声灌满 |
| 流3 | 写失败是否自动转人工 | 转 | 不转只提示 | 连续 2 次才转 | 选 B 则用户卡死无出口 |
| 流4 | 用例评审人 | 产品 | 客服主管 | 双方会签 | 单人审 → 用例只覆盖自己关心的 |

### 22.4 权限
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 权1 | `tool:read` 授予范围 | 仅 AI_AGENT | 所有员工 | 不设码（客户也能用只读） | 选 C 则失去灰度能力 |
| 权2 | 写工具是否按渠道再收窄 | 是 | 否 | 按客户白名单 | 不收窄则某渠道出事全渠道停 |
| 权3 | 本体权限码数量 | 3 个（read/write/audit） | 2 个（read/write） | 复用 `knowledge:*` | 复用会让知识运营意外获得本体写权 |
| 权4 | 评测报告读权限 | `tool:admin` | 新 `ai:eval:read` | 不限 | 不限则内部口径外泄 |

### 22.5 安全
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 安1 | F21 修复放哪 | 并入 `phase4-tools` | 单列 `phase4-security` | 延后 | 延后 = 门禁纸糊 |
| 安2 | 确认卡片是否显示手机后四位 | 不显示 | 显示 | 只显示"尾号 **34" | 显示完整后四位即为不该露的 PII |
| 安3 | 是否落 prompt 全文 | 不落 | 落脱敏版 | 落全文 | 落全文 = 用户原话里的 PII 进库 |
| 安4 | 工具失败是否回显底层错误串 | 不回显 | 回显 | 仅回显 code | 回显 = 泄露内部结构 |

### 22.6 交互
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 交1 | 确认按钮文案 | "确认取消订单" | "确认" | "继续" | 泛化文案 → 用户误点 |
| 交2 | 工具执行中表现 | 骨架卡"正在查询…" | 三点动画 | 无提示 | 无提示 → 用户以为卡死 |
| 交3 | 事实卡片 | 可折叠 | 常驻 | 不展示（只文字） | 不展示 → 模型复述数字风险回来 |
| 交4 | 撤销入口 | 结果卡内按钮 | 跳转售后页 | 不给 | 不给则用户只能找人工 |

### 22.7 非功能
| # | 问题 | A | B | C | 选错的后果 |
|---|---|---|---|---|---|
| 非1 | 事实类首字节目标 | 待实测后定 | `≤1.5s` | `≤2.5s` | 先拍数字 = 编指标 |
| 非2 | 工具超时 | 读 3s / 写 8s | 统一 5s | 统一 10s | 统一值要么拖垮只读、要么砍断写 |
| 非3 | 单轮工具次数上限 | 3 | 1 | 5 | 选 5 则 token 与延迟不可控 |
| 非4 | 本体递归深度上限 | 检索 1 / 取证 2 | 统一 2 | 统一 3 | 统一 3 会让 token 爆炸 |

---

## 23 下一步

1. 本笔记的 §18–§22 是本轮交付物；需求说明书正文与验收清单正式版落 `docs/四期/01_四期需求说明书.md`、`docs/四期/02_验收清单.md`（**尚未创建，需确认**）。
2. 转 `/openspec-propose` 建 3 个 change（§21），建议顺序：`phase4-ontology` → `phase4-tools` → `phase4-eval`。
3. §22 的 27 个问题不阻塞拆 change；其中 **业1、数1、数4、安1、非1** 建议在 propose 前定，否则 spec 里会出现"待定"。
