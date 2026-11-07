"""
站点统一图表规范 v1.0（2026-10-09定稿）
=========================================
所有面向访客的图表（首页缩略图、项目页配图、文章插图）共用这一套样式，
由 tools/redraw_charts.py 调用；今后新增图表也 import 本模块，不再各画各的。

规范要点：
  · 画幅      16:9 —— figsize=(7.2, 4.05)，dpi=200 → 1440×810。
              与首页 .p-thumb 卡位同比例，object-fit:contain 时四周无白边。
  · 画布底色  #FBF9F3（暖白），与首页图框背景一致，contain 留白不可见。
  · 色板      深青 #1F5F5B 主色（主线/正确/良好）
              赭   #B5651D 强调（第二系列/强调标注）
              砖红 #A8442A 语义红（失败/过拟合，克制使用）
              暖沙 #CFC8B8 中性填充（障碍物/参照柱）
              线 #D6D1C3 网格 · 次级文字 #6E6A60 · 墨 #1A1B18 标题
  · 字体      Noto Sans SC（fonts/_src_cache 下的 TTF，本地注册，离线可用）
  · 图注      结论与「来源行」不画进图里——写在 HTML 的 .p-cap 图注行，
              PNG 保持干净、读屏可及、改文案不必重绘图。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ---- 色板（与站点 CSS 变量同源）----
PAPER = "#EFEBE1"        # 站点底色（图内不用，仅备注）
BG = "#FBF9F3"           # 图表画布底色 == 首页 .p-thumb 背景
INK = "#1A1B18"
INK_SOFT = "#3A3B36"
MUTED = "#6E6A60"
LINE = "#D6D1C3"
AXIS = "#B9B4A6"
ACCENT = "#1F5F5B"       # 深青
ACCENT_DEEP = "#16443F"
WARN = "#B5651D"         # 赭
BAD = "#A8442A"          # 语义红（失败/过拟合）
SAND = "#CFC8B8"         # 暖沙（中性填充）

# 画幅：16:9，与首页 .p-thumb 一致
FIG_W, FIG_H, DPI = 7.2, 4.05, 200

_FONTS = Path(__file__).resolve().parents[1] / "fonts" / "_src_cache"
_font_ready = False

# 深青单色渐变（混淆矩阵等热图用）
CMAP_TEAL = LinearSegmentedColormap.from_list(
    "site_teal", ["#FFFFFF", "#DCE9E6", "#7FA9A3", ACCENT, ACCENT_DEEP]
)


def setup() -> None:
    """注册中文字体并应用全局 rcParams；可重复调用。"""
    global _font_ready
    if not _font_ready:
        for w in (400, 500, 700):
            f = _FONTS / f"NotoSansSC-{w}.ttf"
            if f.exists():
                matplotlib.font_manager.fontManager.addfont(str(f))
        _font_ready = True
    matplotlib.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "font.family": "Noto Sans SC",
        "font.size": 11,
        "axes.unicode_minus": False,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.9,
        "axes.labelcolor": INK_SOFT,
        "axes.labelsize": 12,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.titlepad": 12,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "grid.color": LINE,
        "grid.linewidth": 0.8,
    })


def new_fig(w: float = FIG_W, h: float = FIG_H):
    """按规范画幅新建 figure。"""
    setup()
    return plt.subplots(figsize=(w, h))


def clean(ax, ygrid: bool = True, xgrid: bool = False) -> None:
    """隐藏上/右脊线，按需开单向网格（规范：网格只单向、颜色 #D6D1C3）。"""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ygrid:
        ax.yaxis.grid(True, color=LINE, linewidth=0.8)
    if xgrid:
        ax.xaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, path: str | Path) -> Path:
    """按规范 dpi 落盘 PNG，返回实际路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"  ✓ {path.name}  {path.stat().st_size//1024} KB")
    return path


def to_webp(png_path: str | Path, quality: int = 85, lossless: bool = False) -> Path:
    """PNG → WebP（页面统一引用 WebP，PNG 只作重绘源）。
    图表与截图用 lossless=True：文字保持锐利，体积仍能减到 PNG 的一半以下。"""
    from PIL import Image

    png_path = Path(png_path)
    webp = png_path.with_suffix(".webp")
    im = Image.open(png_path)
    if lossless:
        im.convert("RGB").save(webp, "WEBP", lossless=True, method=6)
    else:
        im.save(webp, "WEBP", quality=quality, method=6)
    print(f"  ✓ {webp.name}  {webp.stat().st_size//1024} KB")
    return webp
