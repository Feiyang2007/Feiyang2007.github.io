#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人知识 RAG 助手 —— 本地运行器（run_rag.py）
==================================================

一句话：在你自己电脑上把 site/ 网站跑起来，并充当 RAG 页面需要的“后端代理”，
        这样 knowledge-rag.html 就能真正做【向量语义检索 + DeepSeek 生成回答】，
        完全不用碰 Cloudflare / 魔搭，密钥只从你本机环境变量读取，绝不写进任何文件。

它做三件事：
  1) 静态托管整个 site/ 目录  →  http://127.0.0.1:8017/projects/knowledge-rag.html
  2) 代理 POST /embeddings        →  转发到「硅基流动 bge-m3」（问题向量化）
  3) 代理 POST /chat/completions  →  转发到「DeepSeek」（生成回答）
  并在返回 knowledge-rag.html 时，把里面的占位符 __PROXY_BASE__ 换成本地地址。

这与线上方案（site/proxy/worker.js 那个 Cloudflare Worker）是同一套接口契约，
将来要上线，只需把 PROXY_BASE 从本机地址换成 Worker 地址即可，代码零改动。

依赖：只用 Python 标准库，无需 pip 安装任何东西。

密钥（环境变量，二选一命名都支持）：
  DEEPSEEK_API_KEY          生成回答用
  SILICONFLOW_CN_API_KEY    或 SILICONFLOW_API_KEY   向量检索用（缺省则自动降级 BM25，仍能检索）
  （也可以在本目录放一个 .env 文件写 KEY=VALUE，本目录 .env 已在 .gitignore 里，不会进仓库）

运行：
  python run_rag.py                # 默认 127.0.0.1:8017
  python run_rag.py 8020           # 换端口
  然后浏览器打开 http://127.0.0.1:8017/projects/knowledge-rag.html
"""
import os
import sys
import json
import ssl
import gzip
import io
import mimetypes
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

# ------------------------------------------------------------------ 路径与配置
HERE = Path(__file__).resolve().parent            # .../site/rag_local
SITE_ROOT = HERE.parent                            # .../site
DEFAULT_PORT = 8017
RAG_PAGE_REL = "projects/knowledge-rag.html"       # 需要注入 PROXY_BASE 的页面

UPSTREAM = {
    "embeddings": "https://api.siliconflow.cn/v1/embeddings",
    "chat": "https://api.deepseek.com/v1/chat/completions",
}


def load_dotenv(path: Path):
    """极简 .env 解析：KEY=VALUE，不覆盖已存在的真实环境变量。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def get_key(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    return None


DEEPSEEK_KEY = get_key("DEEPSEEK_API_KEY", "DEEPSEEK_KEY")
SILICONFLOW_KEY = get_key("SILICONFLOW_CN_API_KEY", "SILICONFLOW_API_KEY", "SILICONFLOW_KEY")


def mask(k):
    if not k:
        return "未检测到（相关功能会降级）"
    return f"已检测到（{k[:6]}…{k[-4:]}）"


# ------------------------------------------------------------------ 转发上游
def _ssl_context():
    ctx = ssl.create_default_context()
    return ctx


def forward(upstream_url, key, body_bytes):
    """把前端 POST 的 JSON 原样转发到上游，返回 (status, content_type, raw_bytes)。"""
    if not key:
        payload = json.dumps({"error": "缺少密钥（请在环境变量或 .env 里配置对应 KEY）"}).encode()
        return 500, "application/json", payload
    req = urllib.request.Request(
        upstream_url,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            # 告知上游接受 gzip，便于我们在窄环境里也能拿到响应
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "application/json")
            return resp.status, ct, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        # 上游错误体透传给前端，方便排障
        return e.code, e.headers.get("Content-Type", "application/json"), raw
    except ssl.SSLError:
        # 个别 Windows Python 缺根证书时：本地开发工具，退一步用非校验上下文重试
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                raw = resp.read()
                return resp.status, resp.headers.get("Content-Type", "application/json"), raw
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type", "application/json"), e.read()
        except Exception as e2:  # noqa: BLE001
            payload = json.dumps({"error": f"upstream failed: {e2}"}).encode()
            return 502, "application/json", payload
    except Exception as e:  # noqa: BLE001
        payload = json.dumps({"error": f"upstream failed: {e}"}).encode()
        return 502, "application/json", payload


# ------------------------------------------------------------------ Handler
class Handler(BaseHTTPRequestHandler):
    server_version = "RagLocal/1.0"

    # --- 静默访问日志，只保留有用输出
    def log_message(self, fmt, *args):  # noqa: A003
        sys.stderr.write("  · " + (fmt % args) + "\n")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ---------- POST：代理端点 ----------
    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"

        if path == "/embeddings":
            status, ct, raw = forward(UPSTREAM["embeddings"], SILICONFLOW_KEY, body)
        elif path == "/chat/completions":
            status, ct, raw = forward(UPSTREAM["chat"], DEEPSEEK_KEY, body)
        else:
            status, ct, raw = 404, "application/json", json.dumps({"error": "not found"}).encode()

        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    # ---------- GET：静态文件（含对 RAG 页面注入 PROXY_BASE） ----------
    def do_GET(self):  # noqa: N802
        rel = unquote(urlparse(self.path).path).lstrip("/")
        if rel in ("", "/"):
            rel = "index.html"
        target = (SITE_ROOT / rel).resolve()

        # 防目录穿越
        try:
            target.relative_to(SITE_ROOT.resolve())
        except ValueError:
            self.send_error(403, "forbidden")
            return

        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            self.send_error(404, "not found")
            return

        # RAG 页面：注入本地代理地址
        try:
            is_rag_page = target.relative_to(SITE_ROOT.resolve()).as_posix() == RAG_PAGE_REL
        except ValueError:
            is_rag_page = False

        if is_rag_page:
            html = target.read_text(encoding="utf-8")
            base = f"http://127.0.0.1:{self.server.server_port}"
            html = html.replace("__PROXY_BASE__", base)
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        ctype, _ = mimetypes.guess_type(str(target))
        ctype = ctype or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class RagServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    load_dotenv(HERE / ".env")
    # 重新读取（.env 可能补上了之前没有的 key）
    global DEEPSEEK_KEY, SILICONFLOW_KEY
    DEEPSEEK_KEY = get_key("DEEPSEEK_API_KEY", "DEEPSEEK_KEY")
    SILICONFLOW_KEY = get_key("SILICONFLOW_CN_API_KEY", "SILICONFLOW_API_KEY", "SILICONFLOW_KEY")

    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    url = f"http://127.0.0.1:{port}/" + RAG_PAGE_REL
    print("=" * 64)
    print(" 个人知识 RAG 助手 · 本地运行器")
    print("=" * 64)
    print(f"  静态目录 : {SITE_ROOT}")
    print(f"  DeepSeek : {mask(DEEPSEEK_KEY)}   → 生成回答")
    print(f"  硅基流动 : {mask(SILICONFLOW_KEY)}   → 向量语义检索")
    if not SILICONFLOW_KEY:
        print("   （无硅基流动 key 也没关系：检索会自动降级为中文 BM25，仍能按语义命中）")
    print("-" * 64)
    print(f"  用浏览器打开 →  {url}")
    print("  按 Ctrl+C 停止")
    print("=" * 64)

    httpd = RagServer(("127.0.0.1", port), Handler)
    httpd.server_port = port
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")
        httpd.shutdown()


if __name__ == "__main__":
    main()
