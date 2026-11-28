# 大仓建库性能调查与原子知识库设计

[#19](https://github.com/zhanglunet/req-code-kb/issues/19) 的工作坊反馈未提供仓库、版本、命令或日志。本报告用固定版本的 CLI-Anything 测量真实建库，用合成仓库单独验证同名调用带来的开销。两组实验均在本地完成。原始超时的触发条件仍未知。

## 性能定位

基线为 req-code-kb `3bebfd9`，Linux x86-64、Python 3.12.14，AMD EPYC 9V74 云实例，CPU 配额 4 核。使用 `full` 和默认预算，同进程运行三次，取各列的墙钟时间中位数。每次重新解析源码并写入一个空的临时知识库。检索列包括 TF-IDF 索引和评分、调用图、PageRank、上下文裁剪。计时范围从扫描本地源码开始，到 Markdown 和索引 JSON 写完。网络克隆、手动确认及已有大索引的更新开销在本次测量范围之外。

| 用例 | 索引文件 / 符号 | 解析（秒） | 检索（秒） | 渲染（秒） | 写盘（秒） | 总计（秒） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CLI-Anything `34f5195`，`req-hub` | 1,708 / 18,075 | 2.874 | 6.165 | 0.000348 | 0.000566 | 9.011 |
| 合成，256 个唯一目标 | 512 / 512 | 0.013 | 0.014 | 0.000037 | 0.000377 | 0.028 |
| 合成，256 个同名目标 | 512 / 512 | 0.014 | 0.090 | 0.000051 | 0.000429 | 0.104 |
| 合成，1,024 个唯一目标 | 2,048 / 2,048 | 0.055 | 0.061 | 0.000040 | 0.000308 | 0.116 |
| 合成，1,024 个同名目标 | 2,048 / 2,048 | 0.054 | 1.188 | 0.000079 | 0.001035 | 1.243 |

- **真实仓库主要耗时在检索，其次是解析。** CLI-Anything 三次均生成 10 个文件、约 7,450 tokens。独立的 `cProfile` 运行显示 `tokenize` 的累计时间为 10.75 秒，`TfIdfIndex.__init__` 为 6.32 秒，`chunk_cosine` 为 5.57 秒。计数包含嵌套调用，剖析用时只用于定位。索引整篇文本后，行窗口评分又对同一文件的窗口分词，另一次需求构建会重复这些工作。
- **同名调用可以让图处理成为瓶颈。** 在每组有 N 个定义和 N 个调用的实验中，唯一命名生成 N 条边。当前的同文件优先、跨文件按短名回退规则让同名组生成 N² 条边。在同样 2,048 个文件下，验证了唯一组的 1,024 条边和同名组的 1,048,576 条边，检索从 0.061 秒增加到 1.188 秒，约 19 倍。独立剖析中 `pagerank` 为 1.72 秒，两次 `reverse_edges` 共 1.09 秒，明显高于评分。
- **当前构建完全在本地运行。** 解析、检索、渲染、落盘四个阶段没有模型请求。工作坊原始工具和运行条件未知，因此无法判断当时的模型响应是否参与。下次复现应记录目标仓库和提交、命令、源码文件及符号数、图边数和阶段耗时，并记录当时的输出或错误。

### 复现

从 req-code-kb 仓库根目录运行，保留固定输入以便比较。下载 CLI-Anything 仅发生在准备阶段。

```bash
work=$(mktemp -d)
mkdir -p "$work/reqkb" "$work/cli"
git archive 3bebfd9 | tar -xf - -C "$work/reqkb"
mkdir -p "$work/reqkb/tools"
cp tools/benchmark_build.py "$work/reqkb/tools/"

git init -q "$work/cli-git"
git -C "$work/cli-git" fetch -q --depth=1 https://github.com/HKUDS/CLI-Anything.git \
    34f519533bc175d2fe287ab8316b0dd99bb9cc43
git -C "$work/cli-git" archive FETCH_HEAD | tar -xf - -C "$work/cli"

python3 - "$work/reqkb/site/kb-cli-anything/requirements/req-hub.md" "$work/req-hub.md" <<'PY'
from pathlib import Path
import sys

page = Path(sys.argv[1]).read_text(encoding="utf-8")
body = page.split("## 需求原文\n\n", 1)[1].split("\n\n来源：", 1)[0]
Path(sys.argv[2]).write_text(f"# req-hub\n\n{body}\n", encoding="utf-8")
PY

PYTHONHASHSEED=0 python3 "$work/reqkb/tools/benchmark_build.py" \
    --repo "$work/cli" --req "$work/req-hub.md"
PYTHONHASHSEED=0 python3 -m cProfile -s cumulative "$work/reqkb/tools/benchmark_build.py" \
    --repo "$work/cli" --req "$work/req-hub.md" --repeat 1
```

合成对照只改变跨文件调用的目标名称。继续在同一 shell 中运行。

```bash
python3 - "$work" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
(root / "req.md").write_text("Trace the implementation of `entrypoint`.\n", encoding="utf-8")
for size in (256, 1024):
    for shape in ("unique", "duplicate"):
        source = root / f"{shape}-{size}"
        (source / "definitions").mkdir(parents=True)
        (source / "callers").mkdir()
        for index in range(size):
            definition = "worker" if shape == "duplicate" else f"worker_{index}"
            caller = "entrypoint" if index == 0 else f"caller_{index}"
            (source / "definitions" / f"def_{index}.py").write_text(
                f"def {definition}():\n    return {index}\n", encoding="utf-8"
            )
            (source / "callers" / f"call_{index}.py").write_text(
                f"def {caller}():\n    return {definition}()\n", encoding="utf-8"
            )
PY

for repo in "$work"/unique-* "$work"/duplicate-*; do
    printf '%s\n' "$repo"
    PYTHONHASHSEED=0 python3 "$work/reqkb/tools/benchmark_build.py" \
        --repo "$repo" --req "$work/req.md"
done
PYTHONHASHSEED=0 python3 -m cProfile -s cumulative "$work/reqkb/tools/benchmark_build.py" \
    --repo "$work/duplicate-1024" --req "$work/req.md" --repeat 1
```

## 原子知识库设计草案

候选方案是在按需求生成知识页前复用源码解析和文本索引，增加一个带证据的能力查询视图。全仓原子索引保存出处和结构。每个需求选取预算内的证据生成知识页，并用回流记录核对实际改动。

| 类型 | 最小单元 | 字段和来源 |
| --- | --- | --- |
| 实现 | 函数、类、方法、独立脚本入口 | 语言、限定名、签名、提交、路径、行区间、调用和导入，来自解析器 |
| 数据与接口 | API、命令、表、事件或配置合同 | 名称、输入输出、约束、关联实现与测试引用，来自源码、模式文件及测试 |
| 约束与说明 | 文档小节或需求验收条目 | 小节标题、行区间、文档版本、证据状态及已匹配的实现，来自 Markdown 或需求 |
| 验证 | 可执行测试用例或可核对的验收记录 | 检查对象、用例路径、运行时版本和已观测结果，来自测试、盲测或回流 |

能力地图按用户意图组织。一个能力可以同时引用上述几种原子，保留入口、实现和证据关系。比如“记录合并后的真实改动”关联 `reqkb harvest` 入口、`changed_files_from_git` 和 `harvest` 实现、`tests/test_harvest.py` 测试，以及方案里的回流约定。查询先返回少量匹配能力、摘要、入口和验证覆盖。调用方选择能力后，用其 ID、提交、token 预算以及允许的关系深度请求具体证据。每个结果带可回到该提交的源位置、缺失项和解析状态。调用目标有歧义时返回待确认的限定名候选，避免为所有远端同名定义物化边。

**完整性口径。** 每个快照记录被纳入的根路径、提交和解析器版本，以及已扫描、已成功、出错、忽略或不支持的文件数和原因。每个原子的源位置应在当前版本可定位，删除后不得被检索命中。能力标为已验证前，入口和实现需要有确定的来源，验证需有测试或人审核的记录。缺失字段和无法解析的调用显式记为未知。历史需求可用作查找线索，和当前实现不一致或缺少证据的说明进入待核队列。部分快照保留缺失信息，供调用方识别覆盖边界。

**增量更新。** 快照以仓库和提交为范围。清单记录路径、文件内容 SHA-256、解析器及索引格式版本。内容和解析版本未变时直接复用原子和词频。变更文件重新解析，删除和重命名同步处理旧路径及反向引用。依赖解析单独使用当前模块路径和导入关系。更新已变更或受其影响的关系以及词项文档频率，对能力摘要和验证状态标记待刷新。图发生变化时重新计算全局 PageRank，验证增量算法等价后再替换全量排序。新版清单和索引在同一事务内发布。失败时保留上一个查询快照。首版可用标准库 SQLite 来存每个快照的文件清单、原子和关系，以便通过事务完成更新。

**校核与验收。** 模型可以提出能力描述和证据映射，源码解析结果、测试输出和人工审核负责确认。先选覆盖多个模块的真实问题，检查能否在现有预算内找到正确入口、实现和测试，并用 `harvest` 记录遗漏。给定同一目标提交，增量和全量重建应生成一致的可查询原子、已解析关系和出处。对新增、编辑、重命名、删除以及源码无法解析的提交逐一比较，并保留现有盲测作为回归基线。性能上分别汇报首次构建与单文件更新耗时、解析文件数及图边数。可先验证分词和解析结果复用，再针对重名调用控制候选边。此草案给出验证路径，结构化索引和增量缓存尚未实现。
