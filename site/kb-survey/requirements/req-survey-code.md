# req-survey-code

> **方法说明**：本页由 2026-11-26 调研整理（各仓库 README / 架构文档 / 源码关键文件），非 reqkb build 从代码抽取——build 只解析 Python，这两仓虽是 Python，但本页是跨仓借鉴分析，不是对单一仓库做 build。借鉴点只借思路，代码不直接复用。数字只用分析文件里已核实的。

## 需求原文

## 背景

#11 实战演练：找 GitHub 上最流行的知识库相关开源仓库，分析可借鉴之处。
本页是代码知识库类：aider（repo map 的源头，req-code-kb 借鉴的正是这套骨架）、
deepwiki-open（与 req-code-kb“知识页”形态最接近的参照）。

## 需求

- 说清两仓的组织、检索、索引、回流、协作五点。
- 给出对 req-code-kb 具体可借鉴的点，每条注明对应 issue 或新想法，并附来源。

## 验收标准

- [ ] 两仓五点齐全，借鉴点至少 3 条，条条有对应 issue 或标明新想法
- [ ] 数字与分析文件、短名单文件一致

## 仓库一览

| 仓库 | star | 语言 | 许可证 | 最近 push | 一句话 |
| --- | --- | --- | --- | --- | --- |
| Aider-AI/aider | 50,265 | Python | Apache-2.0 | 2026-05-22 | 终端里的 AI 结对编程 |
| AsyncFuncAI/deepwiki-open | 18,501 | Python + Next.js | MIT | 2026-11-22 | 给任意仓库自动生成可交互 wiki |

## 内容

### Aider-AI/aider

- **组织单位**：没有持久化的“知识页”。组织单位是即时生成的 repo map：`文件 → 该文件内排过序的符号（类/函数/变量定义，只含签名与关键行，不含实现体）`，外加当前对话文件。另有两份留痕物：每次改动自动产生的 git commit，以及 `.aider.chat.history.md` 会话记录。知识是“每次请求现算的地图”，不是入库的文档。
- **检索**：图检索，无向量。`aider/repomap.py: get_ranked_tags()`：tree-sitter 按语言解析每个文件，用 `queries/<lang>-tags.scm` 抽出两类 tag：`name.definition.*`（def）和 `name.reference.*`（ref）；只有 def 没有 ref 的语言用 pygments 词法 token 回填 ref。建 NetworkX `MultiDiGraph`：节点是文件，边是“引用者文件 → 定义者文件”，无引用的定义加一条权重 0.1 的自环以便参与排序。跑个性化 PageRank，personalization 来自三处：chat 中的文件、被提及的文件名、被提及的标识符（路径分量命中也算）。排完序把文件级 rank 沿出边权重再分配到 `(文件, 标识符)` 上，得到 ranked definitions；LLM 还能凭地图反向索要完整文件——地图是导航层，全文是深挖层。
- **索引与切分**：逐文件 tree-sitter 解析，tag 结果缓存在仓库根目录的 `.aider.tags.cache.v<CACHE_VERSION>`（diskcache/SQLite，当前 v4，格式一变就升版号），key 是文件名、凭 mtime 判定失效；SQLite 出错时删缓存重建，仍失败则退化为内存 dict。另有 `map_cache`，key 是（chat 文件、其他文件、token 预算、提及内容），`refresh` 分 auto/manual/always/files 四档。切分/预算：不是按字符切块，而是按“排好序的 tag 列表”取前缀，再用二分搜索找恰好塞满预算的最大前缀（`get_ranked_tags_map_uncached`，误差容忍 15%）。默认 `--map-tokens 1024`；对话里没文件时预算自动放大 `map_mul_no_files=8` 倍，并受 `max_context_window - 4096` 封顶。渲染时只取定义所在关键行（grep_ast `TreeContext`），每行截断到 100 字符。排序前的加权细节（`get_ranked_tags` 的 `mul`）：被提及的标识符 ×10；含 `_`/`-`/大小写混合且长度 ≥8 的标识符 ×10；下划线开头 ×0.1；在 >5 个文件里都有定义的标识符 ×0.1；引用者是 chat 文件 ×50；引用次数开平方（防高频词垄断）。另用 `filter_important_files` 把重要文件（如 README/配置）钉在地图最前面。
- **回流/防过时**：mtime 缓存失效 + 每次请求重算 map；`refresh` 可强制每次重算。改动留痕（强项）：与 git 深度绑定——每次改文件自动提交，提交信息由弱模型按 Conventional Commits 规范对照 diff 与对话历史生成；改前先把用户未提交的脏文件单独提交一次（防 AI 改动覆盖用户工作）；commit 的 author/committer 名后附 `(aider)` 标记作者身份（可关）；`/undo` 一键撤销上次改动，`/diff` 看自上条消息以来的改动。改完自动跑 lint 与测试，报错就自动修。没有 harvest 式“预测 vs 真实改动”对照回流：它的闭环是 lint/test + git 历史，不是预测准确率统计。
- **协作与版本化**：单人 CLI 工具，无多用户概念。协作 = 走正常 git（分支、PR、review）；版本化 = git 提交本身。配置四种等价写法：命令行开关、家目录或仓库根的 `.aider.conf.yml`、环境变量 `AIDER_xxx`、`.env` 文件。语言支持 100+ 种（tree-sitter 语言包 + tags.scm 查询文件）。

