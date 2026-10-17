# Design — 客户侧多会话列表

## Context

- GET /ai/conversations 已返回当前客户自己的会话（tenant_id + user_id 过滤，按 updated_at desc），字段含 conversation_no / title / status / message_count / last_message_at。
- GET /ai/conversations/{id}/messages 可分页拉历史；POST .../close 关闭会话。
- 现状：ChatPage 挂载时只拉「最近一条」并恢复，没有列表 UI。

## Decisions

### 决策 1：列表数据直接复用现有接口，不加后端

GET /ai/conversations?page_size=50 足够；不新增「未读」字段。为什么不加未读数：三期没有客服推送通道，未读需要额外状态位与轮询，收益低。

### 决策 2：默认选中「最近一条进行中」，而不是「最近一条」

已结束会话不该抢占默认视图——用户进来是想继续聊。若无进行中会话则新建。

### 决策 3：已结束会话可查看但不可提问

后端对已关闭会话的流式请求返回 409（已有行为）。前端在选中已结束会话时禁用输入区并提示「该会话已结束，可新开会话」，避免用户白打字。

### 决策 4：列表排序与标题靠刷新，不做本地插入

发送消息后 invalidateQueries 重拉列表，标题（首问前 30 字）由后端写入，避免前后端两套标题逻辑。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 会话多时列表变长 | page_size=50，超出不翻页（三期客户会话量级小）；后续需要再加「加载更多」 |
| 切换会话时丢失正在生成的回答 | 生成中禁止切换（发送中禁用列表点击） |
| 已结束会话堆积 | 保留期 90 天由 assistant_cleanup.py 清理 |

## Migration Plan

- 纯前端改动；回退即还原 ChatPage.tsx。