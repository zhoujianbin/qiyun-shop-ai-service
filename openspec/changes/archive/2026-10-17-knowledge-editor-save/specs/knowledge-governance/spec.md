# Spec Delta

## ADDED Requirements

### Requirement: 手动新建版本

后台 SHALL 支持直接以 Markdown 文本为指定文档新建草稿版本；版本号 MUST 为该文档当前最大值加一，内容 MUST 重新切片并进入待向量化状态，且 SHALL 写入审计。

#### Scenario: 新建版本后版本号递增

- **WHEN** 对已有 v1 版本的文档提交新内容
- **THEN** 生成 v2 草稿版本，且原有 v1 保持不变

#### Scenario: 新版本重新切片

- **WHEN** 新建版本成功
- **THEN** 该版本下的切片全部为新生成的待处理切片，向量化状态为待处理

#### Scenario: 文档不存在

- **WHEN** 对不存在的文档新建版本
- **THEN** 返回 404

#### Scenario: 缺少写权限

- **WHEN** 只读身份调用新建版本接口
- **THEN** 返回 403
