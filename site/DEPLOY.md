# 部署方案：req-code-kb 知识库网站 → Cloudflare Pages

> 状态：方案已写好，未部署。部署前须用户确认选 A 还是 B。

## 已核实的前提（2026-11-24，全部是只读查询）

- Cloudflare API token 有效：`GET /client/v4/user/tokens/verify` 返回
  `active`，有效期到 2027-11-13。
- 账户：`77ede614403a81f68b2fa75a8863c8d4`（Zhanglu.net@gmail.com's Account）。
- 账户下现有 19 个 Pages 项目，**没有** `req-code-kb`，项目名可用，
  默认域名将是 `https://req-code-kb.pages.dev`。
- Token 的权限范围**无法**通过 API 自查（`GET /client/v4/user/tokens/<id>`
  报 403 code 9109）；Pages:Read 已证实（项目列表能拉出来），
  Pages:Edit **未证实**——第一次写操作才能验证，见下边 B 方案的回退。

## 方案 A（推荐）：Pages + GitHub 自动部署

不需要 API token，改动在仓库与网页控制台里完成；以后 main 每推一次，
网站自动重新生成上线。

### A1. 先把生成器放进仓库（须用户批，开 PR，只开不合）

把本目录的 `sitegen.py`、`sources.json`、`templates/`、`assets/`、
`README.md`、`DEPLOY.md` 原样放进 `zhanglunet/req-code-kb` 的 `site/`
目录。`sources.json` 里的 `kb_dir` 要改成仓库内相对路径，例如：

```json
{"id": "click", "kb_dir": "kb", "repo_name": "pallets/click",
 "repo_url": "https://github.com/pallets/click",
 "title": "pallets/click 范例", "blurb": "……"}
```

也就是说 click 的 `kb/` 也要随仓库走（它本来就在仓库里）；CLI-Anything
的 `kb/` 目前只在本地工作目录（`~/workspace/req-code-kb-work/`），要么
也放进仓库（建议：`site/kb-cli-anything/`，公开内容、无敏感信息），
要么 A 方案第一期只上 click，CLI-Anything 等它进仓库再加。

生成器要改一处：`kb_dir` 从绝对路径改成相对 `site/` 的路径（小改，
`sources.json` 里写相对路径、`sitegen.py` 按 `site/` 解析即可）。

### A2. 控制台建项目（用户在网页上点，约 5 分钟）

1. Cloudflare 控制台 → Workers & Pages → Create → Pages → Connect to Git。
2. 选 `zhanglunet/req-code-kb` 仓库（首次要授权 Cloudflare GitHub App
   访问该仓库）。
3. Build settings：
   - Framework preset：None
   - Build command：`python3 site/sitegen.py --out dist`
     （Cloudflare 构建镜像自带 Python 3；若构建日志报 Python 不可用，
     改走 `python3 -m pip install` 不需要——生成器是纯标准库）
   - Build output directory：`dist`
   - Root directory：留空（仓库根目录）
   - Production branch：`main`
4. Project name 填 `req-code-kb` → Save and Deploy。
5. 首次部署成功后访问 `https://req-code-kb.pages.dev` 核对首页与一页
   调用链图。

### A3. 以后的更新

- 新知识页沉淀进仓库 main → Pages 自动重新构建上线，无需人工操作。
- 改生成器本身也走同样的 PR 流程。

## 方案 B（不改仓库）：本机 wrangler 直接部署

适合“先上线看看，不动仓库”的情况。缺点是每次更新都要在本机跑一次
部署命令，没有自动部署。

```bash
cd ~/workspace/req-code-kb-site
python3 sitegen.py
# 用现成的 wrangler（meeting-agent 项目自带的 node_modules 里有）
# 并按 custom.cloudflare 连接器的做法，把 token 经代理交给 wrangler：
CLOUDFLARE_API_TOKEN='<由 dynamic_credentials 运行时解析的 surrogate>'
~/workspace/work/meeting-agent-transcript-md/src/node_modules/.bin/wrangler \
  pages deploy dist --project-name req-code-kb
```

注意：

- `wrangler` 没有全局安装；上面用的是已装好的那份，或 `npx wrangler`
  现场下载（第一次慢）。
- 若报 403（token 缺 Pages:Edit），回退办法二选一：
  1. 在 Cloudflare 控制台 My Profile → API Tokens → Create Token，
     建一个带 **Account: Cloudflare Pages:Edit** 权限的新 token
     （不要用 Global API Key），再按连接器文档走 `request_api_access`
     重新注册；或
  2. 改走方案 A（控制台点几下，不用 token）。
- 首次部署时 wrangler 会问是否新建项目，选创建 `req-code-kb`。
- 部署成功后 wrangler 会打印 `https://req-code-kb.pages.dev`。

## 域名

- 默认：`https://req-code-kb.pages.dev`（免费，名已确认可用）。
- 自定义域名（可选，以后再定）：比如 `kb.zhanglu.net`，在 Pages 项目里
  Custom domains → Set up a custom domain，按提示加 DNS 记录即可。
  前提是 `zhanglu.net` 的 DNS 在 Cloudflare 上（部署时再核对）。

## 费用

纯静态站：无 Worker 函数、无 KV、无 R2、无构建分钟数之外的计费项，
在 Cloudflare Pages 免费额度内。部署本身不建任何计费资源。

## 部署前检查清单

- [ ] 用户选 A 还是 B
- [ ] A：生成器进仓库的 PR 已开并已合；`sources.json` 路径已改相对路径；
      CLI-Anything 的 `kb/` 是否进仓库已定
- [ ] B：Pages:Edit 权限已验证（或已准备好新 token 的回退）
- [ ] 上线后核对：首页 2 个来源、6 页、每页调用链图能画出来、无本机路径泄露
