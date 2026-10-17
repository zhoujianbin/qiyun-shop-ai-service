# knowledge-ingestion Specification

## Purpose
让企业知识素材以可追溯、可重放、可观测的方式进入系统，并加工成可被检索消费的切片与向量；导入失败按文件隔离，重复导入不产生新版本。

## Requirements

### Requirement: 文档导入支持三种文本格式

系统 SHALL 接受 Markdown、纯文本与 DOCX 三种格式的文档导入，单文件不得超过 20MB；超限、空文件、扩展名与内容不匹配的文件 MUST 被拒绝并返回可识别的错误码与 `request_id`。

#### Scenario: 批量导入 Markdown

- **WHEN** 用户在一次请求中上传 158 个 `.md` 文件
- **THEN** 系统为每个文件建立文档与草稿版本，并返回导入任务编号

#### Scenario: 超限文件被拒

- **WHEN** 用户上传一个 25MB 的文件
- **THEN** 系统返回 422，错误体含 `code` 与 `request_id`，且不产生任何文档

#### Scenario: 扩展名与内容不符

- **WHEN** 可执行文件被改名为 `.docx` 后上传
- **THEN** 系统拒绝该文件并记为解析失败

### Requirement: 导入按内容去重

系统 SHALL 以文件内容的 sha256 作为去重依据；同一内容重复导入 MUST 不产生新的文档或版本，并计入本次任务的跳过数。

#### Scenario: 重复导入

- **WHEN** 同一批文件被第二次导入
- **THEN** 文档总数不变，导入任务的跳过数大于零

### Requirement: 导入幂等

导入接口 SHALL 接受 `Idempotency-Key`；携带相同键的重复请求 MUST 返回同一个导入任务，不得重复处理文件。

#### Scenario: 同键重试

- **WHEN** 使用同一 `Idempotency-Key` 再次提交同一批文件
- **THEN** 返回与首次相同的任务编号

### Requirement: 导入失败按文件隔离

单个文件解析失败 MUST NOT 阻塞同批其他文件；失败文件的名称、原因与位置 SHALL 记入任务错误清单。

#### Scenario: 混入损坏文件

- **WHEN** 一批文件中混入一个损坏的 DOCX
- **THEN** 其余文件成功入库，错误清单包含该文件名与失败原因

### Requirement: 导入任务结果可查

导入任务 SHALL 暴露总数、成功数、失败数、跳过数与错误清单五项，供人核对本次导入规模。

#### Scenario: 查询任务结果

- **WHEN** 用户查询导入任务
- **THEN** 返回五项字段，且总数等于本次提交的文件数

### Requirement: front matter 元数据解析

系统 SHALL 解析文档 front matter 中的 `document_id`、`title`、`category`、`owner`、`version`、`effective_date`、`status`；缺失必填项的文件 MUST 判为解析失败。

#### Scenario: 完整 front matter

- **WHEN** 导入一篇带完整 front matter 的文档
- **THEN** 入库后的文档标识、标题、类目、责任人与原文一致

#### Scenario: 缺失必填项

- **WHEN** 文档 front matter 缺少 `document_id`
- **THEN** 该文件进入错误清单且不入库

### Requirement: 结构化规则 YAML 专用通道

系统 SHALL 仅接受政策数值型、保修型、升级矩阵型三类规则 YAML；其他形态 MUST 被拒绝并说明"该形态不纳管"的原因。

#### Scenario: 三类规则导入

- **WHEN** 导入政策、保修、升级三个 YAML 文件
- **THEN** 共 24 条规则入库，来源类型分别为政策、保修、升级

#### Scenario: 未纳管形态被拒

- **WHEN** 导入意图分类 YAML
- **THEN** 系统返回 400，且说明该形态不在纳管范围

### Requirement: 切片按标题层级生成

系统 SHALL 按 Markdown 标题层级切分，单片长度 MUST 控制在 200 至 600 字符之间，超长内容按段落二次切分；每片 SHALL 保留标题路径。

#### Scenario: 标题路径与长度

- **WHEN** 抽查任意切片
- **THEN** 其标题路径形如「一级 / 二级」，且字符数不超过 600

### Requirement: 切片可回指原文

每个切片 SHALL 记录原文起始行号与结束行号，使任意命中都能定位到原文位置。

#### Scenario: 行号一致

- **WHEN** 按切片记录的起止行号回读原文
- **THEN** 读到的内容与切片内容一致

### Requirement: 向量化异步且状态可观测

切片 SHALL 先以待处理状态落库，再由后台任务补齐向量并置为就绪；失败 MUST 置为失败状态且可重试，检索 MUST 只使用就绪状态的切片。

#### Scenario: 导入后待处理

- **WHEN** 导入完成后立即查询切片
- **THEN** 向量化状态为待处理

#### Scenario: 后台补齐

- **WHEN** 后台任务执行一轮
- **THEN** 切片状态变为就绪

#### Scenario: 失败可重试

- **WHEN** 向量化过程发生异常
- **THEN** 该切片置为失败，重试后变为就绪

### Requirement: 向量契约

切片向量 MUST 为 512 维且已完成归一化；查询侧向量 SHALL 与切片侧使用同一模型与同一维度。

#### Scenario: 维度与模长

- **WHEN** 抽查任一就绪切片
- **THEN** 向量维度为 512，模长为 1

### Requirement: 向量可重算

系统 SHALL 提供分批重算能力；重算过程中断后 MUST 能继续，且不得遗漏或重复处理切片。

#### Scenario: 断点续跑

- **WHEN** 重算在批次之间被中断后重新启动
- **THEN** 已完成批次不再重复处理，最终全部切片为就绪

### Requirement: 原文校验可复现

导入前置校验 SHALL 对知识素材目录给出与既有独立校验器一致的结论，包括元数据完整性与规则标识引用完整性。

#### Scenario: 引用悬空检查

- **WHEN** 对知识素材目录执行校验
- **THEN** 悬空的规则标识引用数为 0
