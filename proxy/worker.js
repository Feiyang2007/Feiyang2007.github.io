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
 *
 * 服务端钳制（该端点无鉴权、全公网可达，CORS 只能挡浏览器挡不住脚本，
 * 故转发前必须白名单重建请求体）：
 *   - 请求体 > 20 KB → 413
 *   - 带 Origin/Referer 且与 ALLOW_ORIGIN 不符 → 403
 *   - 请求体白名单重建：模型固定 deepseek-flash / BAAI/bge-m3（防调用贵价模型）、
 *     max_tokens ≤ 4000、messages ≤ 12 条且 role 受限、input ≤ 16 条
 */

const UPSTREAM = {
  embeddings: "https://api.siliconflow.cn/v1/embeddings",
  chat: "https://api.deepseek.com/v1/chat/completions",
};

const MAX_BODY_BYTES = 20000;
const MAX_TOKENS = 4000;
const MAX_MESSAGES = 12;
const MAX_EMBED_INPUTS = 16; // 前端 embedBatched 每批 12 条，留出余量
const ALLOWED_ROLES = new Set(["system", "user", "assistant"]);

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

/**
 * 来源校验：带 Origin/Referer 却不是配置的前端源 → 拒绝（防浏览器侧跨站滥用，
 * 脚本可伪造此头）。无这两个头的调用（如 curl 自检）放行，由请求体重建钳制兜底。
 */
function originOk(request, env) {
  const allowed = env.ALLOW_ORIGIN && env.ALLOW_ORIGIN !== "*" ? env.ALLOW_ORIGIN : null;
  if (!allowed) return true;
  const origin = request.headers.get("origin");
  if (origin) return origin === allowed;
  const referer = request.headers.get("referer");
  if (referer) return referer.startsWith(allowed + "/");
  return true;
}

/** 白名单重建请求体：只保留允许的字段并钳制规模；不合法返回 null */
function sanitizeChat(payload) {
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const trimmed = messages
    .filter(m => m && ALLOWED_ROLES.has(m.role) && typeof m.content === "string")
    .slice(0, MAX_MESSAGES)
    .map(m => ({ role: m.role, content: m.content }));
  if (!trimmed.length) return null;
  return {
    model: "deepseek-flash",
    messages: trimmed,
    max_tokens: Math.max(1, Math.min(parseInt(payload.max_tokens, 10) || 400, MAX_TOKENS)),
  };
}

function sanitizeEmbeddings(payload) {
  let input = payload.input;
  if (typeof input === "string") input = [input];
  if (!Array.isArray(input) || !input.length) return null;
  return {
    model: "BAAI/bge-m3",
    input: input.slice(0, MAX_EMBED_INPUTS).map(x => String(x)),
    encoding_format: "float",
  };
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

    // 路径 -> (上游地址, 对应密钥, 请求体重建器)
    let target, key, sanitizer;
    if (url.pathname === "/embeddings") {
      target = UPSTREAM.embeddings; key = env.SILICONFLOW_KEY; sanitizer = sanitizeEmbeddings;
    } else if (url.pathname === "/chat/completions") {
      target = UPSTREAM.chat; key = env.DEEPSEEK_KEY; sanitizer = sanitizeChat;
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

    if (!originOk(request, env)) {
      return new Response("forbidden origin", { status: 403, headers: cors });
    }

    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) {
      return new Response("payload too large", { status: 413, headers: cors });
    }

    let sanitized;
    try {
      sanitized = sanitizer(JSON.parse(raw));
    } catch (e) {
      sanitized = null;
    }
    if (!sanitized) {
      return new Response("bad request", { status: 400, headers: cors });
    }

    let upstream;
    try {
      upstream = await fetch(target, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
        body: JSON.stringify(sanitized),
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
