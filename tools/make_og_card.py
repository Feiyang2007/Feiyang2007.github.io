from PIL import Image, ImageDraw, ImageFont
import os

# 用法：python tools/make_og_card.py   （重画长文的社交分享卡 1200x630）
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

W, H = 1200, 630
PAPER = (239, 235, 225)
PAPERW = (245, 242, 234)
MUT = (110, 106, 96)
LINE = (214, 209, 195)
ACC = (31, 95, 91)
ACCD = (22, 68, 63)
WARN = (181, 101, 29)

VF = r"C:/Windows/Fonts/NotoSerifSC-VF.ttf"
SANS = r"C:/Windows/Fonts/Noto Sans SC (TrueType).otf"
SANSB = r"C:/Windows/Fonts/Noto Sans SC Bold (TrueType).otf"


def serif(size, weight=700):
    f = ImageFont.truetype(VF, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def sans(size, bold=False):
    return ImageFont.truetype(SANSB if bold else SANS, size)


im = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(im)

# ---------- right panel: two real rollout frames ----------
pw = 452
pad = 56
fw = pw - pad * 2
CAP = 26          # caption box height
GAP = 16          # gap between caption and next frame
frames = []
for src, cap in [("writing/img/w_ep00_fail_poster.jpg", "zero-shot · ep00 失败"),
                 ("writing/img/w_wrist_success_poster.jpg", "LoRA · ep00 成功")]:
    a = Image.open(src).convert("RGB")
    fh = int(fw * a.size[1] / a.size[0])
    a = a.resize((fw, fh), Image.LANCZOS)
    frames.append((a, cap, fh))

block = lambda f: f[2] + CAP
total_h = sum(block(f) for f in frames) + GAP * (len(frames) - 1)
top = (H - total_h) // 2
d.rectangle([(W - pw, 0), (W, H)], fill=PAPERW)
d.line([(W - pw, 0), (W - pw, H)], fill=LINE, width=1)
y = top
for idx, (a, cap, fh) in enumerate(frames):
    d.rectangle([(W - pw + pad - 1, y - 1), (W - pw + pad + fw, y + fh)], outline=LINE, width=1)
    im.paste(a, (W - pw + pad, y))
    d.text((W - pw + pad, y + fh + 7), cap, font=sans(15), fill=MUT)
    y += fh + CAP + GAP

L, R = 72, W - pw - 46

# ---------- kicker ----------
d.text((L, 64), "复现手记 001 / WRITING", font=sans(19, True), fill=WARN)
d.line([(L, 96), (L + 132, 96)], fill=WARN, width=3)

# ---------- title ----------
y = 126
for txt, size in [("AutoBio 复现笔记", 48),
                  ("单张 RTX 5090 + 5000 步 LoRA", 29),
                  ("成功率从 0% 做到 90%", 40)]:
    d.text((L, y), txt, font=serif(size, 700), fill=ACCD)
    y += int(size * 1.44)

# ---------- subtitle ----------
y += 10
d.text((L, y), "修复上游冻结快照 · π0 LoRA 微调 · 同种子对照评测", font=sans(19), fill=MUT)

# ---------- stat row ----------
y += 54
stats = [("0% → 90%", "zero-shot → LoRA"),
         ("≈ 1/200", "对比上游训练算力"),
         ("11 条", "踩坑实录")]
cw = max(150, (R - L) // len(stats))
for i, (n, l) in enumerate(stats):
    x = L + i * cw
    d.line([(x, y), (x, y + 64)], fill=LINE, width=2)
    d.text((x + 16, y + 1), n, font=serif(28, 600), fill=ACC)
    d.text((x + 16, y + 42), l, font=sans(14), fill=MUT)

# ---------- footer ----------
d.text((L, H - 62), "feiyang2007.github.io/writing/", font=sans(18), fill=MUT)
d.text((L, H - 36), "陈斐阳 · Feiyang Chen", font=sans(15), fill=LINE)

im.save("writing/img/og_autobio-lora.png", "PNG", optimize=True)
print("ok", im.size)
