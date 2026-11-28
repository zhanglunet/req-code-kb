# 验证记录

提案、增量规格、设计和任务在排序实现前建立，并通过 OpenSpec 严格校验。实现过程中用概览知识页验证了明确写出文件扩展名时的行为，随后补齐了这一规格场景。 [Issue #13](https://github.com/zhanglunet/req-code-kb/issues/13)

- 用 CLI-Anything 固定源提交 `34f519533bc175d2fe287ab8316b0dd99bb9cc43` 重建 Hub。前四为 `registry.py`、`installer.py`、`matrix.py`、`cli.py`。原本排第六的应用级 `install.py` 掉出前十。重建结果共 10 个文件，约 7,466 tokens，和入库的 Hub 索引一致。 [CLI-Anything 源提交](https://github.com/HKUDS/CLI-Anything/tree/34f519533bc175d2fe287ab8316b0dd99bb9cc43)
- 同一提交的核心机制上下文保留 `repl_skin.py`、`skill_generator.py` 和 `PREVIEW_PROTOCOL.md`。概览上下文也保留了需求明确点名的 `repl_skin.py`。核心机制、概览和卖点的临时重建都替换了一个 eth2 应用候选，各用 10 个文件，分别约为 8,000、7,758 和 7,979 tokens。
- 排序回归测试和确定性测试通过。三条 Click 盲测均通过，#3896 命中 4/5（7,181 tokens），#3878 命中 2/4（5,405 tokens），#3902 命中 4/6（5,689 tokens）。
