# Design

## Context

见 `proposal.md` - Why。三条实测事实塑造方案：

| # | 事实 | 出处 |
|---|---|---|
| F1 | `order.list_orders` 的 `keyword` 只匹配 `order_no` / `receiver_name`，**不匹配商品名**；且列表默认不带明细 | `app/services/order.py:191-210` |
| F2 | embedding **冷启动 12.1 s**、预热 7 ms；检索 20–55 ms；LLM 首 token 1.4 s | 实测 |
| F3 | “门锁”是上位词，产品名“栖云智能门锁 L3 Pro”含该子串；spec 明确“上位词不误判具体型号” | `ontology` spec |

## Goals / Non-Goals

**Goals**
- 让“我订单里那个门锁，能退货么”这类问题走通：列单 → 按商品筛 → 查售后 → 叠加政策
- 归一能容忍错别字/口语，同时不破坏“上位词不误判”
- 首个问题的等待从 ~13.5 s 降到 ~2 s 量级（把模型加载挪到启动）

**Non-Goals**
- 不给实体建向量索引（实测足以用低成本方案覆盖，见 D3）
- 不改一期 `list_orders` 的过滤语义（越界）
- 不做“按订单反查商品目录”的双向映射

## Decisions

### D1 新工具 `query_my_orders` 自己筛商品，不改一期

一期 `list_orders` 的 keyword 只认单号/收件人（F1）。方案：工具内部 `list_orders(page_size=N)` 拿最近 N 单，再逐单 `get_order`（带明细）在**进程内**按 `product_name` 过滤。

- N 上限 10 → 最多 11 次查询，实测单次 <5 ms，总开销可接受
- 备选：给 `list_orders` 加商品名过滤（改一期语义，否决）；或直接写 SQL JOIN order_item（绕过服务层，否决）

参数：`{product_keyword?, status?, limit?}`；返回每单的 `order_no / status / created_at / items[{product_name, quantity, after_sales_status}]`。

### D2 路由：加"我的单据"词表，不加"订单"这个泛词

新增 `MY_ORDER_WORDS = ("我订单", "我的订单", "订单里", "我的单", "我买的") → IDENTITY_REQUEST`（进工具分支）。
**不加**单独的"订单"二字：否则"订单怎么取消"这类政策问题也会被塞进工具分支，白付一次模型往返。

### D3 归一：先做 2-gram 模糊，不上向量

向量方案的成本核算：查询向量本来就在 `search()` 内部算（+7 ms），但实体侧需要新增向量列/表 + 回填 + 阈值调参，且会引入“语义漂移”这类难解释的错误。

2-gram 方案：把问题与每个实体的 `name/alias` 都切成二元组，算 Jaccard；**唯一最优且 ≥0.5** 才采纳。

- 成本：80 实体 × 少量别名，纯 CPU，实测 <2 ms
- 安全：多候选并列直接放弃（spec 的“多候选并列时放弃”）
- 局限：解决错别字/语序，不解决“上位词”

### D4 上位词：只 boost，不过滤

“门锁”这类词不进 `alias`（否则违反“上位词不误判”），而是走**宽松命中**：问题里出现某产品 `name` 的 ≥2 字子串 → 把该产品实体加入 `state.boost_entities`，`rank_by_ontology` 对命中这些实体的切片加权前置。

- 不产生 `filters`，可见范围不变（spec 的“排序不改变可见范围”）
- 不会把“门锁”说成“QL-L3P”去过滤

### D5 启动预热 embedding

`app/main.py` 的 lifespan 里起一个后台线程：加载模型 + 编码一次空串。

- 不阻塞启动（后台线程），失败只告警
- 需要能关闭（测试环境设 `APP_ENV=test` 时不预热，避免测试启动变慢）

### D6 评测补 3 条，并且有一条是“不得调用”

| 用例 | 断言 |
|---|---|
| 我订单里门锁那个能退么 | `must_call_tool: [query_my_orders]` |
| 我的订单都有什么 | `must_call_tool: [query_my_orders]` |
| 七天无理由退货有什么条件 | `must_not_call_tool: [query_my_orders]`（防止过度调用） |

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 逐单取明细带来 N+1 | N≤10 且单次 <5 ms；后续可下沉为 SQL 但需走 change |
| 模糊匹配误命中 | 唯一最优 + ≥0.5 阈值 + 多候选放弃 + 评测覆盖 |
| 宽松命中把排序带偏 | 只 boost 不过滤；`ontology_rank` 观测里记录 boosted 数量，可回归 |
| 预热让启动变慢 | 后台线程、不阻塞；测试环境跳过 |

## Migration Plan

无迁移。部署后重启服务即生效；回滚只需回退代码（无数据结构变化）。

## Open Questions

1. 实体向量匹配是否值得做？成本已核算（+7 ms 查询侧，实体侧需回填）——留待样本量更大时再评估。
2. `limit` 默认值 10 是否够？若客户单量常见 >10，需要提供“翻页”或按状态收窄。
