## Why

CLI-Anything 的 Hub 知识页把另一个应用自己的 `install.py` 排到第 6 位。这个文件的原始相关分只有 5.06，主要靠文件名与需求种子相同获得 55 分额外奖励，挤占了有限的上下文。与此同时，真正定义种子符号的 `repl_skin.py` 仍需要保底。 [Issue #13](https://github.com/zhanglunet/req-code-kb/issues/13)

## What Changes

- 用已有的内容和符号相关分约束仅文件名主干相同的候选，保留对完整文件名或路径的明确引用。
- 重新生成 CLI-Anything Hub 知识页并核对核心文件。
- 用 CLI-Anything 核心页和三条 Click 盲测校验排序与预算。

## Capabilities

### New Capabilities

- `context-ranking`：记录精确文件名奖励的相关性要求和验收场景。

### Modified Capabilities

无，`context-ranking` 是本仓首次归档的能力规格。

## Impact

改动涉及 `reqkb/retrieve.py` 的候选排序、排序回归测试、Hub 知识页及其索引。
