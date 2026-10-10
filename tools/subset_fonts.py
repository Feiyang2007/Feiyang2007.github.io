#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全站字体子集化重建
--------------------------------
从 Google Fonts 取回完整 TTF，用 pyftsubset 裁成「只含站内实际用到的字」的
woff2，输出到 fonts/ 并重写 fonts.css。

为什么需要它：字体是子集化的，**改完文案若不重跑，新出现的字会变成豆腐块**。
配套 tools/check_font_coverage.py 会在缺字时报警，这个脚本负责把它修好。

用法：
    python tools/subset_fonts.py            # 下载 + 子集化 + 重写 fonts.css
    python tools/subset_fonts.py --offline  # 用 fonts/_src_cache 里已下载的 TTF 重跑
    python tools/subset_fonts.py --dry-run  # 只算字符集和预计体积，不写文件

源 TTF 会缓存到 fonts/_src_cache/（已 gitignore，不要提交）。
"""
import glob
import io
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_font_coverage import visible_chars, ROOT, FONT_DIR  # noqa: E402

UA = "curl/8.0"          # 朴素 UA 才会拿到单一完整 TTF，而不是 woff2 分片
CACHE = os.path.join(FONT_DIR, "_src_cache")

# (CSS 家族名, 输出文件前缀, {字重: css2 family 参数})
FAMILIES = [
    ("IBM Plex Mono", "IBMPlexMono", {400: "IBM+Plex+Mono:wght@400", 500: "IBM+Plex+Mono:wght@500"}),
    ("Noto Sans SC", "NotoSansSC", {w: "Noto+Sans+SC:wght@%d" % w for w in (300, 400, 500, 700)}),
    ("Noto Serif SC", "NotoSerifSC", {w: "Noto+Serif+SC:wght@%d" % w for w in (400, 600, 700)}),
    ("Source Serif 4", "SourceSerif4",
     {w: "Source+Serif+4:opsz,wght@8..60,%d" % w for w in (400, 500, 600, 700)}),
]

# 额外生成的真斜体（hero-en 用）：不做子集的话浏览器会给衬线英文合成伪斜体，观感毛糙
ITALIC_FAMILIES = [
    ("Source Serif 4", "SourceSerif4-Italic", "italic",
     {400: "Source+Serif+4:ital,opsz,wght@1,8..60,400"}),
]

# 无论页面里有没有用到，这些字符都必须留着
BASELINE = (
    "".join(chr(c) for c in range(0x20, 0x7F))          # ASCII 可见
    + "\u00a0\u00b7\u00d7\u00b1\u00b0\u2014\u2013\u2018\u2019\u201c\u201d"
    + "\u2026\u2192\u2190\u2191\u2193\u2264\u2265\u2248\u221e\u00a9\u2192"
    + "\u3001\u3002\u300c\u300d\u300e\u300f\u3010\u3011\u3014\u3015"
    + "\uff01\uff08\uff09\uff0c\uff1a\uff1b\uff1f\uff5e\u25cf\u2500\u2022"
    + "\u00e9\u00e8\u00ea\u00e0\u00fc\u00f6\u00e4\u00df"                  # 西欧字母
    + "\u25b6"                                          # ▶ 项目卡「可交互」标记
)


def site_charset():
    chars = set(BASELINE)
    pages = set(glob.glob(os.path.join(ROOT, "*.html")))
    for sub in ("projects", "writing"):
        pages |= set(glob.glob(os.path.join(ROOT, sub, "*.html")))
    for p in sorted(pages):
        chars |= visible_chars(io.open(p, encoding="utf-8").read())
    # 训练/评测文本里常见的下划线与连接符
    chars |= set("_-/\\.,:;!?()[]{}<>=+*/%$#@&|~^'\"`")
    return {c for c in chars if not unicodedata_control(c)}


def unicodedata_control(c):
    return ord(c) < 0x20 or ord(c) == 0x7f


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=120).read()
    io.open(dest, "wb").write(data)
    return len(data)


def ttf_url(fam_spec):
    api = "https://fonts.googleapis.com/css2?family=%s&display=swap" % fam_spec
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    css = urllib.request.urlopen(req, timeout=60).read().decode()
    m = re.search(r"url\((https://[^)]+?\.ttf)\)", css)
    if not m:
        raise RuntimeError("没在 CSS 里找到 TTF 地址：%s\n%s" % (fam_spec, css[:400]))
    return m.group(1)


def subset(src_ttf, out_woff2, text_file):
    cmd = [sys.executable, "-m", "fontTools.subset", src_ttf,
           "--text-file=%s" % text_file,
           "--flavor=woff2",
           "--output-file=%s" % out_woff2,
           "--layout-features=*",
           "--hinting=False",
           "--desubroutinize",
           "--no-glyph-names",
           "--drop-tables+=DSIG"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("pyftsubset 失败：%s\n%s" % (out_woff2, r.stderr[-800:]))


def main():
    offline = "--offline" in sys.argv
    dry = "--dry-run" in sys.argv

    chars = site_charset()
    text_file = os.path.join(FONT_DIR, "_charset.txt")
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    print("字符集：%d 个码位（其中汉字 %d）" % (len(chars), cjk))

    if dry:
        print("--dry-run：不下载、不写文件")
        return 0

    io.open(text_file, "w", encoding="utf-8").write("".join(sorted(chars)))
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)

    made = []
    jobs = [(f, p, "normal", w) for f, p, w in FAMILIES] + ITALIC_FAMILIES
    for family, prefix, style, weights in jobs:
        for w, spec in sorted(weights.items()):
            out = os.path.join(FONT_DIR, "%s-%d.woff2" % (prefix, w))
            cached = os.path.join(CACHE, "%s-%d.ttf" % (prefix, w))
            if os.path.exists(cached):
                src = cached
            elif offline:
                print("  ! 缺少缓存 %s，跳过（去掉 --offline 以联网下载）" % cached)
                continue
            else:
                url = ttf_url(spec)
                n = fetch(url, cached)
                print("  ↓ %-26s %6.1f MB 源 TTF" % ("%s-%d" % (prefix, w), n / 1048576.0))
                src = cached
            subset(src, out, text_file)
            made.append((family, w, style, out))
            print("  ✓ %-26s %6.0f KB" % (os.path.basename(out), os.path.getsize(out) / 1024.0))

    if not made:
        print("没有生成任何字体，fonts.css 保持不变")
        return 1

    lines = ["/* 自动生成：全站用字子集化字体（来源 Google Fonts, OFL license）。"
             "改页面文案后重跑 tools/subset_fonts.py */"]
    for family, w, style, out in made:
        lines.append("@font-face{font-family:'%s';font-style:%s;font-weight:%d;"
                     "font-display:swap;src:url('%s') format('woff2')}"
                     % (family, style, w, os.path.basename(out)))
    io.open(os.path.join(FONT_DIR, "fonts.css"), "w", encoding="utf-8",
            newline="\n").write("\n".join(lines) + "\n")

    total = sum(os.path.getsize(o) for _, _, _, o in made)
    print("\n完成：%d 个 woff2，合计 %.2f MB；fonts.css 已重写" % (len(made), total / 1048576.0))
    print("下一步：python tools/check_font_coverage.py 复核")
    return 0


if __name__ == "__main__":
    sys.exit(main())
