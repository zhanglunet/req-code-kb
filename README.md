# req-code-kb

Requirement-driven code knowledge base: build a **minimal complete
context** KB per requirement, from code, requirement docs and chat
groups. No whole-repo dumping.

做一道菜只备齐这道菜要用的料，不把整个菜市场搬进厨房：一个需求
进来，只给它建最小完备上下文，沉淀成一页“需求知识页”；需求越多，
库越完善；死需求、死代码不用管。

## 快速开始

默认流程只用 Python 标准库（Python 3.10+）：

```bash
# 1. 给一个需求建最小上下文并沉淀成知识页
python -m reqkb build --repo <仓库路径或 URL> --req examples/click-req-3896.md --yes

# 2. 拿新需求问知识库（只检索 + 拼提示词，不调大模型）
python -m reqkb ask --kb kb --q "CliRunner.invoke 怎么传 context 设置？"

# 3. 盲测验收（先按 tests/test_blind.py 准备三个历史版本）
python3 tests/test_blind.py
```

## 目前支持的语言

默认用 Python 的 `ast` 解析 `.py`，并按小节索引 Markdown。需要 JS、Shell
或 SQL 时，安装可选的 Tree-sitter 解析器，再为 `build` 或 `eval` 选择语言。
可以重复使用 `--language`。

```bash
python3 -m pip install -r requirements-treesitter.txt
python3 -m reqkb build --repo <仓库路径或 URL> --req <需求文档.md> --yes \
  --language javascript --language bash --language sql
python3 tests/test_multilang.py
```

| 语言 | 文件 | 索引内容 |
| --- | --- | --- |
| JavaScript | `.js`、`.mjs`、`.cjs` | 函数、类、导入和可静态识别的调用。跳过压缩版 `*.min.*` |
| Bash | `.sh`、`.bash` | 函数、`source` 引用和可静态识别的命令调用 |
| SQL | `.sql` | 语句、表、视图、函数、存储过程和可静态识别的函数调用 |

这些代码文件按语法结构提取候选片段。调用图按语言和名称连接静态调用，
动态派发和 SQL 方言的专有语法可能只能获得部分结果。

## 它怎么做

1. **解析**：Python 用标准库 `ast` 抽取符号和调用。启用其他语言时使用
   Tree-sitter，Markdown 按文本和小节索引。
2. **排序**：调用关系构图 + PageRank（像论文引用一样，越多人
   调用的函数越重要）。思路借鉴 Aider repo map，代码是自己写的。
3. **检索**：需求文档反引号里的标识符当种子 + TF-IDF（FDE 机器人
   同款做法）；1 跳邻居必进，2 跳按 PageRank 筛；默认 8000 tokens
   预算，超了从低往高砍；单文件最多 5 个片段、1200 tokens。
4. **沉淀**：人确认候选清单后才入库（`--yes` 跳过确认）；每页固定
   结构：需求原文、相关文件 / 函数（带 `文件:行号` 链接）、调用链
   Mermaid 图、群消息佐证、验收清单；重叠的文件只存一份，多需求
   共享（见 `kb/index.json` 的 `shared_with`）。
5. **问答**：TF-IDF 取 Top-5 片段带出处，拼成提示词打印出来——MVP
   不内置大模型调用，现场把提示词贴给模型问一句。

飞书群消息是第三路来源：群消息导出成 JSON（`--messages`），只索引
与需求关键词相关的片段，不整群倒灌。`examples/feishu-sample.json`
是虚构的格式样本。

## 盲测验收（已跑通）

盲测使用 pallets/click 的三个已合并 PR。检索时只输入需求描述，并使用
改动前的源码。检索结束后与真实改动文件对照。历史版本的准备命令见
[`tests/test_blind.py`](tests/test_blind.py)，完整运行会报告三个用例。

| 用例 | 输出 | 命中 |
|---|---|---|
| click #3896（给 `CliRunner.invoke` 加 `context_settings`） | 10 个文件，7181 tokens | 4/5，含 `src/click/testing.py` 和 `docs/testing.md` |
| click #3878（`\x04` / `\x1a` 回显为 `^D` / `^Z`） | 10 个文件，5405 tokens | 2/4，含 `src/click/testing.py` |
| click #3902（帮助文本内带连字符的名称保持完整） | 10 个文件，5689 tokens | 4/6，含 `src/click/formatting.py` 和 `src/click/_textwrap.py` |

#3902 将验证范围扩展到帮助文本排版。文件级命中只说明文件进入上下文，
例如命中 `CHANGES.md` 时，改动前的文件还没有该 PR 新增的条目。
详见 [MVP 方案 §10](docs/mvp-plan.md)。

## 为什么不整仓倒进去

- SWE-Explore 基准（2026）：上下文效率与修复成功率的相关系数
  Pearson r = +0.95（arXiv:2606.07297）。
- 微软 FastContext（2026）：最小证据让主 Agent token 最多降 60%、
  解决率最多升 5.5%（arXiv:2606.14066；“最多”是 up-to 口径）。

## 许可证与致谢

本项目 MIT。借鉴与引用见 [ATTRIBUTION.md](ATTRIBUTION.md)：
Aider（Apache-2.0，只借算法思路）、spec-kit（MIT，模板结构）、
deepwiki-open（MIT，产品形态）、RepoGraph（ICLR 2025，k-hop 策略）。
SocratiCode 是 AGPL-3.0，只看了思路，没有抄代码、没有当依赖。

## 已知局限

- 检索是 TF-IDF + 调用图，没有向量 embedding。
- “死需求”的判定只做到“90 天零引用标疑似沉寂”，删不删由人定。
