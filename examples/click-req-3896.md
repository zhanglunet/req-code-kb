# click-req-3896

## 背景

`CliRunner.invoke()` 会把多余的关键字参数传给命令的 `Context`，
但 `color` 例外：`invoke()` 自己有一个 `color` 参数占了这个名字。
于是测试里没法在同一次调用中，既设定终端支持情况、又设定
`Context` 的 `color`。

这个问题 5 年前在 #2110 提过，当时被认为太小众；此后 Click 做了一
系列颜色处理改进（#3505、#3653、#3739），颜色相关的测试多了很多，
不再是小众需求。

## 需求

给 `CliRunner.invoke()` 加一个 `context_settings` 参数，让测试能把
上下文相关的设置传给命令的 `Context`，从而解决 `color` 的名字冲突。

## 验收标准

- `CliRunner.invoke()` 接受 `context_settings` 参数，并把它传给 `Context`。
- 一次调用里能同时设定终端支持情况和 `Context` 的 `color`。
- 已有 `color` 参数的行为不变。

## 来源

- pallets/click PR #3896《Add `context_settings` parameter to `CliRunner.invoke`》
  （2026-11-06 已合并；作者 kdeldycke）
- 本文档是盲测输入：只含需求描述，已隐去真实改动文件清单；
  需求正文提到的两个测试函数名已略去（那是验收证据，不是需求本身）。
