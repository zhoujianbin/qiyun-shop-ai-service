# Tasks

## 1. P0 转人工落库

- [x] 1.1 `decision == "HANDOFF"` 时创建 handoff（复用幂等约束）；验证：对话里说"我要转人工"后队列出现记录
- [x] 1.2 e2e 覆盖"对话内转人工 → 队列可见 → 接单 → 客户侧 409"；验证：`pytest -q tests/test_assistant_fix.py -k handoff`

## 2. P1 意图零开销

- [x] 2.1 新增配置 `assistant_use_llm_planner`（默认 False）；验证：`settings.assistant_use_llm_planner is False`
- [x] 2.2 `classify()` 未命中规则时直接返回 KNOWLEDGE，不再调模型；验证：单测断言 `llm.complete` 未被调用
- [x] 2.3 真实首字时延复测；验证：普通知识问题首字 < 1.5s（走查记录）

## 3. P2 别名覆盖

- [x] 3.1 别名表补真实说法（陌生人访问/被偷看/漏电/锁死/异地登录/鼓包等）；验证：YAML 条目数增加且可解析
- [x] 3.2 反向覆盖测试：每条带 `forbid` 的规则 ≥2 条真实问句必须命中；验证：`pytest -q tests/test_assistant_guard_alias.py`

## 4. P3 相关性闸门

- [x] 4.1 实现 `relevance_ok(question, hits)`（2-gram 去停用词，阈值可配）；验证：单测覆盖 4 正例 2 反例
- [x] 4.2 `finalize` 在相关性不足时清空命中并走澄清/拒答，引用为空；验证：火星移民问题引用为 0
- [x] 4.3 回归：门锁/退货/摄像头三个真实问句仍带引用；验证：`pytest -q tests/test_assistant_fix.py`

## 5. 会话延续（走查补充发现）

- [x] 5.1 进入对话页恢复最近一条未结束会话并加载历史消息；验证：刷新页面可见上次对话
- [x] 5.2 新增"新对话"按钮显式开新会话；验证：点击后消息列表清空
- [x] 5.3 关单改为弹窗必填结论（原先点按钮直接提交空结论 → 422 "参数校验失败"）；验证：不填结论时确认按钮禁用

## 6. 收口

- [x] 6.1 全量回归与契约；验证：`pytest -q` 0 failed、`check_frontend_contract.py` problems=0
- [x] 6.2 真实浏览器走查（客户对话页 + 客服工作台）；验证：两个页面的关键路径均可完成
- [x] 6.3 更新 `docs/三期/03_三期总结.md` 已知限制；验证：四条缺陷不再列为未完成
