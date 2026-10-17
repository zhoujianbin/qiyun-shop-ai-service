# Design — 三期收口补丁

## Context

三期（`phase3-assistant`）已归档：31 条 requirement 进主 specs。本补丁不改架构，只补三处欠账。现状事实：

- `app/services/assistant_graph.py` 中 `ESCALATION_ALIASES` 是 20 条硬编码字典。
- `guard_hints()` 读 `knowledge.rule` 中 `source_kind='escalation'` 的行，用 triggers + 别名匹配。
- 流式端点在 `_finish` 里只更新消息状态，不创建 handoff。
- `POST /ai/messages/{id}/feedback` 已实现并有测试，前端未调用。

## Decisions

### 决策 1：别名表外置为 YAML，代码保留内置回退

```
knowledge_raw/13_结构化规则/escalation_aliases.yaml
  person_trapped: [被困, 关在里面, 出不去]
  remote_unlock: [远程开锁, 远程开门]
```

- 加载顺序：文件存在且可解析 → 用文件；否则用代码内置字典（保证离线与测试可用）。
- 为什么外置：别名属于**业务话术资产**，应由业务方维护，不该埋在 Python 里等我们改代码。
- 为什么保留回退：删除/损坏文件不应让护栏整体失效。

**备选**：存进数据库表（要新增表与后台页面，本期过重）；只留代码（业务方无法维护，否决）。

### 决策 2：完整性自检是硬门禁

新增测试：对每条 `source_kind='escalation'` 且 `forbid` 非空的规则，要求 `triggers` 里**每个** trigger 在别名表里有至少一条中文别名（trigger 本身是英文时）。

- 失败时打印缺失的 `rule_id + trigger` 清单。
- 为什么是硬门禁：漏一条别名的后果是"安全规则静默失效"，这比报错严重得多。

### 决策 3：3 类自动转人工在流式链路里接线

| 触发 | 判定点 | 记录 |
|---|---|---|
| `HIGH_RISK_RULE` | `finalize` 后 `state.guard_hints` 非空 | 回答带安全提示，同时建 handoff |
| `NO_HIT` | 同一会话里**第二次**同主题无命中（`state.decision == 'REFUSE'` 且前一条助手消息也是拒答） | 建 handoff 并告知已转人工 |
| `MODEL_ERROR` | 生成异常分支 | 先置消息 FAILED，再建 handoff |

- 幂等：`create_handoff` 已有"同会话只允许一个未决"的部分唯一索引，重复触发返回已有记录。
- `CLARIFY`（首次无命中）**不**转人工——这是设计里"先反问一次"的语义。

### 决策 4：点赞点踩复用已有端点与 JSONB

- 前端点踩弹一个原因选择（答非所问 / 没有引用 / 内容过时 / 不安全），写入 `message.metadata.feedback`。
- 不新增表、不新增列。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 外置 YAML 被删或写坏 | 代码内置回退 + 启动时 WARN 日志 |
| 完整性门禁过严（英文 trigger 无需别名也会报） | 只校验"英文标识符形态"的 trigger；中文 trigger 直接跳过 |
| `NO_HIT` 误判（用户换个问法就转人工） | 仅当连续两条助手消息都是拒答才触发 |
| 自动转人工打扰客服 | 已有"同一会话只允许一个未决"约束；关单可退回 AI |

## Migration Plan

- 无数据库变更；新增 1 个数据文件与 1 个测试文件。
- 回退：删除 YAML 即回到内置字典；前端图标可单独回滚。

## Open Questions

1. 点踩原因的四项是否满足业务分类（当前沿用探索阶段结论）。
2. 别名表最终词条需业务确认（本补丁给出可维护载体 + 完整性门禁，词条内容仍需人工过一遍）。
