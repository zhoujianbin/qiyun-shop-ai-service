# 三期探索笔记（决策台账）

> 性质：探索笔记，**不驱动实现**；实现以 OpenSpec change 为准。
> 上游：`docs/二期/01_二期需求说明书.md` 附录 A.1（三期摘要）、二期实际代码。
> 交付物：`docs/三期/01_三期需求说明书.md`、`docs/三期/02_验收清单.md`。
> 本文件记录"为什么这么定"，与需求说明书互补。

---

## 0 事实基线（实测，优先于文档表述）

| # | 事实 | 出处 |
|---|---|---|
| F1 | 检索是**进程内 service**，非 HTTP：`search(db, query, *, filters, top_k, actor, identity_level)` | `app/services/knowledge_retrieval.py:92` |
| F2 | 阈值二期已内建：向量 0.35、全文 0.15、RRF k=60 | 同文件 :19-21 |
| F3 | `hits` 只有稳定引用字段；分数在 `debug`，且二期 spec 明确"三期勿依赖" | `knowledge-retrieval` spec |
| F4 | 向量：bge-small-zh-v1.5 / 512 / 查询加指令前缀 | `app/integrations/embedding.py` |
| F5 | 规则**不参与检索**（D12），护栏拿不到 forbid 除非另走结构化查询 | `docs/二期/01…` §5.4 与二期 design 决策 4 |
| F6 | `assistant` schema 不存在；库内 55 表；migrations 只到 0006 | `db/schema.sql` |
| F7 | 中间件在 SSE 响应上**提前 return，不写 COMPLETED** → 幂等记录永久 IN_PROGRESS | `app/core/middleware.py:101-111` |
| F8 | 前端全走 axios，无 `fetch` 直连；EventSource 不能带 header | `web/src/**` |
| F9 | 游客是真实 `app_user(party=GUEST)`，有 token | `app/services/identity.py:135` |
| F10 | 一期有客服↔客户消息表 `commerce.after_sales_message`，语义是工单 | `db/schema.sql:801` |
| F11 | 二期认领制先例：`review_task.assignee_id` + PENDING/CLAIMED | `app/services/knowledge_review.py:93` |
| F12 | DeepSeek `deepseek-flash` 已连通：首 token 255ms，流里含 `reasoning_content` | 实测（.env 已配） |
| F13 | 二期 design 说 chunk.metadata 存 product_scope/effective_until，实际未存 | `knowledge_import.py:330-334` |

---

## 1 决策台账

### 1.1 入口与身份（B1/B2）

| ID | 决策 | 理由 |
|---|---|---|
| D1 | 客户侧**先做独立页 `/assistant`**；`CustomerShell` 挂入口按钮，浮窗不复制对话逻辑 | 浮窗需全局状态提升 + 移动端适配；独立页 SSE 生命周期绑页面组件，最稳 |
| D2 | **游客可问知识类；订单/退款/设备类必须登录 + 核验** | 游客也是 user（F9），无需特例；登录提供可追责主体 |
| D3 | `conversation.user_id` NOT NULL + `party`(CUSTOMER/GUEST) | 同上 |

### 1.2 数据与协议（(b)/(a)）

| ID | 决策 | 理由 |
|---|---|---|
| D4 | 新 `assistant` schema **6 张表**（含独立 `citation`）；55 → **61** | 四期评测要按引用逐条统计，jsonb 难 JOIN |
| D5 | `message.role` 四值：USER/ASSISTANT/**AGENT**/SYSTEM | 客服回话进同一时间线，避免 UNION |
| D6 | `conversation.ai_paused` 唯一表示"AI 是否闭嘴" | 与 handoff 状态联动，不另建表 |
| D7 | `seq` 用会话行锁 + `message_count+1` | 会话内连续无空洞，游标分页简单 |
| D8 | 幂等靠 `UNIQUE(conversation_id, client_msg_id)` | 重发返回同一消息，不重复生成 |
| D9 | SSE over **POST + fetch ReadableStream**，Bearer 鉴权 | EventSource 不能带 header（F8）；token 不进 query |
| D10 | **SSE 端点必须加中间件幂等豁免** | 否则留下永久 IN_PROGRESS（F7） |
| D11 | 先落 USER + 占位 ASSISTANT(STREAMING)，结束再更新终态；超 2 分钟置 FAILED | 断线可见"已中断"，可重试 |
| D12 | 断线不补发，重连拉历史；15s ping；响应头 `X-Accel-Buffering: no` | 无状态服务，不引入 token 缓存 |

