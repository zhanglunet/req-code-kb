# req-survey-hub

> **方法说明**：本页由 2026-11-26 调研整理（各仓库 README / 架构文档 / 官方文档），非 reqkb build 从代码抽取——build 只解析 Python，这 10 个仓库大多不是 Python，无法用 build 直接建页。借鉴点只借思路：AGPL-3.0（思源、logseq、wiki.js）与自定义协议（dify、AFFiNE）仓库不复用代码。数字只用分析文件里已核实的。

## 需求原文

#11 实战演练的真需求：在 GitHub 找到目前最流行的知识库相关开源仓库，
分析可以借鉴的地方，整理成知识库。短名单 10 个仓库，四类，按 star 数排，
只收一年内有 push 的。深挖时每仓读了 README + 至少一份架构/文档关键页，
从组织、检索、索引、回流、协作五点分析。

## 背景

## 需求

- 给出 10 个仓库的短名单（star 数、语言、许可证、最近 push 实时核实）。
- 给出按价值排序的“最值得借的 10 条”，每条注明对应 issue #12/#13/#14/#15/#16 或新想法，并附来源。
- 给出四组交叉验证的共识，以及未采纳 / 诚实标注。

## 验收标准

- [ ] 10 条借鉴点齐全，条条有对应 issue 或标明新想法
- [ ] 三条共识写明，数字与分析文件一致
- [ ] 诚实标注写明未核实项与不抄的点

## 仓库一览

| 仓库 | star | 语言 | 许可证 | 最近 push | 一句话 |
| --- | --- | --- | --- | --- | --- |
| langgenius/dify | 161,927 | Python | 自定义协议 | 2026-11-26 | Agent 工作流 + RAG 流水线平台 |
| infiniflow/ragflow | 94,734 | Go | Apache-2.0 | 2026-11-26 | Agent 原生 RAG 引擎 |
| toeverything/AFFiNE | 78,602 | TypeScript | 自定义协议 | 2026-11-26 | 块编辑器：文档 + 白板 + 数据库合一 |
| Mintplex-Labs/anything-llm | 68,654 | JavaScript | MIT | 2026-11-24 | 一体化桌面 AI，内置文档知识库 |
| meta/docusaurus | 66,806 | TypeScript | MIT | 2026-11-25 | 开源文档网站生成器 |
| Aider-AI/aider | 50,265 | Python | Apache-2.0 | 2026-05-22 | 终端里的 AI 结对编程 |
| siyuan-note/siyuan | 47,397 | TypeScript | AGPL-3.0 | 2026-11-26 | 隐私优先的块级知识库 |
| logseq/logseq | 45,712 | Clojure | AGPL-3.0 | 2026-11-26 | 大纲式本地知识图谱 |
| requarks/wiki | 29,394 | TypeScript | AGPL-3.0 | 2026-11-23 | Wiki.js，下一代开源 wiki |
| AsyncFuncAI/deepwiki-open | 18,501 | Python | MIT | 2026-11-22 | 给任意仓库自动生成可交互 wiki |

## 借鉴点与对应关系

