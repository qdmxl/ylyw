#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild_merge.py — 从备份重新合并（这次用唯一锚点，避免全局 replace 误伤）
"""
PAPER = "YLYW汉语言文字处理新范式.md"
BAK = "YLYW汉语言文字处理新范式.md.bak"
NEW = "新增章节_语料自组织成长.md"

paper = open(BAK, encoding="utf-8").read()          # 从干净备份开始
newch = open(NEW, encoding="utf-8").read()

# 1) 新章节正文
idx = newch.find("## 6.8")
body = newch[idx:].strip() + "\n"
# 调整标题层级
body = body.replace("## 6.8 ", "### 6.8 ", 1)
body = body.replace("### 6.8.", "#### 6.8.")

# 2) 插入 6.8 章节到 "## 7 讨论" 之前（唯一锚点）
m = paper.find("## 7 讨论")
assert m > 0
paper = paper[:m] + body + "\n" + paper[m:]

# 3) 摘要：在关键词前加一段（唯一）
kw = "**关键词：** YLYW模型"
extra_abs = (
    "进一步，我们将其拓展为'先天（易理字形）+ 后天（语料分布）'的自适应语义底座：\n"
    "系统通过大量上下文的阅读，自行整理、内建起语义知识库（分布语义自组织），\n"
    "并以嵌套元胞的方式随阅读持续繁殖与成长。在真实中文语料（8.7万字）的增量阅读实验中，\n"
    "覆盖面、系统复杂度、语义划分收敛三项成长指标均随阅读量单调上升；\n"
    "统一双通道评分（字形先验+语料证据+知几校准）在多主题语料上达 97.7% 准确率，\n"
    "优于单一语料通道。这一机制使 YLYW 的语义底座从'人工抄录的静态字典'\n"
    "迈向'随阅读持续生长、日益巩固的自组织知识系统'。\n\n"
)
assert paper.count(kw) == 1
paper = paper.replace(kw, extra_abs + kw)

# 4) §6.7：在末尾追加第4条（用"### 6.7"到"## 7"间、以句子唯一结尾定位）
#  §6.7 的 3. 结尾是 "...大量不规则口语用法。" 后紧跟换行再过渡段
#  在其后插入第4条
anchor_67 = "扩展到现代汉语需要处理大量不规则口语用法。"
new_67_4 = (
    anchor_67 + "\n"
    "4. **语义底座依赖人工标注**：原型的部首隶属度、会意字知识库均为人工先验，规模受限于标注成本。\n"
    "   下一节（§6.8）提出'先天字形+后天语料'的双通道架构，使语义底座可由语料自组织生长，缓解该瓶颈。\n"
)
# 该锚点在全文唯一（§6.7 表述与 §7.4 不同）
i67 = paper.find("## 6.7")
j67 = paper.find("## 7 讨论", i67)
sec67 = paper[i67:j67]
assert sec67.count(anchor_67) == 1, "§6.7锚点不唯一"
sec67 = sec67.replace(anchor_67, new_67_4)
paper = paper[:i67] + sec67 + paper[j67:]

# 5) §7.4：精确更新第2条（整行唯一）
old2 = "2. **模糊隶属度的标定**：偏旁部首的语义隶属度初始定义为人工先验值，需通过语料校准提升精度。"
new2 = old2 + "§6.8 的语料指纹通道天然提供校准信号，后续可据此对部首隶属度做数据驱动微调。"
i74 = paper.find("### 7.4")
j74 = paper.find("## 8 结论", i74)
sec74 = paper[i74:j74]
assert sec74.count(old2) == 1, "§7.4第2条不唯一"
sec74 = sec74.replace(old2, new2)
paper = paper[:i74] + sec74 + paper[j74:]

# 6) 结论：追加贡献(6)
old_c = "为文言文理解提供了可工程化的技术路径。"
new_c = ("为文言文理解提供了可工程化的技术路径；"
         "（6）提出'先天字形+后天语料'的自适应语义底座（统一双通道评分+嵌套元胞成长+知几校准），"
         "经验证系统能通过大量阅读自行整理、内建语义知识库，覆盖面、复杂度、语义收敛三项指标随阅读量单调上升，"
         "统一评分在多主题语料上达 97.7% 准确率，使 YLYW 语义系统从静态人工知识库迈向自组织成长。")
i8 = paper.find("## 8 结论")
j8 = len(paper)
sec8 = paper[i8:]
assert sec8.count(old_c) == 1
sec8 = sec8.replace(old_c, new_c)
paper = paper[:i8] + sec8

open(PAPER, "w", encoding="utf-8").write(paper)
print("重做完成：从备份合并，全部唯一锚点，无全局误伤。")
print("总行数:", paper.count("\n"))