### AsyncFuncAI/deepwiki-open

- **组织单位**：两级大纲 + 页，Pydantic 模型（`api/schemas.py` 的 `WikiStructureModel`）：`WikiSection → WikiPage`。每页含 `id`、`title`、`content`、`filePaths`（支撑该页的源文件）、`importance`（high/medium/low 三档）、`relatedPages`。另有两类组织单位：codemap（代码导览：按“怎么做 X”的问题生成分节、分步、带引用与 Mermaid 图的引导式教程）和 Ask / DeepResearch（问答与最多 5 轮迭代的多轮研究）。注意：英文 README 现已缩减为 Grok-Wiki 2.0 的引流 stub，完整功能说明以 `README.zh.md` 为准——项目重心正在转向托管版，自托管代码仍在仓内（Dockerfile、docker-compose、Helm chart 都在）。
- **检索**：纯向量检索，无 BM25/混合。`api/rag/rag.py`：adalflow 的 `FAISSRetriever`，`embedder.json` 里 `retriever.top_k = 20`。问答时把 top-k chunk 按文件分组、标注行号范围拼成上下文，配 `RAG_SYSTEM_PROMPT`/`RAG_TEMPLATE`（`api/prompts.py`）。对话历史用自写的 `CustomConversation`/`DialogTurn` 等 dataclass 维护。图关系不存在于数据库里，只存在于渲染出的 Mermaid 图中。
- **索引与切分**：流水线在 `api/rag/pipeline.py`，`DatabaseManager.prepare_database()`：① 克隆：`Repo.download()`，支持 GitHub/GitLab/BitBucket，私有仓用 PAT；落盘 `~/.adalflow/repos/{owner}_{repo}`。② 读文件：`read_all_documents()` 按 `api/config.py: iterate_files()` 的 include/exclude 走一遍（树列举与索引共用同一套过滤实现，避免两边口径漂移）。每文件产一个 `Document`，元数据含 `file_path`、`type`、`is_code`、`is_implementation`（非 test 文件才算实现）、`token_count`。超大文件（> 8192×10 tokens）直接跳过并记 warning。③ 切分：`LineTrackingTextSplitter`（继承 adalflow `TextSplitter`），`api/config/embedder.json`：`split_by: word`、`chunk_size: 350`、`chunk_overlap: 100`。关键设计：每个 chunk 单独复制一份 meta_data，并用顺序子串搜索反算出该 chunk 在原文中的起止行号（`start_line`/`end_line`），所以引用能精确到行。④ 向量化：`ToEmbeddings`，默认 OpenAI `text-embedding-3-small`（256 维），备选 Ollama（`nomic-embed-text`）、Google（`gemini-embedding-001`）、Bedrock（Titan v2），batch 500；embedding 上限 `MAX_EMBEDDING_TOKENS = 8192`。⑤ 存盘：adalflow `LocalDB` 序列化为 `~/.adalflow/databases/{owner}_{repo}.pkl`。过滤清单（`api/config/repo.json`）：excluded_dirs 含 `.venv`、`node_modules`、`__pycache__`、`dist`、`build`、`docs`、`_site`、`.idea`、`.vscode`、`logs` 等 30+ 项；excluded_files 含各类 lock 文件、`.env*`、压缩包、二进制、`.pyc`、`.min.js` 等上百条 pattern；`code_extensions` 列了 16 种代码后缀。Wiki 生成流程：先读文件树 + README（`structure.py: read_repo_file_tree`，默认分支用 `git rev-parse --abbrev-ref HEAD` 探测，失败则默认为 main）→ LLM 一次调用返回 XML 大纲（section/page、file_path、importance、related），解析失败时有正则兜底（`_pages_via_regex`/`_sections_via_regex`，按 `<page>…</page>` 块逐个恢复）→ 再逐页用 RAG 填充内容 → 生成 Mermaid 架构图 → `content.py` 做引用后处理：把模型输出的 `[path:行]()` 空括号引用转成真实仓库链接（GitHub `/blob/<branch>/<path>#Lx-Ly`，GitLab/BitBucket 各有格式），并规整 "Relevant source files" 的 `<details>` 块。Codemap 流程（`api/services/codemap.py`）：两段 LLM 调用——skeleton（分析代码，产出带引用的大纲 JSON，解析失败最多重试 3 次，含修 trailing comma 等轻量 JSON 修复）→ enrich（逐节补 prose 指南与 Mermaid 图），以 NDJSON 事件流式推送三阶段进度（analyzing → initial codemap → diagrams/guides）。
- **回流/防过时**：弱，这是它的短板。Wiki 生成结果以 JSON 缓存在 `~/.adalflow/wikicache/deepwiki_cache_{repo_type}_{owner}_{repo}_{language}.json`（`api/services/wiki/io.py`），有读/写/删/列四种操作；向量库若已存在且含非空 embedding 就直接加载，否则重建（embedding 全空时记 warning 并重建）。但没有增量更新、没有基于 git diff 的失效判定、没有版本比对——仓库变了，缓存不会自动失效，靠用户手动删缓存或点重新生成。没有任何“预测 vs 实际”回流。
- **协作与版本化**：无内置多用户/权限体系，只有一个共享授权码（`DEEPWIKI_AUTH_MODE=true` 要求输入授权码才能生成；外部文章指出须放反向代理后加公司登录才有角色权限，角色功能在 OpenDeepWiki 分支）。私有仓访问靠用户填 PAT。配置全走 `.env`（`GOOGLE_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` 等）+ `api/config/*.json`；自托管三件套：`docker-compose.yml`（挂载 `~/.adalflow` 做持久化：repos、databases、wikicache 三目录）、`Dockerfile-ollama-local`（本地模型）、`charts/deepwiki-open` Helm chart（Secret 存 key、PVC 保 `~/.adalflow`、支持 Ingress/Gateway API）。对外暴露 MCP server 供外部 agent 查询仓库知识；Wiki 可导出。生成物的“版本”就是缓存文件名里的 owner/repo/language，不进 git。

