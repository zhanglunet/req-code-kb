# req-survey-rag

> **方法说明**：本页由 2026-11-26 调研整理（各仓库 README / 官方文档），非 reqkb build 从代码抽取——build 只解析 Python，ragflow 是 Go、anything-llm 是 JavaScript，无法用 build 直接建页。借鉴点只借思路：dify 是自定义协议，只借思路、不复用代码。数字只用分析文件里已核实的。

## 需求原文

## 背景

#11 实战演练：找 GitHub 上最流行的知识库相关开源仓库，分析可借鉴之处。
本页是 RAG/文档知识库类：dify（本类星数第一，知识库当数据集）、
ragflow（深度文档解析 + 图 RAG，重“怎么切文档”）、anything-llm
（一个库一个工作区，本地向量库一条龙）。

## 需求

- 说清三仓的组织、检索、索引、回流、协作五点。
- 给出对 req-code-kb 具体可借鉴的点，每条注明对应 issue 或新想法，并附来源。

## 验收标准

- [ ] 三仓五点齐全，借鉴点至少 3 条，条条有对应 issue 或标明新想法
- [ ] 数字与分析文件、短名单文件一致

## 仓库一览

| 仓库 | star | 语言 | 许可证 | 最近 push | 一句话 |
| --- | --- | --- | --- | --- | --- |
| langgenius/dify | 161,927 | Python | 自定义协议 | 2026-11-26 | Agent 工作流 + RAG 流水线平台 |
| infiniflow/ragflow | 94,734 | Go | Apache-2.0 | 2026-11-26 | Agent 原生 RAG 引擎 |
| Mintplex-Labs/anything-llm | 68,654 | JavaScript | MIT | 2026-11-24 | 一体化桌面 AI，内置文档知识库 |

## 内容

### langgenius/dify

- **组织单位**：Dataset（数据集）→ Document（文档）→ Chunk（块）三级。数据集是检索与权限的基本单位，一个应用可挂多个数据集。另有新形态 Agent Knowledge Base（1.18.0 beta）：文档先由推理模型读出大纲（Contents Outline，源自标题、模型补小节）+ 每节摘要，再建知识图谱。
- **检索**：分两档，可逐数据集调参。High Quality（高质）：向量检索 / 全文检索 / 混合检索，可选 Rerank 模型（默认关）；Economical（经济）：每块只抽 10 个关键词，零 token，倒排索引检索，精度较低。默认 TopK=3、分数阈值 0.5，且 TopK/阈值只在启用 Rerank 后才生效。Agent 知识库另有三档检索深度：Fast（语义+关键词直 match）、Deep（沿知识图谱扩到相关主题）、Research（复杂问题拆子问题，用节标题+摘要选节读）。多数据集应用还有 Multi-path Retrieval（并行查多库再 Rerank / 加权分融合）。
- **索引与切分**：流水线组件化、可视化编排：Data Source → Extractor（解析）→ Chunker（切分）→ Knowledge Base（索引+检索设置）→ Test & Publish，每步是可拖拽节点。三种 Chunker：General（定长+自定义分隔符+重叠长度）、Parent-child（子块短、用于精准匹配；父块大、用于给 LLM 供上下文；仅 HQ 模式）、QA Chunk（CSV/Excel 问答对，按问题建索引）。另有 Summary Index（v1.12.0）/ Summary Auto-Gen：给每块自动生成摘要并一并向量化索引，摘要命中则原块一并返回，摘要可人工改写或对指定文档重生成；兼容 General 与 Parent-child。
- **回流/防过时**：没有显式的“过期检测”机制（所读文档中未见 staleness 判定）。靠三条间接手段：Notion 数据源自动同步更新；换推理模型后已索引文档保持旧结果，需点 Re-index 重建（不耗 token）；换 Embedding 模型则全部文档重生成向量（耗 token）。
- **协作与版本化**：知识库默认权限 Only me，可改共享；流水线是“先编排 → Test Run（跑通并可看 History Logs / Variable Inspector）→ Publish 才生效”，发布前 Documents 与 Retrieval Testing 两个 Tab 不可用；工作流可导出为 YAML，进 Git 做版本控制、diff、按执行回放（第三方验证文章，README 本身未展开）。

### infiniflow/ragflow

