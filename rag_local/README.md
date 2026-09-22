# 个人知识 RAG 助手 · 本地运行指南

这是**在你自己电脑上**把 RAG 助手跑到「能真正回答」的最省事方式：不碰 Cloudflare、不碰魔搭，
密钥只从本机环境变量读取，任何文件里都不写密钥。

## 它是什么

`run_rag.py` 是一个只用 Python 标准库的本地小服务器，扮演网站 RAG 页面需要的「后端代理」：

| 页面发来的请求        | 本服务器转发到            | 作用             | 用到的密钥                  |
|-----------------------|---------------------------|------------------|-----------------------------|
| `POST /embeddings`       | 硅基流动 `bge-m3`          | 把问题变成向量   | `SILICONFLOW_CN_API_KEY`     |
| `POST /chat/completions` | DeepSeek `deepseek-chat`   | 生成自然回答     | `DEEPSEEK_API_KEY`           |

同时它把整个 `site/` 目录当静态站托管，并在返回 `projects/knowledge-rag.html` 时，
自动把页面里的占位符 `__PROXY_BASE__` 换成 `http://127.0.0.1:<端口>`。

> 这与将来上线用的 `site/proxy/worker.js`（Cloudflare Worker）是**同一套接口**。
> 哪天要上线，只要把页面 `CONFIG.PROXY_BASE` 从本机地址换成 Worker 地址即可，代码零改动。

## 跑起来（3 步）

```bash
cd site/rag_local
python run_rag.py
# 浏览器打开  →  http://127.0.0.1:8017/projects/knowledge-rag.html
```

- 端口被占用就换：`python run_rag.py 8020`
- 你机器上已设了 `DEEPSEEK_API_KEY` 与 `SILICONFLOW_CN_API_KEY`，启动横幅会显示「已检测到」→ 直接全功能。
- 万一没设硅基流动 key：向量检索会自动降级成中文 BM25，**仍能问答**（只是检索没那么“懂语义”）。

## 没有环境变量怎么办（可选）

在本目录放一个 `.env`（已在 `.gitignore` 里，绝不会进仓库）：

```
DEEPSEEK_API_KEY=sk-xxxx
SILICONFLOW_CN_API_KEY=sk-xxxx
```

## 安全边界

- 服务器只绑定 `127.0.0.1`，不对外网开放，别人连不上你的代理。
- 前端限流每小时 20 次；本工具仅供你自测。
- 任何密钥都不写进 `run_rag.py` / 页面 / 仓库。

## 常见问题

- **打开页面只有“检索到 N 段”但不回答？** 说明 `DEEPSEEK_API_KEY` 没读到——看启动横幅是否“已检测到”。
- **想改语料 / 问得更准？** 语料在 `../projects/knowledge-rag.html` 的 `DOCS` 数组里（36 段真实笔记）。
  改了 `DOCS` 后，用仓库根的 `../build-rag-vectors.mjs` 重算 `rag-vectors.js`（需 `SILICONFLOW_CN_API_KEY`），
  否则页面会用预置旧向量、或自动降级 BM25。