## 借鉴点与对应关系

| # | 借鉴点 | 对应 | 来源 |
| --- | --- | --- | --- |
| 1 | 乘性加权 + 频率阻尼取代扁平三档加分：被提及标识符 ×10、长蛇形/驼峰 ×10、下划线开头 ×0.1、在 >5 文件重复定义 ×0.1、引用次数开平方；通用名（如 install.py、utils）机制上就被压住，不用特判 | #13 | aider `aider/repomap.py` → `get_ranked_tags()` 的 `mul`；`aider/website/docs/repomap.md` §Optimizing the map |
| 2 | 二分搜索贴合预算：对排好序的候选集做二分搜索找恰好塞满预算的最大前缀（误差容忍 15%），比“贪心累加到 8000 tokens 就停”更贴合，同样逻辑可用于 ask 的上下文拼装 | 新想法 | aider `aider/repomap.py` → `get_ranked_tags_map_uncached()` |
| 3 | 制品目录定型为两段式：先出机器可校验的大纲（节 → 页 → 每页源文件、重要度、关联页），解析失败按块正则恢复，再逐页填内容 | #14 | deepwiki-open `api/services/wiki/structure.py`（`_parse_sections`、`_pages_via_regex`、`_normalize_importance`） |
| 4 | 引用精确到行：每个 chunk 单独复制一份元数据，用顺序子串搜索反算起止行号，问答带文件:行-行出处 | #12 | deepwiki-open `api/rag/pipeline.py`（LineTrackingTextSplitter）；`api/config/embedder.json`（chunk_size 350、overlap 100） |
| 5 | 轻量防过时：缓存/制品文件名编码“需求 id + 源 commit + 预算 + 分级”，内容 hash 变化即失效；build 加 `--refresh auto\|manual\|always` 四档 | 新想法 | aider `aider/repomap.py`（`CACHE_VERSION`、mtime 校验、cache_key 含全部输入、refresh 四档）；deepwiki-open `api/services/wiki/io.py`（缓存文件名编码 owner/repo/language） |
| 6 | 树列举与索引共用同一套过滤实现，避免两边口径漂移；超大文件直接跳过并记 warning | 新想法 | deepwiki-open `api/rag/pipeline.py`（`iterate_files`）；`api/config/repo.json`（excluded_dirs 30+ 项、excluded_files 上百条 pattern） |

## 来源

- aider：`README.md`、`aider/repomap.py`（全文 27,306 字节）、`aider/website/docs/repomap.md`、`git.md`、`config.md`
- deepwiki-open：`README.md`、`README.zh.md`（英文 README 已缩成指向 Grok-Wiki 2.0 的 stub，完整说明只剩中文版）、`api/rag/pipeline.py`、`api/rag/rag.py`、`api/services/wiki/structure.py`、`api/services/wiki/io.py`、`api/services/wiki/content.py`、`api/services/codemap.py`、`api/config.py`、`api/config/embedder.json`、`api/config/repo.json`

## 诚实标注

- aider 的 git 自动提交与 Conventional Commits 留痕不适合直接抄——req-code-kb 的纪律是“人按 y 确认才入库”，自动提交会越过确认闸；只借“提交信息对照 diff 生成”这半句。
- deepwiki 的纯向量检索（FAISS + top_k 20）对 req-code-kb 是降级——已有 ast 调用图 + TF-IDF 且零依赖，引向量库会破零依赖红线；只借行号标注与缓存命名。另提醒：deepwiki-open 英文 README 已改为 Grok-Wiki 2.0 托管版引流，自托管路径的长期维护存在不确定性，借鉴以仓内现存代码（`api/`、`docker-compose.yml`、`charts/`）为准。

## 验收

- [ ] 两仓五点齐全，借鉴点至少 3 条，条条有对应 issue 或标明新想法
- [ ] 数字与分析文件、短名单文件一致
