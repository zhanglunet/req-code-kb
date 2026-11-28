# OpenSpec 制品

`changes/<变更名>/` 放进行中的变更，`changes/archive/` 放已完成的提案、增量规格、设计、任务和验证结果。`specs/<能力>/spec.md` 是归档后同步的现行规格。

1. 用现有需求文档作为提案来源。在 `proposal.md` 记录动机、范围与影响，并链接已有的 `examples/` 需求或 issue。
2. 把可验证的行为写入 `specs/<能力>/spec.md`。在 `design.md` 记录实现取舍和对应的知识页，在 `tasks.md` 列出实现与验收步骤。
3. 完成后勾选任务，在变更目录保留实测或回流记录。用 OpenSpec 校验并归档，由归档命令同步现行规格。

可选的校验命令在仓库根目录运行。OpenSpec CLI 2.2.0 需要 Node.js 22.20 或更新版本。需要检查或归档进行中的变更时，将 `change-id` 替换为其目录名。

```sh
npx --yes @fission-ai/openspec@2.2.0 validate change-id --strict
npx --yes @fission-ai/openspec@2.2.0 archive change-id --yes
npx --yes @fission-ai/openspec@2.2.0 validate --specs --strict
```

首次试点使用实际的 Hub 排序需求。 [#13 归档及验收记录](changes/archive/2026-11-28-cap-exact-filename-bonus/validation.md) · [现行排序规格](specs/context-ranking/spec.md)