- **组织单位**：Dataset（数据集）→ Document（文档）→ Chunk（块），之上再叠一层知识编译产物（Knowledge Artifact）：同一份文档可编译出 Graph（实体关系图）、Tree（层级树）、PageIndex（保留原章节结构的层级索引）、Wiki、Mindmap、Timeline、Skills 七种制品，分文档级与数据集级两层。
- **检索**：多路召回 + 融合重排（multiple recall paired with fused re-ranking）；另有 Agentic Retrieval：Low / Medium / High / Ultra 四档思考深度，模型先分析问题、必要时拆解、多轮检索并校验证据充分性（rc3 又加了“证据是否充分”的判定模型）。答案带可追溯引用（哪条 chunk 支撑哪句结论）。
- **索引与切分**：两层。第一层是 DeepDoc 深度文档解析：版式分析（栏、页眉页脚）、表格抽取（保留行列结构）、OCR（扫描件与图内文字）、PDF/DOCX/HTML/Markdown/Excel 等格式专用解析器，1.0 开源版用 CPU 推理做版式/OCR/表格识别；解析结果可视化分块、允许人工干预。第二层是模板化切分（template-based chunking），可解释、按文档类型选模板：`naive`（通用）、`manual`（人工控）、`qa`（问答对）、`table`（表格按行）、`paper`（论文）、`book`（书按章）、`laws`（法规）、`presentation`（一页一 chunk）、`picture`、`one`（整篇一 chunk）、`email`、`knowledge_graph`；自定义流水线里是 Token Chunker（默认 512 tokens，1–2048；重叠 0–30%；分隔符默认 `\n ! ? ; 。；！？`）与 Title Chunker（按标题层级 Hierarchy/Group，chunk 上限默认 512 tokens，128–8000，超限按句再切；表/图可配上下文窗口 0–256 tokens），另支持子块检索（父块切小块做检索）。每块还可抽关键词 + 生成相关问题以提升召回（2024-11-01 更新）。另注：Python API 参考 `create_dataset(chunk_method, parser_config)` 里有个值得注意的参数：`pagerank: int`，默认 0。
- **回流/防过时**：机制分两面。自动的一面：数据集级制品在文档新增/重解析/删除后由系统自动调度更新（新文档跑完 Pipeline 即并入，删文档即从制品中移除其贡献；Ingestor 服务须在运行）；数据源支持增量同步（BigQuery 增量同步，2026-07-02；网站经 sitemap 摄入，2026-09-10）。手动的一面：改编译模板不会自动重编已完成文档，必须重解析（reparse）才生效——这是明确写在文档里的反直觉点。
- **协作与版本化**：Dataset 权限分 `me`（仅自己）与 `team`（全队可管）；摄入流水线是 Save draft → Publish 生成一个 pipeline 版本，数据集配置里选定“某条已发布版本”才生效；解析任务日志可逐节点（Parser→Chunker→Compiler→Indexer）核查。

### Mintplex-Labs/anything-llm

- **组织单位**：Workspace（工作区）是多租户/隔离原语——一个库就是一个工作区。每篇文档以 `workspace_documents` 行挂在某个 `workspaces` 下；向量、聊天记录、LLM/Embedding 选型、权限全部以 `workspaceId` 为键。另有两级上下文：Thread 附件（全文插入、仅当次对话）vs Workspace 嵌入（RAG、全部对话共享）。定位：“私人 ChatGPT + 文档问答”，三进程单体：`server/`（Express+Prisma）+ `frontend/`（React）+ `collector/`（独立的文档摄入服务）。
- **检索**：向量检索为主。默认本地 LanceDB（内嵌、零部署），可换 Qdrant / Weaviate / Pinecone / Chroma / Milvus / Astra 等 10 种后端（`VECTOR_DB` 环境变量）。每工作区可调：Document similarity threshold（默认最低 20%，低于则过滤）、Max Context Snippets（默认 4–6 条，多了会噪音）、Search Preference（仅 LanceDB：默认“最相关”，或 "Accuracy Optimized"——多取再重排，约 +100–500ms）。另有 Document Pinning（钉住关键文档全文插入上下文，不走 RAG、不重复计入检索结果）。
- **索引与切分**：摄入与问答分离——`collector/` 是独立进程，挂了不拖垮 API。流程：`processSingleFile/`（8 类格式转换器：PDF/DOCX/EPUB/TXT/XLSX/音频/图片/Mbox/Office）+ `processLink/`（URL 抓取）+ `processRawText/`；切分默认 1000 字符/块、重叠 20 字符（设置里叫 Text Chunk Size / Overlap），UI 在确认嵌入前显示 chunk 数与预估 token、可调。改切分尺寸只影响之后嵌入的文档，旧文档须移出再加回。
- **回流/防过时**：有，但标实验性质。Automatic Document Sync（Live Document Sync）：后台每小时检查，文件 7 天未刷新即 stale，变了就重抓并替换其在所有工作区的向量，不变则只顺延下次检查；桌面版本地文件每 10 分钟检查。限制要照实写：手动上传的文件在 Docker 版不能同步（服务器读不到你的磁盘），只能同步链接与数据连接器（Confluence/GitHub/YouTube 等）拉来的内容；不能按文件夹 watch，只能逐文件；容器关了同步即停。另两条硬规则：换 Embedding 模型会清空全部工作区向量、须重嵌；回答默认带 Sources 列表（出处可追溯）。
- **协作与版本化**：多用户与细粒度权限仅 Docker 版；工作区级模型/向量库/权限各自独立，互不串味；提供 Developer API（API key）与可嵌入网站的聊天挂件。版本化方面：没有像 Dify/RAGFlow 那样的流水线版本概念——版本靠“文档本身重新摄入”，工作区是快照而非版本链。

