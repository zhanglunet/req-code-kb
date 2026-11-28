# req-overview

## 需求原文

## 背景

CLI-Anything 是个大仓库（1700 多个文件），第一眼看不到全貌：顶层有
几十个软件目录（`blender`、`gimp`、`obsidian`……），又有 `cli-hub`、
`cli-anything-plugin`、`skills`、`skill_generation`、`cli-hub-matrix`、
`docs` 这些横向部件。本需求要一张仓库全图：各部分是什么、彼此怎么
连起来。

## 需求

- 说清顶层目录分工：`cli-anything-plugin`（Claude Code 插件，含
  `HARNESS.md` 方法论、`repl_skin.py`、`commands/`）、`cursor-plugin` /
  `codex-skill` / `hermes-skill` / `reasonix-skill`（各家智能体入口）、
  `cli-hub`（包管理器）、`skills/`（71 个 `cli-anything-<软件>` 的
  canonical SKILL.md）、各软件目录下的 `agent-harness/`（真正的 CLI
  外壳）、`cli-hub-matrix/`（分领域配方）、`docs/`（预览机制等文档）。
- 说清三份注册表 `registry.json` / `public_registry.json` /
  `matrix_registry.json` 各自管什么。
- 说清一条线怎么走通：从“想给某个软件做 CLI”到“智能体在终端里调用
  它”，经过哪几个部件。

## 验收标准

- [ ] 知识页有一张模块分工表，覆盖插件、包管理器、技能库、软件外壳四层
- [ ] 知识页说清三份注册表的分工
- [ ] 知识页有一条端到端的链路说明
- [ ] 最小上下文 ≤10 个文件，≤8000 tokens

来源：/home/hatch/workspace/req-code-kb-work/cli-anything-kb/req-overview.md

## 相关文件 / 函数

| 文件 | 关联 | 命中符号 |
| --- | --- | --- |
| [cli-anything-plugin/HARNESS.md](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cli-anything-plugin/HARNESS.md) | 种子 | — |
| [cli-hub/cli_hub/matrix.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cli-hub/cli_hub/matrix.py) | 种子 | `fetch_matrix_registry` (L65) |
| [README.md](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/README.md#L181) | 种子 | § 🚀 Quick Start (L181-L785) |
| [cli-hub/cli_hub/registry.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cli-hub/cli_hub/registry.py) | 种子 | `_fetch_json` (L32) |
| [cli-anything-plugin/repl_skin.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cli-anything-plugin/repl_skin.py) | 种子 | `ReplSkin.prompt` (L247), `ReplSkin` (L106) |
| [eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/core/commands.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/eth2-quickstart/agent-harness/cli_anything/eth2_quickstart/core/commands.py) | 种子 | `validator_plan` (L27) |
| [cli-anything-plugin/README.md](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cli-anything-plugin/README.md) | 种子 | — |
| [cli-hub/cli_hub/matrix_skill.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cli-hub/cli_hub/matrix_skill.py) | 种子 | `_render_stage_tooling` (L355), `render_matrix_skill_file` (L116), `_render_discovery_section` (L395) |
| [safari/agent-harness/cli_anything/safari/safari_cli.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/safari/agent-harness/cli_anything/safari/safari_cli.py) | 1 跳邻居 | `cli` (L189), `get_session` (L81), `main` (L621) |
| [cc-switch/agent-harness/cli_anything/ccswitch/ccswitch_cli.py](https://github.com/HKUDS/CLI-Anything/blob/34f519533bc175d2fe287ab8316b0dd99bb9cc43/cc-switch/agent-harness/cli_anything/ccswitch/ccswitch_cli.py) | 种子 | `cli` (L181), `skills` (L698), `main` (L982) |

共 10 个文件，约 7812 tokens（预算内），分级：full——完整（跨多文件、核心逻辑）。

## 调用链

```mermaid
flowchart LR
    cli_hub_cli_hub_matrix_py__fetch_matrix_registry --> cli_hub_cli_hub_matrix_py___ensure_cache_dir
    cli_hub_cli_hub_matrix_py__fetch_matrix_registry --> cli_hub_cli_hub_matrix_py___load_cached_data
    cli_hub_cli_hub_matrix_py__fetch_matrix_registry --> cli_hub_cli_hub_matrix_py___load_local_registry
    cli_hub_cli_hub_matrix_py__fetch_matrix_registry --> cli_hub_cli_hub_matrix_py__get
    cli_hub_cli_hub_matrix_py__fetch_matrix_registry --> cli_hub_cli_hub_matrix_py__json
    cli_hub_cli_hub_registry_py___fetch_json --> cli_hub_cli_hub_registry_py___ensure_cache_dir
    cli_hub_cli_hub_registry_py___fetch_json --> cli_hub_cli_hub_registry_py___load_cached_data
    cli_hub_cli_hub_registry_py___fetch_json --> cli_hub_cli_hub_registry_py__get
    cli_hub_cli_hub_registry_py___fetch_json --> cli_hub_cli_hub_registry_py__json
    cli_anything_plugin_repl_skin_py__ReplSkin_prompt --> cli_anything_plugin_repl_skin_py___c
    cli_hub_cli_hub_matrix_skill_py___render_stage_tooling --> cli_hub_cli_hub_matrix_skill_py__get
    cli_hub_cli_hub_matrix_skill_py__render_matrix_skill_file --> cli_hub_cli_hub_matrix_skill_py___copy_matrix_assets
    cli_hub_cli_hub_matrix_skill_py__render_matrix_skill_file --> cli_hub_cli_hub_matrix_skill_py___load_matrix_skill_template
    cli_hub_cli_hub_matrix_skill_py__render_matrix_skill_file --> cli_hub_cli_hub_matrix_skill_py___render_injected_section
    cli_hub_cli_hub_matrix_skill_py__render_matrix_skill_file --> cli_hub_cli_hub_matrix_skill_py___resolve_matrix_content_source
    cc_switch_agent_harness_cli_anything_ccswitch_ccswitch_cli_py__cli --> cc_switch_agent_harness_cli_anything_ccswitch_ccswitch_cli_py___show_status
    cc_switch_agent_harness_cli_anything_ccswitch_ccswitch_cli_py__main --> cc_switch_agent_harness_cli_anything_ccswitch_ccswitch_cli_py__cli
```

## 影响面

改种子文件之前先看这一节：列出调用种子符号的上游文件，也就是改动最先波及的地方（取每文件前 3 个调用者，按调用者重要性排序）。

- 改 `cc-switch/agent-harness/cli_anything/ccswitch/ccswitch_cli.py` 会波及：`cc-switch/agent-harness/cli_anything/ccswitch/ccswitch_cli.py` 的 `main`

## 群消息佐证

暂无。

## 验收

- [ ] 核心改动文件在上方清单中
- [ ] 召回覆盖真实改动文件（盲测见 `tests/test_blind.py`）

