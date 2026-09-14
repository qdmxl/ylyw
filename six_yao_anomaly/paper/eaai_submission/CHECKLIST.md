# EAAI 投稿行动清单

投稿目标：**Engineering Applications of Artificial Intelligence (Elsevier)**
论文：Yijing Yao-Variation Framework for Unsupervised Industrial Image Anomaly Detection

---

## A. 必须完成（硬性要求）

| # | 项目 | 状态 | 说明 |
|---|------|------|------|
| A1 | 换成 `elsarticle` 模板 | ⬜ | 当前是 IEEEtran，需重排 |
| A2 | 参考文献转 Elsevier 数字格式 | ⬜ | 手写 `\bibitem` → 需统一为 num 格式 |
| A3 | Highlights（3–5 条，≤85 字符/条） | ⬜ | 单独文件 |
| A4 | Graphical Abstract（图） | ⬜ | 可选但强烈建议 |
| A5 | CRediT 作者贡献声明 | ⬜ | 必须 |
| A6 | 利益冲突声明 | ⬜ | 必须 |
| A7 | 数据可用性声明 | ⬜ | 必须（MVTec AD 公开，可声明） |
| A8 | AI 使用声明 | ⬜ | Elsevier 新要求 |
| A9 | 摘要 ≤ 250 词、关键词 4–6 个 | ⬜ | 核对 |
| A10 | 图表按 Elsevier 规范（编号、caption 格式） | ⬜ | 部分已就绪 |
| A11 | Cover Letter | ⬜ | 必须 |
| A12 | 作者信息完整（全作者、单位、ORCID、通讯作者） | ⬜ | 目前只有 Ma Xinglu, et al. |

## B. 强烈建议补强（关系录用）

| # | 项目 | 状态 | 说明 |
|---|------|------|------|
| B1 | 多数据集验证（VisA 或 MPDD/BTAD） | ⬜ | 只有 MVTec AD 是最大短板 |
| B2 | 形式化"爻变"判据（相关性流形检验） | ⬜ | 降低哲学占比，提升理论严谨 |
| B3 | random 消融补到 15 类 或 明确说明限制 | ⬜ | 审稿必问 |
| B4 | SOTA 数字逐项核对原论文引用 | ⬜ | PaDiM 0.975 / PatchCore 0.992 及逐类值 |
| B5 | 与更多近 2 年方法对比（WinCLIP/SimpleNet 等） | ⬜ | 相关工作已加引用，对比表可补 |
| B6 | 运行时间/复杂度定量表 | ⬜ | 已有 52×/55×，可扩展 |

## C. 元数据

- 投稿系统：Elsevier Editorial Manager
- 文章类型：Full Length Article
- 语言：英文

---

## 待办优先级
1. 先做 A（模板转换 + 声明文件）——纯格式，不影响科学内容
2. 再评估 B1（多数据集）工作量，决定投前是否补
3. 最终生成 elsarticle 版 PDF + 全套投稿文件
