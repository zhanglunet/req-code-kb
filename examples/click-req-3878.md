# click-req-3878

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
