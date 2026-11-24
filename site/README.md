# req-code-kb 知识库网站

把 req-code-kb 沉淀的知识库（`kb/index.json` + `kb/requirements/*.md`）
生成一个静态站，部署到 Cloudflare Pages。

## 生成

```bash
python3 sitegen.py            # 输出到 dist/
python3 sitegen.py --out /tmp/preview   # 换个输出目录也行
```

纯标准库，不用装任何东西。Mermaid 用的是本地 `assets/mermaid.min.js`
（v10.9.1，已下载进仓库），页面不依赖任何 CDN。

## 新增知识页怎么进来

1. 用 req-code-kb 正常沉淀新页（`reqkb build`），它会更新对应 `kb/index.json`；
2. 重新跑一遍 `python3 sitegen.py`，新页自动出现在首页和 sitemap 里；
3. 不用手写任何 HTML。

## 新增一个知识库来源

在 `sources.json` 里加一条：

```json
{
  "id": "my-repo",
  "title": "作者/仓库名",
  "repo_name": "作者/仓库名",
  "repo_url": "https://github.com/作者/仓库名",
  "kb_dir": "kb",
  "blurb": "一句话介绍"
}
```

`kb_dir` 是相对仓库根目录的路径（仓库里生成器在 `site/` 下，`kb` 就在根目录）；本地用绝对路径也行。

再跑一遍生成器即可。`sources.json` 是本地配置，不会进 `dist/`。

## 文件

| 文件 | 作用 |
|---|---|
| `sitegen.py` | 生成器：标准库迷你 Markdown 渲染（标题、段落、列表、任务清单、GFM 表格、代码块、Mermaid）+ 建站 |
| `sources.json` | 知识库来源清单 |
| `templates/base.html` | 页面骨架 |
| `templates/style.css` | 全站样式（浅色/深色主题与响应式排版） |
| `templates/app.js` | 轻量交互增强（主题切换、Mermaid 主题同步、实时筛选、目录高亮） |
| `assets/mermaid.min.js` | Mermaid v10.9.1（本地化，页面离线也能画调用链图） |
| `dist/` | 生成产物：`index.html`、每来源一目录、每需求一页、`sitemap.xml` |
| `DEPLOY.md` | 部署方案（Cloudflare Pages） |

## 安全注意

- 生成器会删掉知识页里泄露本地绝对路径的行（比如 `来源：/home/...`），
  不会把本机路径印到公开页面上。
- `dist/` 里不含任何密钥、token、`sources.json`。

## 部署

见 `DEPLOY.md`。部署前先确认，部署本身不在本仓库里做。
