---
document_id: KB-CASE-MT-003
title: 订单部分发货后申请取消多轮案例
category: multi_turn_case
version: "1.0"
effective_date: "2026-01-01"
owner: 客户体验中心
source_layer: theme_handbook
chunk_strategy: h2
product_ids: []
reference_ids: ["KB-HANDBOOK-COMMERCE","KB-ORDER-001","KB-SHIP-002"]
rule_ids: ["ADDRESS-CHANGE-AFTER-SHIP","REFUND-MERCHANT-PROCESS-3BD"]
status: ACTIVE
---

# 订单部分发货后申请取消多轮案例

## 场景目标

验证客服区分订单、支付、履约和退款状态，并对不同商品分别处理。

## 对话过程

**用户：** 订单只发了一件，我想把整个订单取消。

**客服：** 我先查询订单中的商品、包裹和未发货状态。请在账户内选择该订单进行授权查询，不需要提供支付密码或验证码。

**用户：** 已授权。

**客服：** 订单已支付，其中摄像头已发货，网关仍在备货。未发的网关可以申请仓库拦截；已发的摄像头只能申请物流拦截，结果不保证。如果拦截失败，需要签收后按退货资格处理。是否先提交网关取消和摄像头物流拦截？

**用户：** 可以，退款什么时候到账？

**客服：** 退款要等各自取消或退货被接受后才会发出。商家接受后 3 个工作日内提交退款指令；钱包通常 1-3 日、银行卡通常 3-7 日，实际以支付机构为准。现在执行两个动作会影响两个商品，请再次确认。

**用户：** 确认。

**客服：** 已分别提交仓库拦截和物流拦截，当前都只是“请求已提交”，不是“已取消”。我已创建跟踪工单，下一次更新会分别说明两个商品的结果。

## 状态记录

订单可能为 PARTIALLY_SHIPPED，履约为 PARTIAL，支付仍为 PAID，退款最初为 NONE。提交请求后不能提前写成 CANCELLED 或 REFUNDED。

## 错误回复示例

“已经帮您整单取消，退款马上到账。”同时混淆四个状态域并作绝对承诺。

## 复盘

部分发货必须拆商品处理。依据：KB-ORDER-001、KB-SHIP-002、KB-HANDBOOK-COMMERCE；规则：ADDRESS-CHANGE-AFTER-SHIP、REFUND-MERCHANT-PROCESS-3BD。
