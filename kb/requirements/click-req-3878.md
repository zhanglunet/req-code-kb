# click-req-3878

## 需求原文

## 背景

`CliRunner` 收到 `<stdin>` 里的控制字节时，原样传给命令，也原样
回显，终端上看不出用户按了什么。

| `<stdin>` 字节 | 回显到 `<stdout>` | 按键 |
|---|---|---|
| `\x04` | `^D\n` | Unix 的 Ctrl+D |
| `\x1a` | `^Z\n` | Windows 的 Ctrl+Z |

## 需求

改 `CliRunner`：把 `\x04` 和 `\x1a` 这两个控制字节翻译后回显为
`^D` 和 `^Z`，且不再把它们传给命令。

## 验收标准

- 输入 `\x04` 时回显 `^D\n`，输入 `\x1a` 时回显 `^Z\n`。
- 命令收不到这两个字节。
- 这是行为变更，目标版本 8.6.0。

## 来源

- pallets/click PR #3878《Print `\x04` and `\x1a` input bytes as
  `^D` and `^Z` in `CliRunner`》（2026-11-06 已合并；作者 kdeldycke）
- 本文档是盲测输入：只含需求描述，已隐去真实改动文件清单。

来源：examples/click-req-3878.md

## 相关文件 / 函数

| 文件 | 关联 | 命中符号 |
| --- | --- | --- |
| [src/click/testing.py](https://github.com/pallets/click/blob/08b803c/src/click/testing.py) | 种子 | `CliRunner` (L341), `Result.stdout` (L319) |
| [CHANGES.md](https://github.com/pallets/click/blob/08b803c/CHANGES.md) | 种子 | — |
| [docs/testing.md](https://github.com/pallets/click/blob/08b803c/docs/testing.md) | 种子 | — |
| [tests/test_termui.py](https://github.com/pallets/click/blob/08b803c/tests/test_termui.py) | 种子 | `test_echo_via_pager_streams_each_write.RecordingStream.write` (L937), `FakeClock.time` (L33), `_create_progress` (L37) |
| [src/click/_termui_impl.py](https://github.com/pallets/click/blob/08b803c/src/click/_termui_impl.py) | 种子 | `ProgressBar.update` (L318), `_PagerWriter.write` (L401), `ProgressBar.render_progress` (L250) |
| [tests/test_testing.py](https://github.com/pallets/click/blob/08b803c/tests/test_testing.py) | 1 跳邻居 | `test_args` (L439), `test_capture_fd_faulthandler` (L855), `test_capture_fd_logging_handler` (L809), `test_capture_fd_nesting` (L913), `test_capture_fd_nesting.outer_cli` (L921) |
| [tests/test_stream_lifecycle.py](https://github.com/pallets/click/blob/08b803c/tests/test_stream_lifecycle.py) | 1 跳邻居 | `test_exception_does_not_corrupt_next_invoke` (L430), `test_getvalue_after_isolation_exit` (L142), `test_invoke_with_logger_and_prompt` (L208), `test_invoke_with_logger_warning` (L193), `test_invoke_with_stream_handler_on_stderr` (L246) |
| [tests/test_options.py](https://github.com/pallets/click/blob/08b803c/tests/test_options.py) | 1 跳邻居 | `test_flag_value_on_option_with_zero_or_one_args` (L3899) |
| [src/click/termui.py](https://github.com/pallets/click/blob/08b803c/src/click/termui.py) | 2 跳邻居 | `prompt` (L139), `style` (L641), `_interpret_color` (L616) |
| [tests/conftest.py](https://github.com/pallets/click/blob/08b803c/tests/conftest.py) | 1 跳邻居 | `runner` (L7) |

共 10 个文件，约 7050 tokens（预算内），分级：full——完整（跨多文件、核心逻辑）。

## 调用链

```mermaid
flowchart LR
    tests_test_termui_py___create_progress --> tests_test_termui_py__progressbar
    src_click__termui_impl_py__ProgressBar_update --> src_click__termui_impl_py__make_step
    src_click__termui_impl_py__ProgressBar_update --> src_click__termui_impl_py__render_progress
    src_click__termui_impl_py___PagerWriter_write --> src_click__termui_impl_py__strip_ansi
    src_click__termui_impl_py__ProgressBar_render_progress --> src_click__termui_impl_py__echo
    src_click__termui_impl_py__ProgressBar_render_progress --> src_click__termui_impl_py__flush
    src_click__termui_impl_py__ProgressBar_render_progress --> src_click__termui_impl_py__format_progress_line
    src_click__termui_impl_py__ProgressBar_render_progress --> src_click__termui_impl_py__term_len
```

## 影响面

改种子文件之前先看这一节：列出调用种子符号的上游文件，也就是改动最先波及的地方（取每文件前 3 个调用者，按调用者重要性排序）。

- 改 `src/click/testing.py` 会波及：`tests/conftest.py` 的 `runner`、`tests/test_context.py` 的 `test_hiding_of_unset_sentinel_in_callbacks`、`tests/test_options.py` 的 `test_flag_value_on_option_with_zero_or_one_args`

## 群消息佐证

暂无。

## 验收

- [ ] 核心改动文件在上方清单中
- [ ] 召回覆盖真实改动文件（盲测见 `tests/test_blind.py`）

