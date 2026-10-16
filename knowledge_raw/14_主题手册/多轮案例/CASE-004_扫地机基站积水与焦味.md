---
document_id: KB-CASE-MT-004
title: 扫地机基站积水与焦味多轮案例
category: multi_turn_case
version: "1.0"
effective_date: "2026-01-01"
owner: 客户体验中心
source_layer: theme_handbook
chunk_strategy: h2
product_ids: ["QR-R5M"]
reference_ids: ["KB-MANUAL-QRR5M","KB-PROD-QRR5M-TROUBLE","KB-SAFE-006"]
rule_ids: ["ESC-P0-ELECTRICAL","ESC-P1-DEVICE-THERMAL"]
status: ACTIVE
---

# 扫地机基站积水与焦味多轮案例

## 场景目标

验证客服区分带电积水 P0 与干燥环境轻微发热 P1。产品为 QR-R5M。

## 对话过程

**用户：** 基站漏水，还有一股焦味，我现在能拔插头吗？

**客服：** 先不要靠近或触碰基站、插头、插座、线缆和积水。请告诉我：地面、插头或插座是否潮湿，是否有烟雾、火花、触电感或电池起火？

**用户：** 插座旁边有水，没有烟和火花。

**客服：** 水已靠近带电设备，按 P0 电气风险处理。请让人员和宠物远离。如果配电箱位于完全干燥且可安全接近的位置，可从配电箱隔离对应回路；否则不要自行操作，联系物业、专业电工或消防。不要拔插头，也不要再次通电验证。

**用户：** 已经从配电箱断电了。接下来怎么处理？

**客服：** 请继续不要接触积水中的设备，等待专业人员确认无电和现场安全。我会创建 P0 安全工单并通知安全团队。设备后续检测前不得充电或开机。

## 分支说明

如果环境完全干燥、无烟无火，只是轻微异常发热或无可见火情的焦味，则停止使用并按 ESC-P1-DEVICE-THERMAL；本案例因水靠近带电设备直接命中 ESC-P0-ELECTRICAL。

## 错误回复示例

“先拔下插头再擦干。”错误原因：人员可能需要接近潮湿插座，存在触电风险。

## 复盘

客服先问环境状态，再判断优先级。依据：KB-PROD-QRR5M-TROUBLE、KB-SAFE-006、KB-MANUAL-QRR5M；规则：ESC-P0-ELECTRICAL。
