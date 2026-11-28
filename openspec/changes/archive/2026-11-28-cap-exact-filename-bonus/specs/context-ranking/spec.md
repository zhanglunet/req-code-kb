## Purpose

按需求相关性组织候选文件，在上下文预算内保留支撑实现的核心代码和文档。
让精确文件名提供定位线索，并根据内容和符号证据控制它在排序中的权重。

## ADDED Requirements

### Requirement: Exact filename bonus requires relevant evidence

对于只凭文件名主干与需求种子精确同名且符合奖励条件的候选文件，系统 SHALL 将额外排序奖励限制为 `min(55, 10 × max(0, 原始相关分 − 5))`。减去的 5 分是原有的文件名匹配分。需求在行内代码中明确写出文件名及其扩展名，或写出仓库相对路径时，符合条件的文件 SHALL 保留 55 分额外奖励。

#### Scenario: Matching basename with little supporting content

- **WHEN** 文件名与需求种子精确匹配且原始相关分为 5.06
- **THEN** 精确文件名额外奖励约为 0.6 分

#### Scenario: Matching basename with relevant symbol evidence

- **WHEN** 文件名与需求种子精确匹配且原始相关分达到 10.5
- **THEN** 该文件仍可获得 55 分额外奖励

#### Scenario: Explicit filename with an extension

- **WHEN** 需求在行内代码中明确写出 `repl_skin.py`
- **THEN** 对应候选保留完整的 55 分精确文件名额外奖励

### Requirement: Rank changes stay within the context budget

系统 SHALL 在现有文件数和 token 预算内应用奖励上限，并保留定义种子符号与前缀匹配的既有奖励。

#### Scenario: Rebuild the pinned CLI-Anything Hub context

- **WHEN** 用保存的 Hub 需求和固定的 CLI-Anything 源提交构建完整上下文
- **THEN** registry、installer、matrix 三份核心文件均进入前四
- **AND** 完整上下文最多包含 10 个文件和 8,000 个估算 tokens

#### Scenario: Validate supported retrieval behavior

- **WHEN** 以同一固定源提交验证 CLI-Anything 核心机制及概览上下文，并运行三条 Click 盲测
- **THEN** 核心机制及概览上下文均包含插件的 `repl_skin.py`
- **AND** 三条 Click 盲测达到各自的命中和预算要求