## 借鉴点与对应关系

| # | 借鉴点 | 对应 | 来源 |
| --- | --- | --- | --- |
| 1 | 按标题小节切分索引，块带标题路径 + 起止行号；检索命中子节、问答带父节标题路径与文件:行-行出处 | #12 | ragflow.io《Configure the Chunker Component》Title Chunker；dify Parent-child Chunker |
| 2 | 按文档类型选切分模板（论文/书/法规/表格/问答对各有模板），可解释、可人工干预 | #12 | ragflow.io《Configure the Chunker Component》template-based chunking；《Apply Template》 |
| 3 | 摘要层索引：给每个知识页加一行“一句话摘要”字段（build 时人按 y 确认时顺手写），ask 先对摘要做 TF-IDF、命中再取全文块 | 新想法 | dify《Knowledge Pipeline Orchestration》§Summary Auto-Gen、Release v1.12.0；ragflow.io《Apply a Knowledge Compilation Template》§Update Knowledge Artifacts |
| 4 | 检索参数逐库可调 + Pinning 关键文件：L1 首页 + L2 分来源页之上再加“每来源一命名空间”（各自的 TopK/阈值/加分档）；允许把 1–2 个“必读文件”钉为全文上下文，不走 TF-IDF 排名 | #16 / 新想法 | dify《Retrieval Settings》（TopK/阈值/混合权重逐数据集）；anything-llm《Using Documents》§RAG settings / Pinning；`workspaceId` 隔离原语 |
| 5 | 轻量防过时：知识页元数据记 `source_sha + last_verified`，超过 7 天未校验即在输出里标 `stale?` | 新想法 | anything-llm《Automatic document sync》（7 天 stale） |
| 6 | Parent-child 双层块：子块短、用于精准匹配；父块大、用于给 LLM 供上下文 | #12 | dify Parent-child Chunker（仅 HQ 模式） |

## 来源

- dify：README 全文，官方文档《Knowledge Pipeline Orchestration》+《Retrieval Settings》+《Specify the Index Method and Retrieval Settings》；当前版本现场核实：1.18.0 引入 Agent Knowledge Base（beta）
- ragflow：README 全文，官方文档《Knowledge Compilation Overview / Apply Template / Configure the Chunker Component》；当前版本现场核实：已发 1.0.0（2026-11-06，Go 重写版）
- anything-llm：README 全文，官方文档《Using Documents in AnythingLLM》+《Automatic Document Sync》；当前版本现场核实：v1.19.0

## 诚实标注

- Dify 的 Agent Knowledge Base 图谱引擎在私有仓库 KnowledgeFS，不开源，抄不了实现只能抄接口思想。
- RAGFlow 1.0.0 刚发、Go 重写，知识编译等新功能 2026-08 才上，尚年轻；且重、须 4 核/16G 起步。
- anything-llm 的两个“不溯及”要当成坑来记：向量库/Embedder 一换就全量重嵌，且切分改动不溯及旧文档。
- 未核实项：Dify 所读文档中未见显式过期判定机制；三仓均未在所读 README/文档中给出可复现的检索精度基准表；RAGFlow 的 `pagerank` 数据集参数（`create_dataset(pagerank=0)`）与 req-code-kb 现有的 PageRank 排序同名，是否同义未在文档中展开说明，不宜直接对标。

## 验收

- [ ] 三仓五点齐全，借鉴点至少 3 条，条条有对应 issue 或标明新想法
- [ ] 数字与分析文件、短名单文件一致
