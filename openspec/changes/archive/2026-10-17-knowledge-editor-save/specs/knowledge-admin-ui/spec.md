# Spec Delta

## ADDED Requirements

### Requirement: 编辑器保存新版本

编辑器 SHALL 允许选择一份已有文档、载入其当前版本内容并保存为新版本；保存成功后 MUST 展示新版本号，并提示需提交审核后才可发布。

#### Scenario: 保存后展示新版本号

- **WHEN** 在编辑器中修改内容并点击保存
- **THEN** 页面提示已生成新版本并显示版本号

#### Scenario: 未选择文档时不可保存

- **WHEN** 编辑器尚未选择任何文档
- **THEN** 保存按钮不可用