| # | 借鉴点 | 对应 | 来源 |
| --- | --- | --- | --- |
| 1 | 按标题小节切分索引，块带标题路径 + 起止行号；检索命中子节、问答带父节标题路径与文件:行-行出处 | #12 | ragflow.io《Configure the Chunker Component》Title Chunker；dify Parent-child Chunker；docusaurus `search.mdx`；deepwiki-open `api/rag/pipeline.py`（LineTrackingTextSplitter）；siyuan `docs/SY-FORMAT.md`（块 ID） |
| 2 | 乘性加权 + 频率阻尼取代扁平三档加分：被提及标识符 ×10、长蛇形/驼峰 ×10、下划线开头 ×0.1、在 >5 文件重复定义 ×0.1、引用次数开平方；通用名（如 install.py、utils）机制上就被压住，不用特判 | #13 | aider `aider/repomap.py` → `get_ranked_tags()` 的 `mul`；`aider/website/docs/repomap.md` §Optimizing the map |
| 3 | “疑似相关”单列待确认候选，不悄悄加分：hub 页开“未命中加分规则、但文本/调用提及的候选”区，人工确认后才进正式列表或记一条显式规则 | #13 | logseq `db-version.md` / README（unlinked references）；siyuan README（反链面板） |
| 4 | 三档加分写进页 frontmatter + 一份版本化打分清单（scoring.json，类比 versions.json），quirk 从魔法数字变成清单里可查的一行 | #13 | docusaurus Versioning 页（`versions.json` 清单思想）、`introduction.mdx`（frontmatter）；wiki.js 修改理由进历史 |
| 5 | 知识页以 Markdown 落盘入 git，git diff 当 harvest 对照源；按 release 打版本快照目录，ask 回答注明“基于 vX.Y 快照”；打分、确认记录等元数据另存清单文件，不只放 git 历史里 | #14 + harvest | wiki.js 双向 Git 同步；docusaurus Versioning 页（快照三件套 + `versions.json`） |
| 6 | 制品目录定型为两段式：先出机器可校验的大纲（节 → 页 → 每页源文件、重要度、关联页），解析失败按块正则恢复，再逐页填内容 | #14 | deepwiki-open `api/services/wiki/structure.py`（`_parse_sections`、`_pages_via_regex`、`_normalize_importance`） |
| 7 | 写一份 SY-FORMAT 式的制品契约文档：页结构、块 ID 规则、三档加分语义（各自定义触发条件与反例）、full/lite/vibe 分级定义、harvest 回流格式——争议先查契约，不翻代码 | #14 | siyuan `docs/SY-FORMAT.md`；logseq `CODEBASE_OVERVIEW.md` |
| 8 | harvest 预测加状态机与版本号：每条预测记状态（待验证/已证实/已证伪/已取代）与 build 版本号；旧预测被新版取代记 superseded 而不是删掉；ask 回答附带预测版本，过期预测自动进 review 而不是继续当证据 | 新想法 | siyuan `docs/LONG-TERM-MEMORY.md`（candidate/active/review/disabled/superseded/withdrawn + SHA-256 CAS 版本号 + 源集合指纹）；logseq `CODEBASE_OVERVIEW.md`（outliner op） |
| 9 | 轻量防过时：知识页元数据记 `source_sha + last_verified`，超过 7 天未校验即在输出里标 `stale?`；缓存/制品文件名编码“需求 id + 源 commit + 预算 + 分级”，内容 hash 变化即失效；build 加 `--refresh auto\|manual\|always` 四档 | 新想法 | anything-llm《Automatic document sync》（7 天 stale）；aider `aider/repomap.py`（`CACHE_VERSION`、mtime 校验、cache_key 含全部输入、refresh 四档）；deepwiki-open `api/services/wiki/io.py`（缓存文件名编码 owner/repo/language） |
| 10 | 检索参数逐库可调 + Pinning 关键文件：L1 首页 + L2 分来源页之上再加“每来源一命名空间”（各自的 TopK/阈值/加分档）；允许把 1–2 个“必读文件”钉为全文上下文，不走 TF-IDF 排名 | #16 / 新想法 | dify《Retrieval Settings》（TopK/阈值/混合权重逐数据集）；anything-llm《Using Documents》§RAG settings / Pinning；`workspaceId` 隔离原语 |

### 接近前十、未进总表的三条

- **二分搜索贴合预算**：对排好序的候选集做二分搜索找恰好塞满预算的最大前缀（误差容忍 15%），比“贪心累加到 8000 tokens 就停”更贴合，同样逻辑可用于 ask 的上下文拼装。来源：aider `aider/repomap.py` → `get_ranked_tags_map_uncached()`。
- **摘要层索引**：给每个知识页加一行“一句话摘要”字段（build 时人按 y 确认时顺手写），ask 先对摘要做 TF-IDF、命中再取全文块；同时把 harvest 写成显式规则记进 OpenSpec：“预测所用的页/块变了即 stale，下次 build 前必须重跑 harvest 重算加分，否则沿用旧分”。来源：dify《Knowledge Pipeline Orchestration》§Summary Auto-Gen、Release v1.12.0；ragflow.io《Apply a Knowledge Compilation Template》§Update Knowledge Artifacts。
- **搜索与解析做成可插拔模块接口，默认 TF-IDF / ast 不变**：`ask` 后留极薄的搜索模块接口（`search(query) -> 带出处的结果`），`build` 解析层留解析器接口（`parse(path) -> 调用图`）；#15 的 tree-sitter 多语言接入就只是“给每种语言注册一个解析器”，以后加向量检索也只是再注册一个搜索模块。先只定义接口、不实现第二套引擎。来源：wiki.js 模块化架构（50+ toggleable modules）；docusaurus 插件体系；logseq `deps/graph-parser`（解析器抽成独立库，mldoc 与应用解耦）。

