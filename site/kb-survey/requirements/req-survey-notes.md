# req-survey-notes

> **方法说明**：本页由 2026-11-26 调研整理（各仓库 README / 架构文档），非 reqkb build 从代码抽取——build 只解析 Python，这三仓是 TypeScript/Clojure，无法用 build 直接建页。借鉴点只借思路：思源、logseq 是 AGPL-3.0，AFFiNE 是自定义协议，只借思路、不复用代码。数字只用分析文件里已核实的。

## 需求原文

## 背景

#11 实战演练：找 GitHub 上最流行的知识库相关开源仓库，分析可借鉴之处。
本页是笔记/个人知识库类：AFFiNE（块是组织单位）、思源笔记（块级引用 +
双向链接）、logseq（大纲 + 本地知识图谱）。三家一致：检索与引用的最小单位
都是块而非文件/页。

## 需求

- 说清三仓的组织、检索、索引、回流、协作五点。
- 给出对 req-code-kb 具体可借鉴的点，每条注明对应 issue 或新想法，并附来源。

## 验收标准

- [ ] 三仓五点齐全，借鉴点至少 3 条，条条有对应 issue 或标明新想法
- [ ] 数字与分析文件、短名单文件一致

## 仓库一览

| 仓库 | star | 语言 | 许可证 | 最近 push | 一句话 |
| --- | --- | --- | --- | --- | --- |
| toeverything/AFFiNE | 78,602 | TypeScript | 自定义协议 | 2026-11-26 | 块编辑器：文档 + 白板 + 数据库合一 |
| siyuan-note/siyuan | 47,397 | TypeScript | AGPL-3.0 | 2026-11-26 | 隐私优先的块级知识库 |
| logseq/logseq | 45,712 | Clojure | AGPL-3.0 | 2026-11-26 | 大纲式本地知识图谱 |

## 内容

### toeverything/AFFiNE

- **组织单位：块（block）。** BlockSuite block model：每个块有不可变唯一 ID、flavor（如 `affine:paragraph`）、属性与父子关系，存于 Yjs `Y.Doc` 这棵 CRDT 块树；文档页、白板（edgeless canvas）、多视图数据库块都由同一批块拼成；工作区 = 文档集合。
- **检索**：`DocsSearchService` + `DocsQuickSearchSession`，标题 + 全文跨块/文档；服务端用 Manticore 做全文、Postgres + pgvector 存 AI 向量；MCP `doc_search` 同时支持关键词与语义检索，返回“有界片段 + 页/画布定位符”（白板文字也可搜，带 element/frame 定位）。
- **索引与切分**：`docs-search` 模块订阅 doc engine 的变更事件，把更新内容增量写入索引器（事件驱动增量索引，非全量重建）；本地桌面用 SQLite、Web 用 IndexedDB，且文档 / blob / 索引 / 同步四类存储分开；切分单位就是块，搜索命中以块为粒度返回。
- **回流/防过时**：索引订阅文档变更，文档一改索引即跟进；Yjs 自带 time-travel（历史回溯）+ 页面历史；协作冲突由 CRDT 在字符/块级合并，而非事后覆盖。
- **协作与版本化**：本地优先（数据先落本地盘，云只是可选项）+ Yjs / y-octo CRDT 实时同步与多人协作；可自托管（Docker）；社区版 CE 可自托管（README 自述 MIT），企业版 EE 另有许可，属开核模式。

### siyuan-note/siyuan

- **组织单位：块。** 段落/标题/列表项/表格等每个块都有 22 字符全局唯一 ID；文档是 `.sy` 文件，即 Lute AST 树序列化成的 JSON（根 `NodeDocument`，`Children` 递归嵌套）；笔记本 > 文档 > 块。文档改名/转标题不破坏引用，因为引用锚的是块 ID 不是标题。
- **检索**：五种检索方法（API `method`：0 关键词、1 查询语法、2 SQL、3 正则、4 语义检索）；SQLite FTS5 全文索引；SQL 查询嵌入块（`NodeBlockQueryEmbed`，如 `select * from blocks where id='…'`，查询结果直接嵌进文档实时渲染）；块引用 + 双向链接 + 反链面板；资产内容检索（PDF/Word/Excel）；CLI 也有 `search` / `sql` / `ref` 命令。
- **索引与切分**：内核维护两套索引——`blocktree.db`（块 ID → 文件路径，块引用与面包屑依赖它）+ `siyuan.db` FTS5；所有写操作必须走 HTTP API / MCP / CLI，让内核同步序列化与索引，直接改文件会绕过索引，事后须跑 rebuild index；块自带 IAL 属性（`id` / `updated` / 自定义 `custom-*`），即块级元数据。
- **回流/防过时**：`docs/LONG-TERM-MEMORY.md` 给了一套可抄的状态机——记录分 candidate / active / review / disabled / superseded / withdrawn，只有 active 且证据有效才可用；每条记录用完整文件字节的 SHA-256 做 CAS 版本号；概览带“源集合指纹”，增删改都使指纹失效；删除/遗忘用 withdrawal marker 而非物理删除，旧快照恢复会把记录与 marker 一起滚回；并明文警告：直接 SQL 写只改派生索引库，不更新源文档、全文索引与块缓存。
- **协作与版本化**：个人工作区定位，README 未提供实时多人共编；同步走官方端到端加密云 / S3 / WebDAV（付费档），dejavu 数据仓做快照与历史（CLI 有 `repo` / `history` / `sync` 三类命令）；明确警告不支持第三方同步盘（会损坏数据）；数据仓密钥独立保护快照与同步数据。

