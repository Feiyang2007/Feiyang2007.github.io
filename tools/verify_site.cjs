/* 全站体检：真实 DOM 渲染 + 资源存在性 + 内链 + a11y + 红线
 * 用法：node tools/verify_site.cjs   （需要 devDependency jsdom）
 * 必须用 jsdom 真跑脚本——假 stub 会掩盖 bug。 */
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.join(__dirname, "..");
process.chdir(ROOT);   // 下面全部按站内相对路径处理

const PAGES = ["index.html", "index-en.html"]
  .concat(fs.readdirSync("projects").filter(f => f.endsWith(".html")).map(f => "projects/" + f))
  .concat(fs.readdirSync("writing").filter(f => f.endsWith(".html")).map(f => "writing/" + f))
  .filter(f => !f.startsWith("googleb"));

let pass = 0, fail = 0;
const fails = [];
function ok(name) { pass++; }
function bad(name, why) { fail++; fails.push(name + " :: " + why); }
function check(name, cond, why) { cond ? ok(name) : bad(name, why || "condition false"); }

/* Canvas 2D 用 Proxy 兜住所有方法，避免雷达图脚本在 jsdom 里静默抛错 */
function canvasStub() {
  const noop = () => {};
  const ctx = new Proxy({}, {
    get(t, k) {
      if (k === "canvas") return { width: 520, height: 430 };
      if (k === "measureText") return () => ({ width: 10 });
      if (k === "createLinearGradient") return () => ({ addColorStop: noop });
      if (k in t) return t[k];
      return noop;
    },
    set(t, k, v) { t[k] = v; return true; }
  });
  return ctx;
}

function load(file) {
  const html = fs.readFileSync(file, "utf8");
  const vc = new VirtualConsole();
  const errors = [];
  vc.on("jsdomError", e => errors.push(String(e.message || e)));
  vc.on("error", (...a) => errors.push(a.join(" ")));
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    pretendToBeVisual: true,
    url: "https://feiyang2007.github.io/" + file,
    virtualConsole: vc,
    beforeParse(w) {
      w.HTMLCanvasElement.prototype.getContext = canvasStub;
      // jsdom 未实现媒体元素：真浏览器里 play() 返回 promise 且已被 catch，
      // 这里补一个 resolve 的桩，避免把环境限制误报成页面 bug。
      w.HTMLMediaElement.prototype.play = () => Promise.resolve();
      w.HTMLMediaElement.prototype.pause = () => {};
      w.IntersectionObserver = class {
        constructor(cb) { this.cb = cb; this.els = []; }
        observe(el) { this.els.push(el); this.cb([{ isIntersecting: true, target: el }], this); }
        unobserve() {} disconnect() {}
      };
      w.requestAnimationFrame = cb => setTimeout(() => cb(Date.now()), 0);
    }
  });
  return { dom, doc: dom.window.document, html, errors };
}