## 共识

- **切分要按节、不要按字符**：四组独立得出同一结论——RAGFlow Title Chunker、Dify Parent-child、Docusaurus 标题段、deepwiki LineTrackingTextSplitter、思源/Logseq/AFFiNE 的块。#12 的修法方向因此最稳。
- **#13 的 quirk 有三种独立解法**：aider 的乘性阻尼（机制压）、logseq 的待确认候选区（流程压）、docusaurus 的 frontmatter + 清单（审计压）。三者可叠加，不互斥。
- **harvest 是 req-code-kb 的差异化优势**：deepwiki 明确没有增量更新与 diff 失效、Docusaurus 没有预测校验闭环、Dify 没有显式过期判定——三家缺的正是 harvest 做的事，值得保留并写进 #14 的制品目录作为固定章节。

## 来源

- 分析文件：`kb-survey-analysis.md`（2026-11-26，四组并行只读调研）
- 短名单文件：`kb-survey-shortlist.md`（2026-11-26，GitHub Search API + /repos 直接查询，PAT 通道）
- 各仓库来源见四张分类页：req-survey-code、req-survey-rag、req-survey-notes、req-survey-docs

## 诚实标注

- aider 的 git 自动提交与 Conventional Commits 留痕不适合直接抄——req-code-kb 的纪律是“人按 y 确认才入库”，自动提交会越过确认闸；只借“提交信息对照 diff 生成”这半句。
- deepwiki 的纯向量检索（FAISS + top_k 20）对 req-code-kb 是降级——已有 ast 调用图 + TF-IDF 且零依赖，引向量库会破零依赖红线；只借行号标注与缓存命名。另提醒：deepwiki-open 英文 README 已改为 Grok-Wiki 2.0 托管版引流，自托管路径的长期维护存在不确定性，借鉴以仓内现存代码（`api/`、`docker-compose.yml`、`charts/`）为准。
- Dify 的 Agent Knowledge Base 图谱引擎在私有仓库 KnowledgeFS，不开源，抄不了实现只能抄接口思想。RAGFlow 1.0.0 刚发、Go 重写，知识编译等新功能 2026-08 才上，尚年轻；且重、须 4 核/16G 起步。
- AFFiNE 服务端检索（Manticore + pgvector）对零依赖的 req-code-kb 不适用，可借的只是“事件驱动增量索引 + 块粒度命中”这个形状。
- 未核实项：Dify 所读文档中未见显式过期判定机制；三仓（dify/ragflow/anything-llm）均未在所读 README/文档中给出可复现的检索精度基准表；RAGFlow 的 `pagerank` 数据集参数（`create_dataset(pagerank=0)`）与 req-code-kb 现有的 PageRank 排序同名，是否同义未在文档中展开说明，不宜直接对标；Wiki.js 3.0 的 Git 分支映射、实时同步细节来自二手深挖文，未在一手代码中逐行核对；Docusaurus 的 DocSearch 记录切分粒度来自其官方爬虫模板的通用设计，`search.mdx` 原文只写到“爬虫聚合全部内容进索引 + sitemap 驱动”，未逐字段展开。以上不影响借鉴点的成立，落到实现时建议以官方模板/代码为准再确认一次。

## 验收

- [ ] 10 条借鉴点齐全，条条有对应 issue 或标明新想法
- [ ] 三条共识写明，数字与分析文件一致
- [ ] 诚实标注写明未核实项与不抄的点