### logseq/logseq

- **组织单位：块（大纲节点）。** 每行一个块，有 UUID、父节点、顺序与属性；页 = 具名根块，日记 = 日期页；DB 版（2.0 beta）里页与块统一为 node，行为趋同。组织靠链接而非文件夹。
- **检索**：DataScript + Datalog 查询（简单查询、高级查询、查询构造器，`#Query` 标签页可管理查询）；独立 SQLite 全文检索索引；`[[ ]]` 双向链接自动生成反链，未链接引用（unlinked references）会把纯文本提及找出来供人转成链接；图谱视图看整图聚类。
- **索引与切分**：OG（文件图）：Markdown/Org 文件是唯一事实源，mldoc 解析器转成块、写入内存 DataScript（派生、可重建的缓存）；敲字时三件事——落盘、更新 UI、向 DataScript 发 transaction 并重建查询缓存；DB 版：内存 DataScript + SQLite-WASM 持久化（OPFS/本地文件），主数据、全文索引、同步操作日志是三个独立的 SQLite 库，数据库操作隔离在专用 worker 线程（Comlink RPC），带 schema 迁移。
- **回流/防过时**：派生索引设计——索引永远可从源文件重建，文件改了就重解析；所有改动走带意图的 outliner op（`:save-block` / `:insert-blocks` / `:move-blocks` / `:delete-blocks` / `:create-page` 等），事务带校验与重试；DB 版用服务端定序的同步日志，按意图重放；自动备份保留最近 12 份（浏览器每小时、桌面进图内 `backups` 文件夹）；可导出 EDN/SQLite。
- **协作与版本化**：OG 是纯本地 Markdown/Org 文件，天然 git 友好（技术栈里有 isomorphic-git），冲突粒度是文件；DB 版上 RTC 实时协作同步（付费，可自托管同步服务器），图内只有 manager/member 两档角色；图谱可发布为静态站（官方文档站本身就是一个发布的 Logseq 图）。

## 借鉴点与对应关系

| # | 借鉴点 | 对应 | 来源 |
| --- | --- | --- | --- |
| 1 | 块级切分 + 稳定块 ID + 索引可重建：把“函数/类/节”定为块，给每个块稳定 ID（文件路径 + 标识符 + 行号锚点），ask 返回块级出处；build 与 ask 必须同走一套索引写入路径，索引损坏/过期时可从源码全量重建，而不是静默读脏索引 | #12 | 思源 SY-FORMAT.md（块 ID 与双索引）、Logseq CODEBASE_OVERVIEW.md（派生索引）、AFFiNE docs-search（块粒度命中） |
| 2 | “疑似相关”单列待确认候选，不悄悄加分：hub 页开“未命中加分规则、但文本/调用提及的候选”区，人工确认后才进正式列表或记一条显式规则 | #13 | logseq `db-version.md` / README（unlinked references）；siyuan README（反链面板） |
| 3 | 写一份 SY-FORMAT 式的制品契约文档：页结构、块 ID 规则、三档加分语义（各自定义触发条件与反例）、full/lite/vibe 分级定义、harvest 回流格式——争议先查契约，不翻代码 | #14 | siyuan `docs/SY-FORMAT.md`；logseq `CODEBASE_OVERVIEW.md` |
| 4 | harvest 预测加状态机与版本号：每条预测记状态（待验证/已证实/已证伪/已取代）与 build 版本号；旧预测被新版取代记 superseded 而不是删掉；ask 回答附带预测版本，过期预测自动进 review 而不是继续当证据 | 新想法 | siyuan `docs/LONG-TERM-MEMORY.md`（candidate/active/review/disabled/superseded/withdrawn + SHA-256 CAS 版本号 + 源集合指纹）；logseq `CODEBASE_OVERVIEW.md`（outliner op） |
| 5 | 搜索与解析做成可插拔模块接口，默认 TF-IDF / ast 不变：`ask` 后留极薄的搜索模块接口，`build` 解析层留解析器接口；#15 的 tree-sitter 多语言接入就只是“给每种语言注册一个解析器” | #15 / 新想法 | logseq `deps/graph-parser`（解析器抽成独立库，mldoc 与应用解耦）；AFFiNE 事件驱动增量索引的形状 |
| 6 | 站名即“知识库名”而非工具名，域名与发布形态（Cloudflare Pages 静态站）写进同一页决策 | #16 | logseq Publish（图谱一键发静态站）；AFFiNE 自托管 |

## 来源

- AFFiNE：README，BlockSuite 架构说明（blocksuite.io 体系）、AFFiNE `docs-search` 模块与 MCP `doc_search` 说明（web 检索补）
- 思源：README，`docs/SY-FORMAT.md`、`docs/LONG-TERM-MEMORY.md`、`docs/API.md`
- logseq：README，`CODEBASE_OVERVIEW.md`、logseq/docs 仓 `db-version.md`

## 诚实标注

- AFFiNE 服务端检索（Manticore + pgvector）对零依赖的 req-code-kb 不适用，可借的只是“事件驱动增量索引 + 块粒度命中”这个形状。
- 思源的教训要记牢：直接改文件会绕过索引，事后须跑 rebuild index——req-code-kb 的 build 与 ask 必须同走一套索引写入路径。
- 三家都是 AGPL-3.0（思源、logseq）或自定义协议（AFFiNE），只借思路、不复用代码。

## 验收

- [ ] 三仓五点齐全，借鉴点至少 3 条，条条有对应 issue 或标明新想法
- [ ] 数字与分析文件、短名单文件一致
