# 陈斐阳 · Feiyang Chen

**湖南大学 · 大数据管理与应用（商务大数据）· 2025 级本科生** ｜ 具身智能方向（大脑侧：学习算法与数据）

Email: chenfeiyang20071228@gmail.com ｜ 个人网站: feiyang2007.github.io ｜ GitHub: github.com/Feiyang2007 ｜ ORCID: 0009-0001-7212-9001

## 教育背景

**湖南大学 · 工商管理学院 · 大数据管理与应用**（2026.09 — 至今，2029 年管理学学士预期）
**湖南大学 · 土木工程学院 · 土木工程**（2025.09 — 2026.06，转入大数据，未留级，学分全部带入）

- 数学核心课（初修）：高等数学 AⅠ 86 · 高等数学 AⅡ 80 · 线性代数 A 83；概率论与数理统计进行中
- 土木阶段系统学习理论力学、大学物理、工程制图（AutoCAD / Revit 熟练）——力学与制图底子直接服务机器人方向

## 项目经历

**AutoBio × π0：VLA 基础模型 LoRA 微调复现**（2026.10）
在 AutoBio 机器人操作基准上修复上游代码（6 处过期导入、SLURM 假设、sm_120 CUDA 兼容），对 π0（PaliGemma 2B + 300M 动作专家）做 LoRA 微调：单张 RTX 5090 训练 7.5 小时（5000 步），thermal_cycler_close 任务从 zero-shot 0/6 提升至 18/20（90%）。权重、逐回合结果与 rollout 视频公开于 GitHub / HuggingFace。

**强化学习从零实现：DQN → PPO → MuJoCo**（2026.09）
纯 PyTorch 手写 Double-DQN 与 PPO（独立 Actor/Critic、GAE、裁剪目标、lr 衰减），不借助现成 RL 库；同一份 PPO 迁移到 MuJoCo InvertedPendulum-v4，第 56 个 iteration 解决，确定性策略复测 20/20 满分。

**手写数字识别 · CNN**（2026.09）
PyTorch 手写小 CNN，真实 MNIST（6 万训练 / 1 万测试）端到端训练，测试准确率 98.9%；权重导出为 JSON，在浏览器里用纯 JavaScript 前向推理实现「画板写字即识别」。

**个人知识 RAG 助手**（2026.09）
将两年自学笔记整理为 35 段语料，bge-m3 向量检索 + DeepSeek 生成，做在线自然语言问答；含中文 BM25 兜底与离线模式，已部署可公开访问。

**其他**：LeRobot 行为克隆复现（PD 专家示教 → MLP 模仿，99.6%）｜ 机械臂关节空间 RRT*（正运动学 + 碰撞检测）｜ Sklearn 端到端流水线（UCI HAR，95.4%）｜ 《动手学深度学习》第一章从零实现

## 技能

- **编程**：Python（NumPy / Pandas / Matplotlib / Streamlit）熟练；C 语言基础；SQL / Git / Linux
- **机器学习**：Scikit-learn 建模全流程；PyTorch（CNN / MLP / 强化学习实现）
- **机器人 / 仿真**：MuJoCo（EGL 无头评测）；URDF；LeRobot 数据格式；openpi / π0 微调
- **数学**：微积分 / 线性代数已修；概率论与数理统计进行中；理论力学（土木阶段）
- **语言**：中文母语；英语持续提升中

## 其他

- 湖南大学校跃鹿战队（RoboMaster）算法组报名中；创新创业人才试点班（机器人方向）面试准备中
- 自建 Obsidian 知识库（课程 / 代码 / 决策全记录，同步 GitHub）；个人网站 8 个项目页全部可交互、可验证
