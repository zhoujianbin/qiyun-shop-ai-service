---
document_id: KB-HANDBOOK-SOP-TICKET
title: 工单、SLA、投诉与升级手册
category: service_sop
version: "1.0"
effective_date: "2026-01-01"
owner: 客户体验中心
source_layer: theme_handbook
chunk_strategy: h2
product_ids: []
reference_ids: ["KB-COMPLAINT-001","KB-TICKET-001","KB-TICKET-002","KB-TICKET-003"]
rule_ids: ["ESC-P1-BATCH"]
status: ACTIVE
---

# 工单、SLA、投诉与升级手册

## 一、何时创建工单

无法一次解决、需要其他团队、需要异步查询、存在安全风险或需要保留检测证据时创建工单。工单不是聊天摘要仓库，应包含问题、事实、证据、已做动作、风险等级、负责人和下一节点。

## 二、状态流转

新工单从 NEW 进入 TRIAGED，再分配到 IN_PROGRESS。等待用户或合作方时进入 PENDING_CUSTOMER 或 PENDING_PARTNER；收到回复后恢复处理。完成方案后进入 RESOLVED，确认或关闭窗口结束后进入 CLOSED。重复或无效工单可以 CANCELLED，但必须有原因。

## 三、解决与重开

RESOLVED 必须包含解决摘要、证据和用户下一步。同一问题在 7 日内复发可从 RESOLVED 进入 REOPENED，再重新分配；新问题不应滥用重开。关闭不代表删除记录。

## 四、优先级

P0 首响 5 分钟并立即安全交接；P1 首响 15 分钟、目标 8 小时；P2 首响 2 小时、目标 3 个工作日；P3 首响 4 小时、目标 5 个工作日。暂停计时仅用于明确等待用户或合作方的状态，不能用来掩盖内部延迟。

## 五、投诉处理

先确认诉求与事实，区分服务态度、时效、政策争议、质量争议和安全问题。主管可审核有记录的例外，但不能绕过法定权益、权限或证据要求。补偿、退款和责任认定必须由有权限角色执行。

## 六、升级与交接

P0/P1 按 escalation_matrix.yaml 处理；交接时传递风险、位置、人员状态、设备状态、已采取动作和禁止动作。批量故障按 ESC-P1-BATCH，不向单个用户承诺未经批准的统一补偿。

底层依据：KB-TICKET-001、KB-TICKET-002、KB-TICKET-003、KB-COMPLAINT-001。
