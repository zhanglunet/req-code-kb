# click-req-3902

## 背景

`HelpFormatter.write_usage` 在终端宽度有限时会将带连字符的选项名
拆成两行。例如 `--max-retry-count` 可能显示成一行末尾的 `--max-`，
再从下一行的 `retry-count` 继续。带连字符的自定义参数占位符也受影响。

报告指出 `wrap_text` 使用的 `textwrap.TextWrapper` 可以在连字符处
折行，调用方目前无法阻止这种拆分。

## 需求

用法行和帮助文本在选项或参数名称之间换行，保持单个带连字符的名称完整。

## 验收标准

- 宽度不足以容纳下一个选项名时，把完整的选项名移到下一行。
- 带连字符的参数占位符不从连字符处拆开。
- 续行保留用法行的缩进。

## 来源

- [pallets/click #3362](https://github.com/pallets/click/issues/3362)
