# 三期收口补丁（phase3-assistant-polish）

## Why

三期已交付并归档，但留下三处欠账，其中一处影响**安全底线是否真的生效**：

1. **护栏的别名表写在代码里，且没有任何完整性校验**。escalation 规则的 `triggers` 是英文标识符（`person_trapped`、`remote_unlock`…），用户提问是中文，必须靠 `ESCALATION_ALIASES` 做桥接。这张表是我按 YAML 语义补的，**遗漏一条别名，就等于那条安全规则永远不会触发**，而系统不会有任何提示。
2. **自动转人工只挂了 2/5 类触发**（`USER_REQUEST`、`IDENTITY_FAILED`）。`HIGH_RISK_RULE`、`NO_HIT`、`MODEL_ERROR` 的接口已留但未接线——高风险问题会照常回答、不转人工。
3. **点赞点踩后端已通，前端没有入口**（验收清单 I7 未达成）。

## What Changes

- **别名表外置为数据文件**（`knowledge_raw/13_结构化规则/escalation_aliases.yaml`），代码保留内置回退；新增**完整性自检**：每条带 `forbid` 的 escalation 规则必须有至少一个中文别名，缺失即测试失败并打印缺失清单。
- **补齐 3 类自动转人工**：`HIGH_RISK_RULE`（护栏命中）、`NO_HIT`（同一问题第二次仍无命中）、`MODEL_ERROR`（生成异常）。
- **前端接点赞点踩**：回答气泡加两个图标，点踩可选原因，写 `message.metadata.feedback`。

## Impact

- 受影响 specs：`assistant-answer`（新增别名表可维护与完整性要求）、`assistant-console`（新增回答反馈要求）。
- 受影响代码：`app/services/assistant_graph.py`（别名加载 + 护栏）、`app/api/v1/assistant.py`（转人工接线）、`web/src/pages/assistant/ChatPage.tsx`（反馈入口）、新增别名数据文件与自检测试。
- 数据：**无表结构变更**，表数保持 61；`assistant.message.metadata` 已能存 feedback，不新增列。
- 数据库迁移：无。
