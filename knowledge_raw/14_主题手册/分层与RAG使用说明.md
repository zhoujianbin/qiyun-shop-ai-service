---
document_id: KB-HANDBOOK-001
title: 知识分层与 RAG 使用说明
category: retrieval_governance
version: "1.0"
effective_date: "2026-01-01"
owner: 知识管理委员会
status: ACTIVE
---

# 知识分层与 RAG 使用说明

## 为什么不把每篇短文档当成完整知识

短文档适合回答单一问题，例如“R5 Max 电池保修多久”；它不适合回答“购买、安装、首次使用、故障、安全、售后如何串起来”。因此知识库同时保留精确卡片和连续主题手册。

## 召回策略

第一阶段根据产品 ID、业务意图和风险词召回原子卡片；第二阶段读取关联主题手册的相关章节；第三阶段如涉及资格、金额、时限、状态或权限，必须回到 YAML 真源；第四阶段用案例检查回复是否越权。

## 分片建议

主题手册以唯一 H1 作为文档标题，并按 H2 业务章节切分；原子卡片一般作为单个检索单元。不要在句子或判断链中间切断。导入器必须把文档 front matter 传播到每个分片，并额外写入当前 heading_path。主题手册已编码 source_layer、chunk_strategy、product_ids、reference_ids 和 rule_ids；分片还需保留 document_id、title、category、effective_date 与版本。

## 冲突处理

产品规格以产品主档为准，时限金额状态权限以 YAML 为准，主题手册负责解释和串联。主题手册与真源冲突时不能自行折中，应修正文档并重新校验。案例仅展示处理过程，不得用案例推导政策。

## 更新策略

结构化真源变化后，先更新受影响主题手册，再运行 validate_knowledge.py，最后更新校验报告。短卡片不是越短越好；应保持单一意图、可追溯和不重复定义事实。