### 1.3 编排与生成（(c)/(d)/(e)）

| ID | 决策 | 理由 |
|---|---|---|
| D13 | LangGraph 3 节点 + 1 回路；**计划 ≤2 步**；最大 4 步 / 1 次 replan / 30s；不用 checkpointer | 三期只有 1 个工具，多步无收益；但要给四期留接口 |
| D14 | 意图**规则词表优先，未命中才调 LLM planner** | 保护首 token（否则每题先付 ~1s） |
| D15 | LLM = DeepSeek `deepseek-flash`，OpenAI 兼容 HTTP；**只转发 `content`，丢弃 `reasoning_content`** | 推理内容不能给用户看，且虚增 token（F12） |
| D16 | 引用只由服务端从 `hits` 生成；**无命中不调模型**，先反问一次 → 仍空则拒答 | 模型会编引用；反问能救回口语化提问 |
| D17 | 阈值不在三期再定（F2）；分数不参与三期决策（F3） | 避免把 RRF 常量当业务阈值 |

### 1.4 核验与转人工（(f)/(h)）

| ID | 决策 | 理由 |
|---|---|---|
| D18 | 核验 = 订单号 + 收货手机后四位；通过后 30 分钟有效，只放宽该订单的只读可见范围 | 不写业务数据 |
| D19 | 核验后给**固定事实快照**（非工具）：订单号/状态/实付/下单时间/物流状态+运单号/售后进度 | 否则核验毫无收益；但通用工具属四期 |
| D20 | 6 字段白名单；永不展示完整手机/地址/卡号/身份证/其他订单/开锁凭证 | 安全红线 |
| D21 | 转人工 5 触发；**认领制**（复用 review_task 模式）；接单即 `ai_paused=true`；关单必填结论 | 无需 presence 基础设施；避免 AI 与客服抢话 |
| D22 | **不自动建售后工单**；会话与工单解耦 | 多数会话无订单，建出来也是脏单 |
| D23 | 护栏规则来源 = 读 `knowledge.rule` 的 escalation `triggers` 词表匹配 | 规则不走向量（F5）；词表是业务给的，确定可测 |

### 1.5 交互与预埋（(g)/(i)）

| ID | 决策 | 理由 |
|---|---|---|
| D24 | 微信式 12 条交互（气泡/头像/时间分组/思考态→流式/引用折叠/快捷问题/输入规则/历史加载/重试/点赞点踩/无多会话侧栏/可结束） | 对齐老板口径"类似微信对话框" |
| D25 | 客户侧引用**只展示不跳转**（后台详情需员工权限，会 403） | 零成本；跳转需公开片段接口（可延后） |
| D26 | 四期预埋：`citation.entity_tags`（product_line/rule_id 两类）、`ToolSpec{read_only,requires_identity,scope}`、十字段埋点 | 只留位不实现，四期加工具不改图 |

---

## 2 与既有 change 的偏差（已回写）

初版 `phase3-assistant` 与本轮结论有 9 处不一致（表数 60→61、缺 citation 表、缺 AGENT 角色、缺 ai_paused、缺事实快照与字段白名单、护栏来源未定、SSE 细节缺失、转人工缺认领制、入口形态未定）。已通过 update-change 回写。

---

## 3 仍开放的问题（不阻塞实施）

1. 会话保留期最终值（当前建议 90 天）。
2. PDF/XLSX 与真实 DOCX 回归（二期遗留，不影响三期）。
3. 客服工作台是否要"会话内搜索"（本期不做）。
4. 成本监控口径（月度按 token 总量对账，单价以账单为准）。

---

## 4 下一步

`/openspec-apply-change phase3-assistant`，从组 1（schema + LLM 适配器）开始；实施第一步先验证 `langgraph` 在 Python 3.13 可安装，装不上则退回手写循环（Q5-B），specs 与任务不变。
