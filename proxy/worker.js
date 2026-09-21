/**
 * RAG 代理 Worker —— 为 feiyang2007.github.io 的个人知识 RAG 助手做后端转发
 *
 * 作用：把前端请求安全转发到 DeepSeek(生成) 与 硅基流动(嵌入)，
 *       两个密钥以 Secret 形式存在 Worker 环境变量里，前端源码零密钥。
 *
 * 需要的环境变量（用 wrangler secret put 或 Dashboard 设置）：
 *   DEEPSEEK_KEY      DeepSeek API Key (sk-...)
 *   SILICONFLOW_KEY   硅基流动 API Key (sk-...)
 *   ALLOW_ORIGIN      可选，允许跨域的前端源；默认用 "*"，生产建议填
 *                     https://feiyang2007.github.io
 *
 * 路由：
 *   POST /embeddings        -> 硅基流动 /v1/embeddings
 *   POST /chat/completions  -> DeepSeek   /v1/chat/completions
 *   OPTIONS *               -> CORS 预检
 */

const UPSTREAM = {
  embeddings: "https://api.siliconflow.cn/v1/embeddings",
  chat: "https://api.deepseek.com/v1/chat/completions",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    const cors = {
      "Access-Control-Allow-Origin": env.ALLOW_ORIGIN || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    };

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST")
      return new Response("method not allowed", { status: 405, headers: cors });

    // 路径 -> (上游地址, 对应密钥)
    let target, key;
    if (url.pathname === "/embeddings") {
      target = UPSTREAM.embeddings; key = env.SILICONFLOW_KEY;
    } else if (url.pathname === "/chat/completions") {
      target = UPSTREAM.chat; key = env.DEEPSEEK_KEY;
    } else {
      return new Response("not found", { status: 404, headers: cors });
    }
    if (!key) {
      return new Response(JSON.stringify({ error: "worker secret not configured: " + url.pathname }),
        { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const body = await request.text();
    let upstream;
    try {
      upstream = await fetch(target, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
        body,
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: "upstream fetch failed: " + e.message }),
        { status: 502, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { ...cors, "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
    });
  },
};
