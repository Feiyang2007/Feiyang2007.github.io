"""
重绘站点图表 —— 按 chart_style v1.0 统一规格（2026-10-09）
============================================================
全部数据来自各项目 30-自学/ 下的确定性产物（固定种子 / 已存权重 / 已存日志），
不重跑训练、不改原项目文件；原图均在本 git 仓库内，可随时 diff / 回退。

产出（覆盖同名文件）：
  projects/img/  mujoco_curve / bc_curve / confusion_matrix /
                 mnist_samples / arm_rrt_result / autobio_result / d2l_fit  (.png)
  writing/img/   w_seedcmp.png + w_seedcmp.webp（原文有列名重叠 + 高饱和红绿，重制）

运行：python tools/redraw_charts.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt  # noqa: F401  （fig_mnist / fig_arm 直接用 pyplot）

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                    # site/
VAULT = ROOT.parent                   # 陈斐阳/
P_IMG = ROOT / "projects" / "img"
W_IMG = ROOT / "writing" / "img"

PPO = VAULT / "30-自学" / "具身智能" / "ppo-pendulum"
BC = VAULT / "30-自学" / "具身智能" / "behavior-cloning"
MNI = VAULT / "30-自学" / "具身智能" / "mnist-cnn"
MLP = VAULT / "30-自学" / "编程" / "projects" / "ml-pipeline"
ARM = VAULT / "30-自学" / "编程" / "projects" / "arm-planning"

sys.path.insert(0, str(HERE))
import chart_style as cs  # noqa: E402


# ================================================================ 1. MuJoCo PPO
def fig_mujoco() -> None:
    d = np.load(PPO / "reports" / "mujoco_rewards.npz")
    y = d["iter_avgs"]
    solved = int(d["solved_at"])
    x = np.arange(1, len(y) + 1)

    fig, ax = cs.new_fig()
    cs.clean(ax, ygrid=True)
    ax.plot(x, y, color=cs.ACCENT, lw=2.4)
    ax.axhline(900, color=cs.MUTED, ls=(0, (5, 4)), lw=1.1)
    ax.text(2, 916, "达标线 900", fontsize=10.5, color=cs.MUTED)
    ax.axvline(solved, color=cs.WARN, ls=":", lw=1.5)
    ax.annotate(f"第 {solved} 次迭代达标",
                xy=(solved, float(y[-1])), xytext=(solved - 21, 760),
                fontsize=11, color=cs.WARN,
                arrowprops=dict(arrowstyle="->", color=cs.WARN, lw=1.1))
    ax.set_xlim(0, len(y) + 2)
    ax.set_ylim(0, 1000)
    ax.set_xlabel("PPO 迭代（每迭代 2048 步）")
    ax.set_ylabel("近 100 回合平均回报")
    ax.set_title("自实现 PPO · MuJoCo InvertedPendulum 训练曲线")
    cs.save(fig, P_IMG / "mujoco_curve.png")


# ================================================================ 2. 行为克隆
def fig_bc() -> None:
    """与 30-自学/具身智能/behavior-cloning/behavior_cloning.py 同一流程、同种子，
    原脚本未落盘逐轮历史，这里按相同管线复算一遍（SEED=0，确定性）。"""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset
    import gymnasium as gym

    SEED, N_DEMO, EXPERT_KP, EXPERT_KD = 0, 300, 12.0, 10.0

    def expert_action(s):
        _, _, th, thd = s
        return 1 if (EXPERT_KP * th + EXPERT_KD * thd) > 0 else 0

    env = gym.make("CartPole-v1")
    states, actions = [], []
    for ep in range(N_DEMO):
        s, _ = env.reset(seed=SEED + ep)
        while True:
            a = expert_action(s)
            states.append(s.copy())
            actions.append(a)
            s, _, term, trunc, _ = env.step(a)
            if term or trunc:
                break
    X = np.array(states, np.float32)
    y = np.array(actions, np.int64)

    np.random.seed(SEED)
    torch.manual_seed(SEED)
    n = len(X)
    idx = np.random.default_rng(SEED).permutation(n)
    nval = int(n * 0.2)
    vi, ti = idx[:nval], idx[nval:]
    Xtr, ytr = torch.tensor(X[ti]), torch.tensor(y[ti])
    Xva, yva = torch.tensor(X[vi]), torch.tensor(y[vi])
    loader = DataLoader(TensorDataset(Xtr, ytr), batch_size=128, shuffle=True)

    model = nn.Sequential(nn.Linear(4, 64), nn.ReLU(),
                          nn.Linear(64, 64), nn.ReLU(),
                          nn.Linear(64, 2))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_h, acc_h = [], []
    for _ in range(60):
        model.train()
        tot = 0.0
        for xb, yb in loader:
            loss = F.cross_entropy(model(xb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(xb)
        model.eval()
        with torch.no_grad():
            acc = (model(Xva).argmax(1) == yva).float().mean().item()
        loss_h.append(tot / len(Xtr))
        acc_h.append(acc)
    ep = np.arange(1, 61)
    print(f"  BC 复算：末轮 loss {loss_h[-1]:.4f} · val_acc {acc_h[-1]:.4f}")

    fig, ax1 = cs.new_fig()
    cs.clean(ax1, ygrid=True)
    ax2 = ax1.twinx()
    ax2.spines["top"].set_visible(False)
    l1, = ax1.plot(ep, loss_h, color=cs.ACCENT, lw=2.2, label="训练损失（交叉熵，左轴）")
    l2, = ax2.plot(ep, acc_h, color=cs.WARN, lw=2.2, label="验证动作准确率（右轴）")
    ax1.set_xlabel("训练轮次（epoch）")
    ax1.set_ylabel("交叉熵损失", color=cs.ACCENT)
    ax1.tick_params(axis="y", labelcolor=cs.ACCENT)
    ax1.set_ylim(0, 0.36)
    ax2.set_ylabel("验证动作准确率", color=cs.WARN)
    ax2.tick_params(axis="y", labelcolor=cs.WARN)
    ax2.set_ylim(0.5, 1.0)
    ax1.set_title("行为克隆 · 模仿 PD 专家（CartPole 示教数据）")
    ax1.legend(handles=[l1, l2], loc="center right", frameon=False, fontsize=10.5)
    cs.save(fig, P_IMG / "bc_curve.png")


# ================================================================ 3. UCI-HAR 混淆矩阵
def fig_confusion() -> None:
    import joblib
    from sklearn.metrics import confusion_matrix

    sys.path.insert(0, str(MLP))
    from data_loader import load_har, feature_columns  # noqa: E402

    model = joblib.load(MLP / "model.joblib")
    meta = json.loads((MLP / "metrics.json").read_text(encoding="utf-8"))
    train_df, test_df = load_har()
    feats = meta.get("feature_cols") or feature_columns(train_df)
    X_te = test_df[feats].to_numpy(np.float64)
    y_te = test_df["activity"].to_numpy()
    pred = model.predict(X_te)

    classes = sorted(set(y_te))
    zh = {"LAYING": "平躺", "SITTING": "坐", "STANDING": "站",
          "WALKING": "走路", "WALKING_DOWNSTAIRS": "下楼", "WALKING_UPSTAIRS": "上楼"}
    cm = confusion_matrix(y_te, pred, labels=classes)
    acc = float((pred == y_te).mean())
    recall = np.diag(cm) / cm.sum(axis=1)

    fig, ax0 = cs.new_fig()
    ax0.remove()  # 去掉 new_fig 自带的占位坐标轴，避免幽灵刻度
    gs = fig.add_gridspec(1, 2, width_ratios=[1.18, 1], wspace=0.24,
                          left=0.09, right=0.965, top=0.82, bottom=0.13)
    a1 = fig.add_subplot(gs[0])
    a2 = fig.add_subplot(gs[1])

    a1.imshow(cm, cmap=cs.CMAP_TEAL, aspect="equal")
    n = len(classes)
    a1.set_xticks(range(n))
    a1.set_yticks(range(n))
    a1.set_xticklabels([zh[c] for c in classes], fontsize=11, color=cs.INK_SOFT)
    a1.set_yticklabels([zh[c] for c in classes], fontsize=11, color=cs.INK_SOFT)
    a1.tick_params(length=0)
    for s in a1.spines.values():
        s.set_visible(False)
    thresh = cm.max() * 0.55
    for i in range(n):
        for j in range(n):
            v = cm[i, j]
            a1.text(j, i, str(int(v)), ha="center", va="center", fontsize=10.5,
                    color="white" if v > thresh else cs.INK_SOFT)
    a1.set_xlabel("预测类别")
    a1.set_ylabel("真实类别")

    ypos = np.arange(n)[::-1]
    a2.barh(ypos, recall, color=cs.WARN, height=0.62)
    for yy, r in zip(ypos, recall):
        a2.text(r + 0.004, yy, f"{r:.1%}", va="center", fontsize=10.5, color=cs.INK_SOFT)
    a2.set_yticks(ypos)
    a2.set_yticklabels([zh[c] for c in classes], fontsize=11, color=cs.INK_SOFT)
    a2.set_xlim(0.72, 1.04)
    a2.set_xticks([0.8, 0.9, 1.0])
    a2.set_xticklabels(["80%", "90%", "100%"])
    cs.clean(a2, xgrid=True, ygrid=False)
    a2.set_title("各类别召回率", fontsize=12.5, pad=8)

    fig.suptitle(f"UCI-HAR 测试集 · 逻辑回归混淆矩阵（总体准确率 {acc:.1%}）",
                 fontsize=15, fontweight="bold", color=cs.INK, y=0.97)
    cs.save(fig, P_IMG / "confusion_matrix.png")


# ================================================================ 4. MNIST 样例
def fig_mnist() -> None:
    import torch

    sys.path.insert(0, str(MNI))
    from data import load_mnist  # noqa: E402
    from model import DigitCNN  # noqa: E402

    _, _, xte, yte = load_mnist()
    ckpt = torch.load(MNI / "mnist_cnn.pt", map_location="cpu", weights_only=False)
    model = DigitCNN()
    model.load_state_dict(ckpt["state_dict"] if "state_dict" in ckpt else ckpt)
    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(xte), 512):
            preds.append(model(torch.from_numpy(xte[i:i + 512])).argmax(1))
    pred = torch.cat(preds).numpy()

    idx = np.random.default_rng(1).choice(len(xte), 16, replace=False)
    ncorrect = int(sum(int(pred[i]) == int(yte[i]) for i in idx))

    fig, axes = plt.subplots(2, 8, figsize=(cs.FIG_W, cs.FIG_H))
    fig.subplots_adjust(left=0.015, right=0.985, top=0.87, bottom=0.03, wspace=0.16, hspace=0.16)
    cs.setup()
    for ax, i in zip(axes.ravel(), idx):
        p, t = int(pred[i]), int(yte[i])
        ok = p == t
        ax.imshow(xte[i].squeeze(), cmap="gray")
        ax.set_title(f"对 {t}→{p}" if ok else f"错 {t}→{p}",
                     color=cs.ACCENT if ok else cs.BAD, fontsize=11.5, pad=5)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    fig.suptitle(f"MNIST 测试集真实样例 · 真实 → 预测（抽 16 张对 {ncorrect} 张）",
                 fontsize=15, fontweight="bold", color=cs.INK, y=0.965)
    cs.save(fig, P_IMG / "mnist_samples.png")


# ================================================================ 5. 机械臂 RRT*
def fig_arm() -> None:
    spec = importlib.util.spec_from_file_location("arm_planner", ARM / "arm_planner.py")
    ap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ap)

    np.random.seed(0)
    arm = ap.PlanarArm(lengths=[1.0, 0.8, 0.6], link_radius=0.06)
    obstacles = [(1.0, 0.9, 0.28), (1.0, -0.9, 0.28)]
    q_start = np.array([2.2, -1.6, 0.6])
    q_goal = np.array([0.0, 0.0, 0.0])
    limits = ([-2.6, -2.6, -2.6], [2.6, 2.6, 2.6])
    planner = ap.ArmRRTStar(arm, obstacles, q_start, q_goal, limits,
                            weights=[1.0, 1.0, 1.0], step=0.5, near_radius=0.9,
                            goal_bias=0.15, goal_conn=0.6, max_iter=8000,
                            rng=np.random.default_rng(7))
    path, iters, ok = planner.plan()
    jlen = sum(planner.dist(path[i], path[i + 1]) for i in range(len(path) - 1))
    print(f"  RRT* 复算：iter {iters} · nodes {len(planner.nodes)} · path {len(path)} · len {jlen:.3f}")

    fig = plt.figure(figsize=(cs.FIG_W, cs.FIG_H))
    cs.setup()
    gs = fig.add_gridspec(1, 2, width_ratios=[1.28, 1], wspace=0.02,
                          left=0.015, right=0.975, top=0.86, bottom=0.03)
    ax = fig.add_subplot(gs[0])
    axp = fig.add_subplot(gs[1])

    reach = float(np.sum(arm.L))
    for (cx, cy, r) in obstacles:
        ax.add_patch(plt.Circle((cx, cy), r, color=cs.SAND, zorder=1))
    ax.add_patch(plt.Circle((0, 0), reach, fill=False, color=cs.AXIS, ls="--", lw=1, zorder=0))
    poses = np.linspace(0, len(path) - 1, 8).astype(int)
    for k, i in enumerate(poses):
        pts = arm.fk(path[i])
        ax.plot(pts[:, 0], pts[:, 1], color=cs.ACCENT, lw=1.2,
                alpha=0.15 + 0.10 * k / len(poses), zorder=2)
    for q, c in [(q_start, cs.ACCENT), (q_goal, cs.WARN)]:
        pts = arm.fk(q)
        ax.plot(pts[:, 0], pts[:, 1], color=c, lw=3, zorder=4)
        ax.plot(pts[0, 0], pts[0, 1], "o", color=c, ms=8, zorder=5)
    ee = np.array([arm.ee(q) for q in path])
    ax.plot(ee[:, 0], ee[:, 1], color=cs.WARN, lw=1.6, ls=":", zorder=3)
    ax.plot(*ee[0], "o", color=cs.ACCENT, ms=9, zorder=6)
    ax.plot(*ee[-1], "X", color=cs.WARN, ms=11, zorder=6)
    ax.set_xlim(-reach - 0.2, reach + 0.2)
    ax.set_ylim(-reach - 0.2, reach + 0.2)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(cs.LINE)

    axp.axis("off")
    axp.set_xlim(0, 1)
    axp.set_ylim(0, 1)
    axp.text(0.06, 0.97, "规划结果", fontsize=13.5, fontweight="bold", color=cs.INK, va="top")
    rows = [("迭代次数", f"{iters}"), ("树节点", f"{len(planner.nodes)}"),
            ("路径点", f"{len(path)}"), ("关节路径长", f"{jlen:.2f} rad"),
            ("末端目标", "(2.40, 0.00)")]
    for k, (kname, v) in enumerate(rows):
        yy = 0.86 - k * 0.093
        axp.text(0.06, yy, kname, fontsize=11.5, color=cs.MUTED, va="top")
        axp.text(0.94, yy, v, fontsize=11.5, color=cs.INK, va="top", ha="right")
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], color=cs.ACCENT, lw=2.6, label="起点臂"),
        Line2D([], [], color=cs.ACCENT, lw=1.2, alpha=0.35, label="树中采样的位姿"),
        Line2D([], [], color=cs.WARN, lw=2.6, label="目标臂"),
        Line2D([], [], color=cs.WARN, lw=1.6, ls=":", label="末端轨迹"),
        Line2D([], [], color=cs.SAND, lw=6, label="障碍物"),
    ]
    axp.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.05, 0.44),
               frameon=False, fontsize=10, labelspacing=0.5, handlelength=1.7)
    fig.suptitle("关节空间 RRT* · 平面三连杆机械臂避障",
                 fontsize=15, fontweight="bold", color=cs.INK, y=0.965)
    cs.save(fig, P_IMG / "arm_rrt_result.png")


# ================================================================ 6. AutoBio 对照
def fig_autobio() -> None:
    rows = [
        ("π0_base · zero-shot\n（6 回合冒烟）", 0.0, "0/6"),
        ("本复现 · LoRA 5k steps\n（20 回合，seed 0）", 90.0, "18/20 · 90%"),
        ("上游论文 · 全量微调 30k steps\n（100×3 种子，H800）", 99.7, "99.7 ± 0.3%"),
    ]
    colors = [cs.SAND, cs.ACCENT, cs.SAND]
    fig, ax = cs.new_fig()
    fig.subplots_adjust(left=0.315, right=0.96, top=0.84, bottom=0.15)
    cs.clean(ax, xgrid=True, ygrid=False)
    ypos = np.arange(len(rows))
    for yy, (_, v, _t), c in zip(ypos, rows, colors):
        if v > 0:
            ax.barh(yy, v, height=0.52, color=c)
    for yy, (_, v, t) in zip(ypos, rows):
        if v > 95:  # 贴近右缘的柱：标签放条内右端，避免出画
            ax.text(v - 2, yy, t, va="center", ha="right", fontsize=11.5,
                    color=cs.INK, fontweight="bold")
        else:
            ax.text(max(v, 0) + 1.5, yy, t, va="center", fontsize=11.5,
                    color=cs.INK, fontweight="bold")
    ax.set_yticks(ypos)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11.5, color=cs.INK_SOFT)
    ax.set_xlim(0, 113)
    ax.set_ylim(-0.55, 2.55)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("thermal_cycler_close 任务成功率（%）")
    fig.suptitle("AutoBio 基准 · 成功率对照（非对等比较：算力 / 步数 / 微调方式均不同）",
                 fontsize=13.5, fontweight="bold", color=cs.INK, y=0.965)
    cs.save(fig, P_IMG / "autobio_result.png")


# ================================================================ 7. 同种子逐局对照（文章）
def fig_seedcmp() -> None:
    fig, ax = cs.new_fig()
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    cols = [(0.24, 0.48, "π0_base 零样本", cs.BAD, "失败"),
            (0.55, 0.79, "π0 + LoRA 微调", cs.ACCENT, "成功")]
    for x0, x1, head, c, word in cols:
        ax.text((x0 + x1) / 2, 0.955, head, ha="center", fontsize=13.5,
                fontweight="bold", color=cs.INK)
        for r in range(4):
            y1 = 0.835 - r * 0.19
            y0 = y1 - 0.15
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color=c))
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, word, ha="center", va="center",
                    fontsize=13, color="white", fontweight="bold")
    for r in range(4):
        ax.text(0.16, 0.76 - r * 0.19, f"ep0{r}", ha="right", va="center",
                fontsize=12, color=cs.MUTED)
    ax.text(0.5, 0.025, "同种子对照：零样本 0/4 失败 · LoRA 4/4 成功 —— 排除随机性，提升来自微调本身",
            ha="center", fontsize=11, color=cs.MUTED)
    ax.set_title("同种子逐局对照（ep00–03 使用完全相同的随机种子）", pad=10)
    cs.save(fig, W_IMG / "w_seedcmp.png")
    cs.to_webp(W_IMG / "w_seedcmp.png")


# ================================================================ 8. d2l 多项式拟合
def fig_d2l() -> None:
    """复刻站内交互演示的数据管线（d2l-ch1.html：LCG 种子 12345、10 个训练点、
    真实函数 sin(πx)、噪声 0.2），与页面演示同一份训练数据。"""
    XMIN, XMAX, NOISE, NTRAIN = -1.15, 1.15, 0.2, 10
    seed = 12345

    def rnd() -> float:
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % (2 ** 32)
        return seed / 2 ** 32

    def gauss() -> float:
        u = v = 0.0
        while u == 0:
            u = rnd()
        while v == 0:
            v = rnd()
        return np.sqrt(-2 * np.log(u)) * np.cos(2 * np.pi * v)

    true_f = lambda x: np.sin(np.pi * x)  # noqa: E731
    tx = np.array([max(XMIN, min(XMAX, XMIN + i / (NTRAIN - 1) * (XMAX - XMIN) * 0.92))
                   for i in range(NTRAIN)])
    ty = true_f(tx) + NOISE * np.array([gauss() for _ in range(NTRAIN)])
    grid = np.linspace(-1.1, 1.1, 300)

    fig, axes = plt.subplots(1, 3, figsize=(cs.FIG_W, cs.FIG_H), sharey=True)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.72, bottom=0.14, wspace=0.10)
    cs.setup()
    panels = [(1, "欠拟合（阶数 1）", cs.WARN, "--"),
              (4, "恰好拟合（阶数 4）", cs.ACCENT, "-"),
              (12, "过拟合（阶数 12）", cs.BAD, "-")]
    for ax, (deg, ttl, c, ls) in zip(axes, panels):
        coef = np.polyfit(tx, ty, deg)
        ax.plot(grid, true_f(grid), color=cs.MUTED, ls="--", lw=1.2, label="真实函数")
        ax.plot(grid, np.polyval(coef, grid), color=c, ls=ls, lw=2.2, label="多项式拟合")
        ax.scatter(tx, ty, s=26, color=cs.INK_SOFT, zorder=5, label="训练数据")
        ax.set_title(ttl, fontsize=12.5, pad=7)
        ax.set_xlim(-1.15, 1.15)
        ax.set_ylim(-1.55, 1.55)
        cs.clean(ax, ygrid=True)
    axes[0].set_ylabel("y")
    axes[1].set_xlabel("x")
    axes[0].legend(loc="lower left", frameon=False, fontsize=9.5)
    fig.suptitle("同一份训练数据、三种阶数的多项式拟合（与站内交互演示同一数据）",
                 fontsize=14.5, fontweight="bold", color=cs.INK, y=0.96)
    cs.save(fig, P_IMG / "d2l_fit.png")


if __name__ == "__main__":
    print("按 chart_style v1.0 重绘：")
    fig_mujoco()
    fig_bc()
    fig_confusion()
    fig_mnist()
    fig_arm()
    fig_autobio()
    fig_seedcmp()
    fig_d2l()
    print("完成。")
