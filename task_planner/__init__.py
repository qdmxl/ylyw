"""
YLYW 任务规划器

基于汉字卦爻推理的通用任务规划器。
纯YLYW体系，不依赖任何环境特定信息（如admissible_commands）。

架构：
  StateEncoder     — 场景状态 → 中文状态词 → 卦象向量
  IntentionDecoder  — 卦名+六爻 → 规划意图（知几学习驱动）
  Experience        — 知几式经验积累（跨局正向+反向校准）
"""
