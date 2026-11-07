#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
字体字形覆盖守卫
--------------------------------
站内字体是用 pyftsubset 子集化过的（见 fonts/ 下 13 个 woff2）。
子集只保留了生成时传入的字符，所以**改完文案必须重跑子集**，
否则新出现的字会渲染成豆腐块（□）。这个脚本就是防止忘记重跑。

用法：
    python tools/check_font_coverage.py            # 检查，有问题时退出码 1
    python tools/check_font_coverage.py --verbose  # 额外打印每个字体的覆盖明细

建议挂到 pre-push：
    echo 'python tools/check_font_coverage.py' >> .git/hooks/pre-push
"""
import html
import io
import os
import re
import sys
import glob
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "fonts")

# 这些字符不需要字形，直接排除
SKIP = set("\t\n\r \xa0\u200b\u200e\u200f\ufeff")

# 这些码位段本来就不在 Google Fonts 的文本字体里，浏览器会用系统 emoji /
# 符号字体回退，属于正常渲染，不算缺字：
#   U+2600–U+27BF  杂项符号与装饰符号（✓ ✅ ★ ☕ 等）
#   U+2B00–U+2BFF  杂项符号与箭头 II
#   U+1F000–       表情符号
#   U+FE0F         变体选择符
# 需要保留检查的邻近区段：U+2190–U+21FF 箭头、U+2460–U+24FF 带圈数字、
# U+25A0–U+25FF 几何形状（● ■ □）、U+4E00 起的全部汉字。
def is_system_fallback(c):
    o = ord(c)
    return (0x2600 <= o <= 0x27BF) or (0x2B00 <= o <= 0x2BFF) \
        or o >= 0x1F000 or o == 0xFE0F

TAG_RE = re.compile(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*>([\s\S]*?)</script>", re.I)
STYLE_RE = re.compile(r"<style\b[^>]*>([\s\S]*?)</style>", re.I)
STR_RE = re.compile(r"'([^'\\\n]{0,400})'|\"([^\"\\\n]{0,400})\"")
CONTENT_RE = re.compile(r"content\s*:\s*(?:\+?\s*)?[\"']([^\"']+)[\"']")


def visible_chars(text):
    """从一份 HTML 里抽出所有可能被渲染出来的字符。"""
    out = set()

    # 1) 可见文本节点（去掉 script/style 与标签，再解实体）
    body = TAG_RE.sub(" ", text)
    body = re.sub(r"<[^>]+>", " ", body)
    for ch in html.unescape(body):
        out.add(ch)

    # 2) 脚本里的字符串字面量（例如雷达图标签是 JS 画到 canvas 上的）
    for m in SCRIPT_RE.finditer(text):
        for s1, s2 in STR_RE.findall(m.group(1)):
            for ch in (s1 or s2):
                out.add(ch)

    # 3) CSS 的 content 伪元素文本
    for m in STYLE_RE.finditer(text):
        for lit in CONTENT_RE.findall(m.group(1)):
            for ch in lit:
                out.add(ch)

    return {c for c in out if c not in SKIP and ord(c) >= 0x20
            and not is_system_fallback(c)}


def font_cmap(path):
    """返回该字体实际包含的字符集合（cmap 的键是整数码位，必须转成字符再比）。"""
    try:
        f = TTFont(path, fontNumber=0, lazy=True)
        cps = {chr(c) for c in f.getBestCmap().keys()}
        f.close()
        return cps
    except Exception as exc:  # noqa: BLE001
        print("  ! 无法读取 %s: %s" % (os.path.basename(path), exc))
        return set()


def main():
    verbose = "--verbose" in sys.argv

    fonts = sorted(glob.glob(os.path.join(FONT_DIR, "*.woff2")))
    if not fonts:
        print("找不到 fonts/*.woff2 —— 字体目录被移走了？")
        return 2

    covered = set()
    per_font = {}
    for fp in fonts:
        cps = font_cmap(fp)
        per_font[os.path.basename(fp)] = cps
        covered |= cps

    used = set()
    per_page = {}
    pages = set(glob.glob(os.path.join(ROOT, "*.html")))
    for sub in ("projects", "writing"):
        pages |= set(glob.glob(os.path.join(ROOT, sub, "*.html")))
    for path in sorted(pages):
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        chars = visible_chars(io.open(path, encoding="utf-8").read())
        per_page[rel] = chars
        used |= chars

    missing = sorted(used - covered)

    print("字体子集：%d 个文件，覆盖 %d 个码位" % (len(fonts), len(covered)))
    print("站内用字：%d 个（含 JS 字符串与 CSS content）" % len(used))

    if verbose:
        for name, cps in per_font.items():
            print("  %-28s %5d 字形" % (name, len(cps)))

    if not missing:
        print("\n[PASS] 所有用字都有字形覆盖。")
        return 0

    print("\n[FAIL] 以下 %d 个字符没有任何字体包含，会显示成豆腐块：" % len(missing))
    print("  " + " ".join(missing))
    print("\n出现在：")
    for rel, chars in sorted(per_page.items()):
        hit = sorted(chars & set(missing))
        if hit:
            print("  %-34s %s" % (rel, "".join(hit)))
    print("\n修法：重跑子集生成脚本（tools/subset_fonts.py 或等价流程），"
          "把新的字符集喂给 pyftsubset 后再提交。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