/* ---------- 1. 资源与内链存在性 ---------- */
const refRe = /(?:src|href|poster)="([^"]+)"|url\('([^']+)'\)/g;
for (const file of PAGES) {
  const dir = path.dirname(file);
  const { html } = load(file);
  const missing = [];
  let m;
  refRe.lastIndex = 0;
  while ((m = refRe.exec(html))) {
    let u = (m[1] || m[2] || "").trim();
    if (!u || /^(https?:|mailto:|data:|#|javascript:)/.test(u)) continue;
    u = u.split("#")[0].split("?")[0];
    if (!u) continue;
    const base = u.startsWith("/") ? path.join(ROOT, u) : path.resolve(ROOT, dir, u);
    if (!fs.existsSync(base)) missing.push(u);
  }
  check(file + " · 本地资源全部存在", missing.length === 0, "缺失: " + [...new Set(missing)].join(", "));

  // 站内相对链接（含 #锚点）目标页面必须存在
  const deadAnchors = [];
  for (const a of html.match(/href="[^"#]*\.html[^"]*"/g) || []) {
    const u = a.slice(6, -1).split("#")[0];
    if (!u || /^https?:/.test(u)) continue;
    if (!fs.existsSync(path.resolve(ROOT, dir, u))) deadAnchors.push(u);
  }
  check(file + " · 内链无死链", deadAnchors.length === 0, "死链: " + deadAnchors.join(", "));
}

/* ---------- 2. 标签平衡 ---------- */
for (const file of PAGES) {
  const { html } = load(file);
  const stripped = html.replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, "")
    .replace(/<(br|hr|img|input|meta|link|source|use)\b[^>]*>/gi, "");
  for (const tag of ["div", "section", "main", "table", "figure", "ul", "ol", "blockquote", "aside", "a"]) {
    const o = (stripped.match(new RegExp("<" + tag + "(?=[\\s>])", "g")) || []).length;
    const c = (stripped.match(new RegExp("</" + tag + ">", "g")) || []).length;
    if (o !== c) { bad(file + " · <" + tag + "> 平衡", `开 ${o} / 闭 ${c}`); }
  }
  ok(file + " · 标签平衡");
}

/* ---------- 3. 首页 a11y 与 Writing ---------- */
for (const [file, expect] of [
  ["index.html", { skip: "跳到正文", main: "main", writing: "写作", lang: "EN", axes: 8 }],
  ["index-en.html", { skip: "Skip to content", main: "main", writing: "Writing", lang: "中文", axes: 8 }]
]) {
  const { doc, errors } = load(file);
  check(file + " · 无脚本错误", errors.length === 0, errors.slice(0, 2).join(" | "));
  const skip = doc.querySelector("a.skip");
  check(file + " · 跳转链接存在", !!skip && skip.textContent.trim() === expect.skip, skip ? "文案不符" : "无 a.skip");
  check(file + " · 跳转目标存在", !!skip && !!doc.getElementById(skip.getAttribute("href").slice(1)), "目标 id 不存在");
  check(file + " · 恰好一个 <main>", doc.querySelectorAll("main").length === 1, "实得 " + doc.querySelectorAll("main").length);
  check(file + " · <main> 有 id", !!doc.querySelector("main#main"));
  const nav = doc.querySelectorAll("nav a");
  check(file + " · 导航含 Writing", [...nav].some(a => a.getAttribute("href") === "#writing"));
  check(file + " · 语言切换按钮", [...nav].some(a => a.textContent.trim() === expect.lang));
  const w = doc.getElementById("writing");
  check(file + " · #writing 区块存在", !!w);
  check(file + " · Writing 卡片链接到长文", !!w && !!w.querySelector('a[href="writing/autobio-pi0-lora.html"]'));
  // 雷达图回挂文本
  const cv = doc.getElementById("radar");
  check(file + " · canvas 有 role=img", !!cv && cv.getAttribute("role") === "img");
  check(file + " · canvas 有 aria-label", !!cv && (cv.getAttribute("aria-label") || "").length > 40);
  const sr = doc.querySelectorAll("canvas#radar + ul.sr-only li, ul.sr-only li");
  check(file + " · 雷达图隐藏文字 " + expect.axes + " 条", sr.length === expect.axes, "实得 " + sr.length);
  // 动效仍然工作
  const revealed = doc.querySelectorAll("section > .wrap > *.in").length;
  check(file + " · reveal 动效仍生效", revealed > 5, "仅 " + revealed + " 个元素获得 .in");
  // 区块编号连续
  const nums = [...doc.querySelectorAll(".section-label")].map(e => e.textContent.trim().slice(0, 2));
  check(file + " · 区块编号 01-09 连续", nums.join(",") === ["01","02","03","04","05","06","07","08","09"].join(","), "实得 " + nums.join(","));
}

/* ---------- 4. 长文页 ---------- */
{
  const file = "writing/autobio-pi0-lora.html";
  const { doc, errors } = load(file);
  check(file + " · 无脚本错误", errors.length === 0, errors.slice(0, 2).join(" | "));
  const strip = doc.getElementById("epstrip");
  check(file + " · 逐回合条渲染 20 格", strip && strip.children.length === 20, strip ? "实得 " + strip.children.length : "无 #epstrip");
  check(file + " · 逐回合条有 aria-label", !!strip && (strip.getAttribute("aria-label") || "").includes("90%"));
  check(file + " · 成功格数 = 18", strip && strip.querySelectorAll(".ep.ok").length === 18, strip ? "实得 " + strip.querySelectorAll(".ep.ok").length : "");
  // 目录锚点全部有对应 id
  const dead = [...doc.querySelectorAll(".toc a")].map(a => a.getAttribute("href").slice(1))
    .filter(id => !doc.getElementById(id));
  check(file + " · 目录锚点全部命中", dead.length === 0, "缺失 id: " + dead.join(","));
  // 视频
  const vids = [...doc.querySelectorAll("video")];
  check(file + " · 3 段 rollout 视频", vids.length === 3, "实得 " + vids.length);
  check(file + " · 视频均 muted+playsinline+preload=none", vids.every(v => v.hasAttribute("muted") && v.hasAttribute("playsinline") && v.getAttribute("preload") === "none"));
  check(file + " · 视频均有无障碍标签", vids.every(v => (v.getAttribute("aria-label") || "").length > 10));
  // 图片 alt
  const noAlt = [...doc.querySelectorAll("img")].filter(i => !i.getAttribute("alt"));
  check(file + " · 所有图片有 alt", noAlt.length === 0, noAlt.map(i => i.getAttribute("src")).join(","));
  // 结构化数据
  const ld = JSON.parse(doc.querySelector('script[type="application/ld+json"]').textContent);
  check(file + " · JSON-LD 为 BlogPosting", ld["@type"] === "BlogPosting");
  check(file + " · JSON-LD 作者与站内身份一致", ld.author.name === "陈斐阳" && ld.author.sameAs.length === 2);
  check(file + " · canonical 指向本页", doc.querySelector('link[rel=canonical]').href.endsWith("/writing/autobio-pi0-lora.html"));
  check(file + " · 有 <main>", doc.querySelectorAll("main").length === 1);
  check(file + " · 有跳转链接", !!doc.querySelector("a.skip"));
  // 表格未被 markdown 残留污染
  check(file + " · 无 markdown 残留", !/\*\*|!\[|^\|\s*---/m.test(doc.body.textContent.replace(/[\s\S]*$/, x => x)));
}

/* ---------- 5. 写作索引 + 旗舰页互链 ---------- */
{
  const { doc } = load("writing/index.html");
  check("writing/index.html · 卡片链到长文", !!doc.querySelector('a[href="autobio-pi0-lora.html"]'));
  check("writing/index.html · 有 <main> 与 skip", doc.querySelectorAll("main").length === 1 && !!doc.querySelector("a.skip"));
}
for (const f of ["projects/autobio-pi0.html", "projects/autobio-pi0-en.html"]) {
  const { doc } = load(f);
  check(f + " · 回链长文", !!doc.querySelector('a.read-note[href="../writing/autobio-pi0-lora.html"]'));
}

/* ---------- 6. 红线扫描（全站可见文本） ---------- */
const REDLINES = [
  [/曹云康|陈文锐/, "导师/中间人姓名"],
  [/保研|推免|绩点|GPA|排名|前\s*\d+[%％]|四级/, "保研推免排名语言"],
  [/跳板|铺路|保研资本|人脉/, "功利化表述"],
  [/调库谁都会|我连.{0,8}都手写|逼自己/, "张狂语言"],
  [/workers\.dev|Cloudflare|wrangler|SILICONFLOW|API[_ ]?KEY|Secret|CORS|限流|run_rag/, "部署与密钥细节"],
  [/127\.0\.0\.1|localhost|30-自学|C:?[Uu]sers|交接包/, "本地/内部路径"],
  [/1[3-9]\d{9}/, "手机号"],
  [/吊打|碾压|狂虐/, "夸饰语气"],
];
/* 已知合法用法，扫描前剥离；每条豁免都必须写清理由 */
const EXEMPT = [
  // openpi 官方文档的「策略服务 + 评测客户端」双进程用法，--host 127.0.0.1 是
  // 复现必需的上游命令，不属于泄露我们自己的部署细节
  [/--host 127\.0\.0\.1/g, ""],
  // 「不是吊打上游」是自我约束的口径声明，不是夸饰
  [/不是吊打/g, ""],
  // 已记录在案的待决项：RAG 演示是纯前端页面，必须直连这个 Worker 端点才能跑。
  // 只豁免这一条完整 URL——出现第二个 worker 地址或其他基础设施细节时仍会报错。
  // 彻底解决需要自定义域名反代，或把演示降级为「描述 + 仓库链接」。
  [/https:\/\/rag-proxy\.chenfeiyang20071228\.workers\.dev/g, ""],
];
for (const file of PAGES) {
  const { doc } = load(file);
  let text = doc.body.textContent + " " +
    [...doc.querySelectorAll("meta")].map(m => (m.getAttribute("content") || "")).join(" ") + " " +
    [...doc.querySelectorAll("script")].map(s => s.textContent).join(" ");
  for (const [re, sub] of EXEMPT) text = text.replace(re, sub);
  const hits = [];
  for (const [re, label] of REDLINES) {
    const m = text.match(re);
    if (m) hits.push(label + " → " + JSON.stringify(m[0]));
  }
  check(file + " · 红线扫描", hits.length === 0, hits.join(" ; "));
}

/* ---------- 汇总 ---------- */
console.log("\n通过 " + pass + " / 失败 " + fail);
if (fails.length) {
  console.log("\n失败明细：");
  fails.forEach(f => console.log("  ✗ " + f));
  process.exit(1);
}
