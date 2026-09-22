/**
 * RAG 代理 Worker —— 为 feiyang2007.github.io 的个人知识 RAG 助手做后端转发
 *
 * 作用：把前端请求安全转发到 DeepSeek(生成) 与 硅基流动(嵌入)，
 *       两个密钥以 Secret 形式存在 Worker 环境变量里，前端源码零密钥。
 *       并做服务端按 IP 的小时级限流，防止公开端点被盗刷额度。
 *
 * 需要的环境变量（wrangler secret put）：
 *   DEEPSEEK_KEY      DeepSeek API Key (sk-...)
 *   SILICONFLOW_KEY   硅基流动 API Key (sk-...)
 *   ALLOW_ORIGIN      可选，允许跨域的前端源；默认 "*"，生产建议填
 *                     https://feiyang2007.github.io
 * [vars]：
 *   RATE_LIMIT_PER_HOUR  每个 IP 每小时最多调用次数（默认 60）
 * 绑定：
 *   COUNTERS (KV)        存放按 IP 的计数
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

function clientIP(request) {
  // Cloudflare 提供 cf-connecting-ip；兜底再取 X-Forwarded-For 第一段
  const cf = request.headers.get("cf-connecting-ip");
  if (cf) return cf;
  const xff = request.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return "unknown";
}

/**
 * 按 IP 的小时窗口计数限流。KV 最终一致，作为"软上限"足够挡住盗刷。
 * 返回 null 表示放行；返回 Response 表示已限流（429）。
 */
async function enforceRateLimit(env, request) {
  const limit = parseInt(env.RATE_LIMIT_PER_HOUR || "60", 10);
  if (!limit || limit <= 0 || !env.COUNTERS) return null; // 未配置则不限流
  const ip = clientIP(request);
  const window = Math.floor(Date.now() / 3600000); // 每小时一个窗口
  const key = `rl:${ip}:${window}`;
  let count = 0;
  try {
    const cur = await env.COUNTERS.get(key);
    count = cur ? parseInt(cur, 10) : 0;
  } catch (e) {
    return null; // KV 读失败时不误伤正常请求
  }
  if (count >= limit) {
    return new Response(
      JSON.stringify({ error: "rate limited: 该 IP 本小时调用已达上限，请稍后再试" }),
      { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "3600" } }
    );
  }
  try {
    // expirationTtl 最小 60s；这里给足一个小时的余量
    await env.COUNTERS.put(key, String(count + 1), { expirationTtl: 3700 });
  } catch (e) {
    /* 写失败忽略，不阻断请求 */
  }
  return null;
}

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

    // 服务端限流（按 IP）
    const limited = await enforceRateLimit(env, request);
    if (limited) {
      return new Response(limited.body, { status: limited.status, headers: { ...cors, "Content-Type": "application/json", "Retry-After": "3600" } });
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
