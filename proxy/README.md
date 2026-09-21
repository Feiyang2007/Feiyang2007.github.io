# RAG 代理 Worker 部署步骤

个人知识 RAG 助手的后端转发层。密钥只存在 Cloudflare Worker 的 Secret 里，
GitHub 仓库和前端页面都不含任何密钥（因此能通过 GitHub 的密钥扫描）。

部署完你会得到一个 `https://rag-proxy.<你的子域>.workers.dev` 地址，
把它填进 `projects/knowledge-rag.html` 顶部的 `CONFIG.PROXY_BASE` 即可上线。

## 前置
- 注册一个免费的 Cloudflare 账号：https://dash.cloudflare.com （无需信用卡）

---

## 方式 A：用 Dashboard（最简单，不用装任何东西）

1. 登录 Cloudflare Dashboard → 左侧 **Workers & Pages** → **Create application** → **Create Worker**。
2. 名字填 `rag-proxy`，把本目录 `worker.js` 的全部代码粘进编辑器，**Save and Deploy**。
3. 进入这个 Worker → **Settings** → **Variables and Secrets** → **Secrets** → **Add**：
   - `DEEPSEEK_KEY` = 你的 DeepSeek key（`sk-17b9...`）
   - `SILICONFLOW_KEY` = 你的硅基流动 key（`sk-...`）
   - （可选）`ALLOW_ORIGIN` = `https://feiyang2007.github.io`
   保存。
4. 顶部地址栏就是你的 Worker URL（形如 `https://rag-proxy.xxxx.workers.dev`），复制它。
5. 打开 `projects/knowledge-rag.html`，把 `CONFIG.PROXY_BASE` 的值改成这个 URL，提交并 push。

---

## 方式 B：用 wrangler CLI

```bash
npm i -g wrangler
cd site/proxy
wrangler login                 # 浏览器授权
wrangler secret put DEEPSEEK_KEY       # 按提示粘贴
wrangler secret put SILICONFLOW_KEY
wrangler deploy                # 输出 Worker URL
```
拿到 URL 后同样填回 `CONFIG.PROXY_BASE`。

---

## 自检
部署后可以先用 curl 验一下代理通不通（把 `<WORKER>` 换成你的地址）：

```bash
# 嵌入
curl -s -X POST <WORKER>/embeddings -H "Content-Type: application/json" \
  -d '{"model":"BAAI/bge-m3","input":["hi"]}' | head -c 120

# 生成
curl -s -X POST <WORKER>/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"说你好"}],"max_tokens":20}' | head -c 200
```
两条都返回 JSON 即代理 OK，网页的向量检索 + 生成就会全部点亮。

## 安全提示
- 千万别把 `sk-...` 写进 `worker.js` / `wrangler.toml` / 页面里 —— 那等于没做代理。
- 想更严可加：Cloudflare 控制台该 Worker → **Rate Limiting** 规则按 IP 限流；
  或用 Workers KV 记录 IP 计数做配额。
