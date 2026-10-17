# Design

## Context

见 `proposal.md` - Why。以下是塑造方案的事实约束（均实测，出处见 `openspec/explore/phase4-notes.md` §0）：

| # | 约束 | 出处 |
|---|---|---|
| C1 | 二期检索的 `filters` **只认两个键**：`category`、`product_scope`（打在 `knowledge.document` 上） | `app/services/knowledge_retrieval.py:61-66` |
| C2 | **召回后无法再过滤**——筛条件在 SQL 里，不在结果集上 | 同上 |
| C3 | 三期"LangGraph 图"实为**手写 5 函数循环**，无 StateGraph / 无 checkpointer | `app/services/assistant_graph.py:207-379` |
| C4 | `llm.py` **无 `tools` 通道**；`stream()` 静默丢弃 `delta.tool_calls` | `app/integrations/llm.py:70-80,105-107` |
| C5 | 一期服务**自带 `db.commit()`** | `app/services/order.py:264`、`aftersales.py:115` |
| C6 | `assistant.message.role` CHECK 仅 4 值，**加不了 `TOOL`** | `db/migrations/0007` |
| C7 | `assistant.handoff.reason` 是 **CHECK 5 值**，加不了新原因 | 同上 |
| C8 | 仓库**无 CI**，唯一门禁是 `make test` / `make contract` | `Makefile` |
| C9 | `var/` 已被 gitignore | `.gitignore` |
| C10 | 流式 tool_calls 实测可用：首块给 `id`+`name`，后续 `arguments` 逐 token，`finish_reason=tool_calls` 收口；决策 690–915ms vs 非流式 1115–1160ms | 实测（notes §15） |

## Goals / Non-Goals

**Goals**
- 本体集成**零改二期代码**（用 C1 的既有键，不碰 C2）
- 写路径在"一期服务自带 commit"（C5）的现实下仍然可审计、可重放、可判定失败
- 事件与协议只做**加法**：老三期 6 个 SSE 事件、6 张表、`reason` 枚举、`role` 枚举全部不动（C6/C7）
- 评测在**无 CI**（C8）的现实下落地：门禁就是 `make test`
- 首 token 不再多付一次模型往返给知识类问题

**Non-Goals**
- 不引入 LangGraph StateGraph / checkpointer / ToolNode——现有骨架够用，换框架不带收益只带迁移风险
- 不做工具注册表的数据库化（双真源风险）
- 不把工具结果写进 `message` 表（C6）
- 不修改 `knowledge_retrieval.py` 的任何一行

## Decisions

### D1 本体表示：关系表 + 递归 CTE（深度 1/2 分用途）

关系表 5 张，**两家不用**：JSONB 单文档（改一条边要重写整份，且 JOIN 不了）；图数据库（违反"不引新运行时"，规模也不到）。

实测推导出的关键结论：**一跳不够**。"指纹失灵 →(SYMPTOM_OF) 锁体电子 →(COVERED_BY) 保修 24 个月"是两跳。但两跳用在检索上会放大 token 与跑题，所以按用途分：

| 用途 | 深度 | 理由 |
|---|---|---|
| 检索扩展 | 1 | 只借邻接实体的 `product_scope`，多一分都是噪声 |
| 回答取证 | 2 | 保修期限必须经"故障→部件→规则"才拿得到 |

递归 CTE 带 `depth` 列 + 路径数组，遇环截断。

### D2 本体对齐检索的位置：**必须在检索前**

被 C2 逼出来的——过滤发生在 SQL 里，召回后没有第二次机会。所以：

```
question
   |
   v
[normalize]  别名最长匹配 → 实体 → product_scope / entity_ids    <-- 新增节点
   |
   v
 [plan]  ──> KNOWLEDGE ──> [retrieve(search(filters))] ──> [expand 深度1] ──> [finalize]
   |                          └─ 零实体命中 → filters 为空，行为与三期完全一致
   +──> FACT ──> [tool_loop] ≤3 次，写则 propose 后结束本轮
   +──> IDENTITY ──> 回核验请求（不调模型、不调工具）
   +──> HUMAN ──> 转人工
```

**备选**：在检索后对 hits 做实体重排。否决——那只是换了排序，不解决"该收窄时没收窄"。

### D3 工具定义放代码，不建表

二期吃过 `product_catalog.yaml` 与 `commerce.product.model_code` 双真源的亏（`phase2-decisions.md:44` 已判定要消除）。9 个工具、变更随发版走，**建表就是重演**。开关与灰度用权限码 + 配置。

### D4 写路径拆两段事务（被 C5 逼）

```
propose : 写 pending_action(PROPOSED) ── commit ── 本轮结束
confirm : CAS PROPOSED→CONFIRMED ── 调一期服务(其内部 commit) ── 写 EXECUTED + audit + outbox
```

代价是"执行中"这个中间态可见；收益是失败可判定、可人工重试，而不是半截不知道发生了什么。

