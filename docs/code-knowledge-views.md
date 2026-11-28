# 从代码整理知识页

按使用场景组织主知识页。每页回答谁在什么条件下做什么、会得到什么结果、怎样验证。模块索引帮助读者从文件或符号找到相关场景。业务、产品、开发、测试和运维视图引用同一页的结论与证据，分别突出读者要做的决定。

| 组织方式 | 适合回答的问题 | 用法 |
| --- | --- | --- |
| 场景 | 一个目标如何完成，哪些输入和例外会影响结果 | 主页面，记录目标、前置条件、步骤、结果、例外和依据 |
| 模块 | 想修改某个模块或函数，会影响哪些场景 | 从模块、文件或符号反查场景 |
| 角色 | 我现在该决策、实现、验证或维护什么 | 从场景页引用对应内容和证据，未确认的结论沿用同一个待核状态 |

给每条结论记录适用版本、条件和证据，引用代码时优先使用固定提交的文件行号。历史意图、当前可验证的行为和建议后续做法各用明确的状态词，读者就能判断结论是否可用于当前工作。

## PR 合并后回填需求知识页的样例

**目标。** 需求已经建库，维护者希望知道原先找出的文件覆盖了哪些真实改动，以及下次要补查哪里。用同一份知识页保留预测和实际对照，便于事后复查。 [原需求示例](../examples/click-req-3902.md) · [回流设计](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/docs/mvp-plan.md#L210-L219)

**前置条件。** 需求 ID 能找到已有知识页。准备实际改动清单，或提供目标 Git 仓库、基线和结果提交。Git 模式用 `git diff --name-only base...head`，从共同祖先计算文件改动。CLI 遇到缺少改动来源或没有改动时以退出码 1 结束。 [命令入口](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/cli.py#L162-L180) · [Git 改动提取](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/harvest.py#L36-L42)

**交付物。** `harvest` 计算预测与实际文件的交集和差集，在需求页末尾和 `index.json` 中追加记录。分母是实际改动的唯一文件数，召回用于衡量预测覆盖。重复执行会追加一条记录，原文件清单可继续复查。 [计算口径](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/harvest.py#L23-L33) · [落盘实现](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/harvest.py#L49-L95) · [追加测试](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/tests/test_harvest.py#L39-L79)

**样例结果。** Click #3902 在改动前的提交 `8abb77a8` 生成预测，随后用合并提交 `a46a95c7` 的真实改动回填。交集是 `CHANGES.md`、`src/click/_textwrap.py`、`src/click/formatting.py`、`tests/test_formatting.py`，共 **4/6**。遗漏 `docs/documentation.md` 和 `tests/test_compat.py`。 [Click PR #3902](https://github.com/pallets/click/pull/3902) · [项目验证记录](https://github.com/zhanglunet/req-code-kb/pull/22)

### 从同一场景派生的角色视图

| 角色 | 可以直接使用的信息 | 要采取的动作 |
| --- | --- | --- |
| 业务 | 用法行换行后，带连字符的选项名应保持完整。 | 确认受影响的使用场景。 [Click 原始需求](https://github.com/pallets/click/issues/3362) |
| 产品 | 知识库预测覆盖 4/6 个改动文件，其中遗漏一份文档和一个兼容性测试文件。 | 把文档、兼容性加入下次同类需求的核查清单。 [Click 实际改动](https://github.com/pallets/click/pull/3902/files) |
| 开发 | CLI 提取真实文件清单，回填模块维护交集和差集，并保留原预测。 | 修改范围提取时找命令层和 `changed_files_from_git`，修改结果口径时找 `compare`。 [实现](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/harvest.py#L23-L42) |
| 测试 | 现有测试验证命中、遗漏、多余、Markdown 与 JSON 记录，以及再次回填的追加行为。 | 按测试断言检查两处产物和预测清单。 [回填测试](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/tests/test_harvest.py#L39-L79) |
| 运维 / 知识库维护者 | 回填要求已有需求页和可核对的改动来源。重复运行会新增记录。 | 记录仓库、提交和 PR，核对需求 ID，再检查 Markdown 和 JSON 的新增项。 [命令与写入顺序](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/harvest.py#L49-L95) |

模块索引把每项指回「PR 合并后回填需求知识页」这个场景。`reqkb.cli.cmd_harvest` 选择改动来源和返回结果。`reqkb.harvest.changed_files_from_git` 从提交提取文件。`reqkb.harvest.compare` 计算覆盖，`reqkb.harvest.harvest` 写入回填。 [CLI 入口](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/cli.py#L162-L180) · [回填模块](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/harvest.py#L23-L95)

### 复跑样例

在本仓库根目录运行。使用 Click 的固定提交和临时知识库。

```sh
work=$(mktemp -d)
git clone https://github.com/pallets/click.git "$work/click"
base=8abb77a8432e03ed14a95f972b44f905279415a7
head=a46a95c733d0ed72f63cd2915f2bc4a09a7179f9
git -C "$work/click" checkout --detach "$base"
python -m reqkb build --repo "$work/click" --req examples/click-req-3902.md \
  --kb "$work/kb" --yes
python -m reqkb harvest --kb "$work/kb" --req click-req-3902 \
  --repo "$work/click" --base "$base" --head "$head" --pr 'pallets/click#3902'
```

检查终端的召回结果、`$work/kb/requirements/click-req-3902.md` 的回流段落和 `$work/kb/index.json` 的 `harvest` 条目。检索实现变化后，可用同一对提交对照差异。

## 历史需求的证据规则

先按 #12 的 Markdown 二级标题切分，保留文档路径、源提交、标题路径和行号。切分和匹配用于选择待看的材料。以单条结论为单位判断可用性，同一小节里的历史事实、当时计划、现行规则可以有不同状态。 [小节切分实现](https://github.com/zhanglunet/req-code-kb/blob/3bebfd90099ce9aa934c976d2c4db24e6c2a763e/reqkb/retrieve.py#L38-L55)

| 状态 | 怎么判断 | 怎么写进知识页 |
| --- | --- | --- |
| 可直接引用 | 有可定位的来源，结论的版本和范围明确。当前行为有目标版本的实现或测试佐证，历史意图有当时的工单或批准记录。 | 带条件、范围和出处引用。Click #3362 可直接说明提交者当时报告了什么。 |
| 疑似相关，待确认 | 来源可定位，但版本、适用范围或实施结果不清楚，暂未找到能印证该结论的证据。 | 以待查线索呈现。旧需求写明「续行保留缩进」时，先查目标版本的实际输出或测试，再写入当前行为。 |
| 需人工核验 | 资料互相冲突、关键承诺无法核实，或涉及业务例外、合同约束和权限口径。 | 并列冲突出处和适用版本，交给对应负责人判断。记录确认人、决定和日期，再更新结论。 |

用历史文档确认「当时希望怎样」，用目标版本代码、测试或运行结果确认「当前实际怎样」。代码已经执行的行为和仍有效的业务承诺如果不一致，应保留差异以便产品或业务负责人核对。原文缺失、检测未覆盖和冲突未解决的结论都保留待核状态。
