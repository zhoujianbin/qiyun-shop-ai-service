# Tasks

> 三组：别名表与门禁 → 转人工接线 → 前端反馈。每条任务的"验证"必须当场可执行。

## 1. 别名表与完整性门禁

- [x] 1.1 新增数据文件 `knowledge_raw/13_结构化规则/escalation_aliases.yaml`（20 条 trigger → 中文别名）；验证：文件可被 YAML 解析，条目数 ≥ 20
- [x] 1.2 在 `assistant_graph.py` 增加 `load_escalation_aliases()`：优先读文件，失败回退内置字典并打 WARN；验证：删掉文件后护栏仍能命中（单测）
- [x] 1.3 `guard_hints()` 改用加载结果；验证：现有护栏测试保持通过
- [x] 1.4 新增完整性测试：每条带 `forbid` 的 escalation 规则，其英文 trigger 都必须有中文别名；验证：`pytest -q tests/test_assistant_guard_alias.py`，缺项时打印 rule_id + trigger
- [x] 1.5 在 `docs/知识库运维.md` 追加"别名表维护"小节（谁改、怎么改、门禁怎么跑）；验证：文档含运行命令

## 2. 自动转人工接线

- [x] 2.1 `HIGH_RISK_RULE`：`guard_hints` 非空时创建 handoff；验证：远程开锁问题后该会话存在一条 `HIGH_RISK_RULE` 记录
- [x] 2.2 `NO_HIT`：连续两条助手消息均为拒答时创建 handoff；验证：同一问题问两次后出现 `NO_HIT` 记录，首次拒答不创建
- [x] 2.3 `MODEL_ERROR`：生成异常分支先置 FAILED 再建 handoff；验证：注入异常后消息 FAILED 且存在 `MODEL_ERROR` 记录
- [x] 2.4 幂等：重复触发不产生第二条未决记录；验证：连问三次高风险问题，未决记录仍为 1 条
- [x] 2.5 测试覆盖三类触发；验证：`pytest -q tests/test_assistant_handoff_triggers.py`

## 3. 前端回答反馈

- [x] 3.1 `ChatPage` 回答气泡加赞/踩图标，状态回显；验证：点击后图标高亮
- [x] 3.2 点踩弹原因选择（4 项）并随反馈提交；验证：选原因后 `message.metadata.feedback.reason` 有值
- [x] 3.3 调 `POST /ai/messages/{id}/feedback`，失败给提示；验证：断网时出现错误提示且不误报成功
- [x] 3.4 前端门禁；验证：`npx tsc --noEmit && npm run build`，首屏 gzip < 260KB

## 4. 收口

- [x] 4.1 契约与全量回归；验证：`export_openapi.py` + `check_frontend_contract.py` problems=0，`pytest -q` 0 failed
- [x] 4.2 更新 `docs/三期/03_三期总结.md` §3 已知限制（删掉已补的三条）；验证：三条限制不再列为未完成