推论（写进 spec 的硬约束）：**单轮最多 1 个写工具**。多写无法回滚，只能靠拆轮次保证语义。

### D5 确认不恢复图

图无持久化状态（C3），也**不打算**为确认引入 checkpointer。确认是一个**新 HTTP 请求**：服务端从 `pending_action` 读参数、独立执行、写一条 ASSISTANT 消息。图状态与确认流程解耦，重启服务不丢确认。

### D6 流式形态：单段流式 + 首轮叙述缓冲（B2）

C10 证明流式可用且更快，但实测暴露一个不稳定行为：**同一问题两次，一次 690ms 直接给 tool_call，一次 867ms 先说"我先帮您查一下…"**。理论上它也可能先说"您的订单已签收"再执行——那就是幻觉。

所以：带 `tools` 的轮次里 `content` **先缓冲**，等 `finish_reason`：

| `finish_reason` | 动作 |
|---|---|
| `tool_calls` | 先发 `tool` 事件 → 执行 → 缓冲叙述随结果一起下发 |
| 纯 `content` | 全量下发（无损） |
| `length` | 判失败（`max_tokens` 与推理 token 共享预算，实测给 200 会返回空） |

**备选**：两段式非流式决策——实测慢 400ms，且知识类本来就不进决策阶段，选它等于白付。

### D7 `identity_level` 改服务端推导（F21）

现状：`StreamRequest.identity_level` 由客户端上传并直通检索，传 `"agent"` 即可解锁内部切片。
修法：**字段保留**（前端与契约零改动），服务端忽略入参，改由 `active_verification()` 推导 + 员工权限判定。

**备选**：删字段——更干净，但要改前端类型 + openapi + contract 检查，违反"不改接口字段"的规约。

### D8 工具失败不改 `handoff.reason`（被 C7 逼）

`reason` 是 CHECK 5 值，加 `TOOL_FAILED` 就是 ALTER 三期表。所以：沿用 `MODEL_ERROR`，`summary` 写 `TOOL_FAILED:<tool>:<code>`，明细进新表 `tool_call`。

### D9 工具结果不落 `message` 表（被 C6 逼）

`role` 加不了 `TOOL`。所以工具结果只进 `tool_call` 表 + 作为**事实块注入第二轮 prompt**。这反过来正好支撑"模型不复述具体数值"的 spec 要求——事实块由服务端渲染，模型只写叙述句。

### D10 评测分三层，门禁只压 L1

无 CI（C8）→ 门禁就是 `make test`。因此：

| 层 | 执行 | 门禁 |
|---|---|---|
| L1 服务端链路（fake 脚本化） | 进 `make test` | 100% 阻断 |
| L2 真实模型 | `@pytest.mark.eval_live`，默认跳过 | 只记录 |
| L3 主观质量 | 人工抽检 10% | 报告 |

不混算总分——这是"评测假阳性"的唯一根治办法。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 本体范围失控（状态机/角色/渠道被塞进来） | 实体清单写进 spec；"明确不做"含状态机入本体 |
| 一期服务自带 commit 导致确认与实际执行之间存在窗口 | 两段事务 + CAS + 频次闸 + 审计三时点 |
| 写工具被 prompt injection 诱导跨单 | 参数不可信 + `resolve_order` 带 `customer_id` + 执行前二次校验 + SCN-017/018 用例 |
| 模型在工具执行前说出结论句 | D6 叙述缓冲 |
| `max_tokens` 与推理 token 共享预算导致空回答 | 决策轮 `max_tokens` 单配 ≥600；`finish_reason=length` 判失败 |
| 评测假阳性 | 分层 + 分表报告 + "改坏一条必须失败"的自检 |
| 本体半年后腐化 | 审核态 + 单一维护责任人 + 导入幂等 |

## Migration Plan

| 步骤 | 内容 | 回滚 |
|---|---|---|
| 1 | `0009_ontology_schema.sql`（5 表 + 索引 + 注释，全部 `IF NOT EXISTS`） | `DROP SCHEMA ontology CASCADE` |
| 2 | `0010_assistant_action.sql`（`pending_action` + `tool_call`） | `DROP TABLE` 两表 |
| 3 | `0011_ontology_tool_permissions.sql`（7 个权限码 + 授权，`ON CONFLICT DO NOTHING`，空库跳过） | 删权限码与绑定 |
| 4 | 导入脚本（幂等） | 删除 `source='import'` 的行 |
| 5 | 回填 `chunk_entity`（幂等，按逻辑键） | 清空该表 |

三步迁移均可在空库与既有库上重放；表数 61 → 66 → 68。前端与 `openapi` 在接口落地后统一重导出。

## Open Questions

1. 事实类问题的端到端首字节目标值——需在实现后实测再定，不预设数字。
2. 本体维护责任人（内容运营 / 客服主管）——不影响本 change 的技术方案，属运营安排。
3. `tool_call.args` 的脱敏规则明细（保留单号前缀几位）——实现时按最小可复现原则定。
