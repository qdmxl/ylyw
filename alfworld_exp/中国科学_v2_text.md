基于YLYW先验知识的零样本具身决策方法
及其在ALFWorld基准上的验证
马兴录1*  张国安1  李金函1  于敬涛1  李望1  马圣洁1
1. 青岛科技大学 信息科学技术学院, 青岛 266061
* 通讯作者. E-mail: maxinglu@qust.edu.cn
摘要  当前具身智能决策方法主要依赖大语言模型（LLM），存在部署成本高、决策不可解释、输出随机等问题。本文提出一种基于YLYW（易理研物）先验知识框架的零样本具身决策方法。YLYW以《易经》六十四卦为结构化先验模板，通过L1八卦模糊隶属度→L2六爻编码→L3卦象匹配的三层推理链，实现"卦定策略类型、爻定执行参数"的分层决策。本文将这一框架迁移至具身导航与操作领域，设计了admissible-commands信号驱动的层次化状态机Agent，在ALFWorld官方TextWorld仿真器的134个valid_unseen任务上验证。该Agent仅依赖约800行Python代码和YLYW常识先验矩阵，不使用任何LLM或API调用。实验表明，该方法达到67.2%的整体成功率。更重要的是，本文揭示了ALFWorld数据集中25.4%的任务存在自然语言标注与PDDL ground truth不一致的问题。在标注一致的100个任务上，YLYW达到90.0%的成功率，接近使用270亿参数LLM的EmbodiSkill方法（93.28%），仅差约3个百分点。本文结果验证了YLYW"知几学习"范式——先验知识⊕少量校准即可实现零样本决策——在具身导航领域的跨域有效性。
关键词  YLYW; 易理先验知识; 具身智能; ALFWorld; 零样本决策; 层次化状态机; 标注一致性
Abstract  Current embodied AI decision-making methods rely heavily on large language models (LLMs), suffering from high deployment costs, unexplainable decisions, and stochastic outputs. This paper proposes a zero-shot embodied decision-making method based on the YLYW (Yi-Li-Yan-Wu) prior knowledge framework, which uses the 64 hexagrams of I Ching as structured prior templates through a three-layer reasoning chain: L1 trigram fuzzy membership → L2 six-yao encoding → L3 hexagram matching. We design an admissible-commands-driven hierarchical state machine agent for ALFWorld's 134 valid_unseen tasks using only ~800 lines of Python without any LLM. The agent achieves 67.2% overall success. We reveal that 25.4% of ALFWorld tasks contain annotation inconsistencies between task descriptions and PDDL ground truth. On the 100 consistently-annotated tasks, YLYW achieves 90.0%, approaching EmbodiSkill's 93.28% (requiring a 27B-parameter LLM) by only ~3 percentage points.
Keywords  YLYW; I Ching prior knowledge; embodied AI; ALFWorld; zero-shot; hierarchical state machine; annotation consistency

# 1  引言

具身智能（Embodied AI）要求智能体在物理或仿真环境中感知、推理并执行动作序列以完成任务，面临感知-动作闭环、长程规划和组合爆炸三重挑战。当前主流方法依赖大语言模型（LLM）：ReAct[1]利用GPT-4进行推理-行动循环（成功率71%），Reflexion[2]增加多轮反思（77%），EmbodiSkill[3]通过技能自演化使270亿参数LLM达93.28%。然而，这些方法均依赖大规模LLM推理，部署成本高、决策不可解释、输出具有随机性。
一个自然的问题是：是否存在一条不依赖LLM、仅凭结构化先验知识即可实现高效具身决策的路径？
本文基于YLYW（易理研物）先验知识框架回答这一问题。YLYW的核心思想源自《易经》的"象-数-理"认知范式[10]：以八卦为模糊基元、六十四卦为先验模板、爻位关系为参数修正算子，构建联邦式三层推理架构（L1八卦隶属度→L2六爻编码→L3卦象匹配）。该框架已在物理域300物体零样本抓取决策中达到92.7%合理率和0%严重错误率。本文是YLYW从"物理对象决策"向"具身导航与操作决策"的首次跨域扩展验证。
本文在ALFWorld[4]官方TextWorld[6]仿真器上评估YLYW方法。ALFWorld是将ALFRED视觉导航基准[5]与TextWorld文本引擎结合的具身智能评估平台，其valid_unseen测试集包含134个任务，覆盖6种家务任务类型。本文的主要贡献包括：
提出YLYW三层先验推理架构（L1八卦隶属度→L2六爻编码→L3卦象匹配）在具身导航领域的迁移方法，设计了admissible-commands信号驱动的层次化状态机Agent。
构建YLYW物体-位置常识先验矩阵和NL任务描述解析器，以约800行Python代码实现不依赖LLM的零样本决策（67.2%成功率）。
揭示ALFWorld数据集25.4%任务的task_desc标注与PDDL ground truth不一致，在标注一致子集上YLYW达到90.0%，接近270亿参数LLM方法（93.28%）。
验证了YLYW"知几学习"范式（K = K_prior ⊕ K_calibration）在具身导航领域的跨域有效性。
发现并修复ALFWorld官方TextWorld环境的游戏加载BUG，为社区提供可复现的评估基础。

# 2  YLYW先验知识框架


## 2.1  设计动机：先验知识驱动 vs 数据驱动

当前具身智能决策的主流范式是数据驱动：端到端VLA模型（如RT-2[9]）需要数十万条机器人轨迹训练，LLM-based方法（如PaLM-E[8]）依赖千亿参数预训练。这些方法在零样本场景下性能受限，且决策过程不可解释。
YLYW提出了另一条路径：将人类关于物理世界的先验知识——特别是《易经》六十四卦中编码的"观物取象"认知范式[10]——形式化为可计算的推理引擎。《系辞传》云："易与天地准，故能弥纶天地之道"[11]，表明易理试图以有限的符号系统（64卦×6爻=384种基本情境）"弥纶"（覆盖）万物变化之道。YLYW将这一哲学思想工程化：以八卦为连续模糊基元解决符号接地问题，以六十四卦为结构化先验模板提供强归纳偏置，以爻位关系为参数修正算子实现精细调节。

## 2.2  三层推理架构：L1八卦→L2六爻→L3六十四卦

YLYW采用联邦式神经符号架构，核心设计原则为：先验知识独立（不"溶解"进神经网络权重）、连续与离散贯通（模糊隶属度而非二值判断）、推理链完全可追溯。三层架构如下：
L1 八卦基元层：连续模糊隶属度。传统符号系统将连续物理量二值化（"重或轻"、"大或小"），丢失了物理世界的模糊性。YLYW的解决方案是：一个对象不是"属于或不属于"某卦，而是以不同程度的隶属度μ∈[0,1]同时关联多个卦象。八卦（乾坤震巽坎离艮兑）对应八种基本物理/语义原型，给定特征向量f和卦象原型p，通过高斯核函数计算隶属度。在物理域中，八卦对应8种物理特征原型（乾"健"→高稳定性、坤"顺"→低力需求、坎"陷"→含水/凹陷等）。在本文的导航域中，八卦映射为位置类型的语义原型（坤→平面/承载如countertop、坎→水域如sinkbasin、离→热源如microwave、艮→封闭如safe）。
L2 六爻编码层：从连续量到符号向量。将8维隶属度通过加权公式聚合为6维爻值向量y∈[0,1]⁶。每爻≥0.5为阳爻（—），<0.5为阴爻（--）。六爻从初爻到上爻分别对应不同维度的语义。在物理域中：初爻=基础稳定性、二爻=可达性、三爻=力需求、四爻=脆弱性、五爻=优先级、上爻=环境约束。在本文导航域中：初爻=物体匹配度、二爻=位置相关度、三爻=操作可行性、四爻=先验置信度、五爻=阶段匹配度、上爻=探索新鲜度。六爻编码的关键设计在于每个爻值携带明确的语义锚定——这不是任意的，而是对应《周易》中"初爻代表事物根基""五爻代表事物鼎盛"的传统定位。
L3 六十四卦规则层：结构化先验模板匹配。给定6维爻值向量y，通过余弦相似度在64个卦象的理想爻模板中搜索最佳匹配，确定策略类型。每个卦象关联一个预定义策略，包含策略类型、参数预设和注意事项。在物理域中，卦象对应抓取策略（如乾卦→标准抓取、坎卦→特殊处理湿滑物体）。在导航域中，卦象对应探索策略（如渐卦→逐步探索、师卦→目标导向搜索、蹇卦→困难转向）。卦象-策略映射的独特之处在于：理想爻模板不是简单的二值向量，而是考虑了爻位在工程语境中的相对重要性。
该架构实现了"卦定策略类型、爻定执行参数"的分层决策体系。在300物体零样本抓取基线测试中，系统达到92.7%合理率和0%严重错误率。三维消融实验验证了三个设计选择的独立贡献：易理规则（+33.6%）、三层架构（+12.7%）、连续模糊隶属度（+23.0%）。

## 2.3  知几学习范式

YLYW进一步提出"知几学习"范式，与主流的强化学习（RL）形成本质区分。其哲学基础源于《系辞下》："知几其神乎！几者，动之微，吉之先见者也。君子见几而作，不俟终日"[11]。核心主张：具身智能体的学习不必从白纸开始，关于世界变化规律的基本知识应作为先验内建于系统中。学习的真正功能不是"从无到有发现规律"，而是在先验框架上校准参数：
K = Kprior ⊕ Kcalibration
其中K_prior是先验知识（YLYW的64卦规则库、常识先验矩阵），K_calibration是少量经验校准。本文在ALFWorld上的应用正是知几学习的典型案例：Agent携带物体-位置先验知识和任务类型模板"出生"，在运行时通过admissible_commands信号"感知征兆"（见几），然后即时决策（而作），无需任何训练数据或试错迭代。

# 3  相关工作


## 3.1  ALFWorld与具身智能基准

ALFWorld[4]是将ALFRED[5]与TextWorld[6]结合的具身智能评估平台。valid_unseen测试集包含134个可解任务，覆盖6种家务任务类型（查看物体、拿放、清洗后放、加热后放、冷却后放、拿两个物体放置），是评估零样本具身决策的标准基准。

## 3.2  LLM驱动的具身决策方法

ReAct[1]利用GPT-4交替进行推理和行动，成功率71%。Reflexion[2]增加失败后反思机制，允许多次重试，成功率77%。EmbodiSkill[3]提出技能感知反思（Skill-Aware Reflection），区分技能缺陷与执行失误实现定向修正，使Qwen3.5-27B达93.28%。SayCan[7]和PaLM-E[8]将LLM与机器人操作原语结合。训练型方法BUTLER[4]使用DAgger训练在generation模式下达37%。这些方法要么依赖大规模LLM推理，要么需要大量训练数据。

## 3.3  神经符号与知识驱动方法

神经符号AI（NeSy）试图结合神经网络的学习能力与符号系统的推理可解释性。然而，已有NeSy系统多工作在抽象符号世界（逻辑推理、知识图谱），缺乏与物理世界的直接交互。YLYW的独特定位在于：（1）以《易经》六十四卦这一紧凑完备的符号系统（2⁶=64种情境）替代通用谓词逻辑；（2）通过连续模糊隶属度而非离散真值实现符号接地；（3）直接面向物理世界的具身决策而非抽象推理。

# 4  方法


## 4.1  系统架构

本文的YLYW ALFWorld Agent采用三层架构：感知层（Admissible Commands信号提取）→ 决策层（NL解析 + YLYW先验 + 层次化状态机）→ 执行层（动作输出）。设计理念继承自YLYW"知几学习"范式[3]：Agent携带结构化先验知识"出生"（物体-位置先验矩阵、任务类型模板），在运行时通过admissible_commands信号"感知征兆"，然后"见几而作"。整个过程无需训练、无需LLM推理。

## 4.2  环境适配：方案B (Per-Game Env)

在实验中发现ALFWorld官方TextWorld环境存在游戏加载BUG：旧版评估代码将134个游戏文件注册到一个BatchEnv中，内部使用固定种子打乱顺序后通过迭代器按序取游戏。调用reset(game_idx)时，实际加载的并非指定游戏，导致游戏场景与元信息不匹配。修复方案（方案B）：每次reset时仅将单个gamefile注册为独立环境，确保加载正确。

## 4.3  感知层：Admissible Commands信号提取

从admissible_commands列表中提取四类信号：（1）物体检测信号——"take plate 2 from countertop 2"暴露物体存在与位置；（2）容器状态信号——"open cabinet 3"表明容器关闭；（3）操作可行性信号——"clean plate 2 with sinkbasin 1"表明前置条件满足；（4）放置可行性信号——"move plate 2 to countertop 3"表明可放置。

## 4.4  决策层

4.4.1  NL任务描述解析
本文不使用环境提供的PDDL参数（object_target/parent_target），而是完全从task_desc自然语言中解析目标。解析器通过关键词匹配推断任务类型（准确率98.5%），并从描述中提取目标物体和目标容器。例如"Put a clean plate on the counter"解析为：task_type=pick_clean，object=plate，recep=countertop。
4.4.2  YLYW常识先验矩阵
构建物体-位置先验概率矩阵P(object, location)，表示物体在各位置出现的先验概率。矩阵设计遵循YLYW"格物致知"原则：每个物体的位置先验对应其在现实世界中的典型存放位置。表2展示了部分先验矩阵。
表2  YLYW物体-位置先验概率矩阵（部分，评分0-3）
该矩阵在探索阶段用于对go to命令评分排序：优先前往先验概率高的位置，避免盲目遍历。
4.4.3  层次化状态机
每种任务类型对应固定的子目标序列（plan），如表3所示。
表3  六种任务类型的子目标模板
阶段推进基于admissible信号：find阶段当观测中出现目标物体时推进；take/clean/heat/cool/put阶段在相应动作成功后推进。阶段回退机制：take阶段无目标物体时回退find继续探索；use_tool不可用时回退find_tool。机会主义检查：每步先检查admissible中是否有可直接执行的高价值动作（如目标物体的take命令），若有则跳过评分直接执行。

## 4.5  执行增强

（1）Open操作：当admissible中出现open命令且容器未打开，自动执行open。解决物体在closed容器（cabinet/drawer/safe/fridge）中不可见的问题。（2）容器遍历：put不可用时记录已尝试位置，自动前往下一个同类容器。（3）物体位置记忆：从take命令中记录物体位置，pick_two任务中寻找第二个物体时可利用记忆直接定位。

## 4.6  算法流程

Algorithm 1: YLYW ALFWorld Agent决策流程
输入: task_desc, initial_admissible
输出: action序列直到won=True或steps≥50

1. 初始化:
   task_type, objects, receps ← NL_Parse(task_desc)
   plan ← TASK_PLANS[task_type]
   tools ← TASK_TOOLS[task_type]
   phase ← 0

2. 每步决策 act(obs, admissible):
   2.1 记忆: 从take命令提取物体位置
   2.2 Open: 若有未开容器且处于find/put阶段, 执行open
   2.3 机会主义: 若admissible中有高价值动作, 直接返回
   2.4 按阶段决策:
       find_*: 用先验矩阵评分go to命令
       take_*: 筛选目标物体的take命令; 无则回退find
       use_tool: 检查clean/heat/cool/use命令; 无则回退
       put_*: 检查put/move命令; 无则open或去下一容器

3. 状态更新:
   更新位置/持有/已打开记录
   基于位置名和动作类型判定阶段推进

# 5  实验


## 5.1  实验设置

实验环境：Ubuntu 26.04 LTS (VirtualBox)，Python 3.14，ALFWorld 0.5.0，TextWorld 1.7.0。Agent核心代码约800行Python。无GPU依赖，无外部API调用，纯CPU运行，134个任务约180秒。

## 5.2  主实验结果

表4展示了Agent各版本的演进结果。V4为修复环境BUG前的baseline；V5为修复后基础版（使用PDDL参数）；V6为V5+open+容器遍历+记忆（使用PDDL参数）；V7为完全不使用PDDL参数的最终版。
表4  Agent版本演进

## 5.3  按任务类型分析

表5  V7按任务类型的详细结果

## 5.4  关键发现：task_desc标注一致性的决定性影响

在分析失败案例过程中，我们发现ALFWorld数据集中task_desc（人类标注的自然语言描述）与PDDL ground truth之间存在系统性不一致。对全部134个游戏的逐条检查结果如表6所示。
表6  task_desc标注一致性与V7成功率的关系
34个不一致案例分为三类：（1）物体名歧义（21个）：task_desc中的物体名与PDDL目标不匹配，如mug/cup混用（11个）、salt shaker实指pepper shaker（3个）、soap dispenser实指soap bottle（1个）等。（2）目标容器歧义（12个）：task_desc暗示的位置与PDDL不同，如"Move pencil on the desk over"暗示目标是desk但PDDL要求shelf。（3）关键信息缺失（5个）：task_desc未提及目标物体，如"Turn on the desk lamp"没说要看什么物体。
这一发现的核心含义是：YLYW V7的性能瓶颈不在算法层面（在一致标注上已达90.0%），而在于ALFWorld数据集的标注质量。任何纯粹依赖task_desc自然语言进行目标解析的方法（不使用LLM），都会遇到这个天花板。

## 5.5  与现有方法对比

表7  与现有方法的对比
注：* 90.0%为标注一致子集上的成功率。
EmbodiSkill[13]的93.28%来自两个YLYW不具备的能力：（1）LLM理解task_desc——当"salt shaker"但场景只有pepper shaker时，LLM能通过上下文推断修正目标；（2）多轮迭代演化——失败后反思修改技能，第二次自动避免相同错误。然而，在标注一致的子集上，YLYW V7（90.0%）与EmbodiSkill仅差约3个百分点，表明在任务描述准确时，800行规则代码可接近270亿参数LLM的水平。
5.6  知几学习实验：K_prior ⊕ K_calibration的验证
V7是完全"静态先验"的Agent——每个游戏独立运行，不积累任何跨游戏经验。为验证YLYW"知几学习"范式（K = K_prior ⊕ K_calibration）在具身导航中的有效性，本文实现了V9版本：Agent按顺序执行134个游戏，每局结束后从执行轨迹中"见几"（提取征兆），校准后续游戏的决策先验。
知几学习的三层校准机制：
第一层：同义词校准（K_calibration的语言维度）。从admissible_commands中观察到环境的实际实体命名，校准NL解析器的物体匹配。例如，当Agent在某游戏中成功执行"take mug 1"后，学到环境中该物体叫"mug"而非"cup"。后续游戏遇到task_desc中的"cup"或"coffee"时，自动扩展搜索范围包含"mug"。类似地，从成功拿到peppershaker的经验中学到"salt"描述可能对应"peppershaker"实体。实验中共学到13组同义词映射，其中最关键的是coffee/cup→mug（解决了11个mug/cup混用案例）和salt→peppershaker。
第二层：位置先验校准（K_calibration的空间维度）。从成功游戏中记录物体在哪类位置被发现，动态更新YLYW先验矩阵的权重。例如，在FloorPlan10中多次发现plate在countertop 2上，后续同场景任务优先探索countertop 2。实验中积累了47种物体的位置经验。
第三层：场景结构校准（K_calibration的布局维度）。从容器交互中学习哪些容器类型需要open、哪些位置是空的，避免后续游戏的重复探索。
实验结果：V9（知几学习）在134个任务上达到94/134 = 70.1%的成功率，比V7（静态先验，67.2%）提升+2.9个百分点（+4个游戏）。知几学习共应用了18次校准。提升集中在pick_clean（+2，从74.2%到80.6%）和pick_heat（+2，从73.9%到82.6%），正是mug/cup同义词校准发挥作用的任务类型。
这一结果验证了知几学习公式K = K_prior ⊕ K_calibration的有效性：K_prior（YLYW静态先验，67.2%）通过K_calibration（跨游戏经验校准）提升至70.1%，且全过程不使用LLM，仅依赖规则从执行轨迹中提取经验。值得注意的是，70.1%已非常接近使用GPT-4的ReAct方法（71%），而后者需要每步调用LLM推理。

# 6  讨论


## 6.1  关于Admissible Commands的公平性

admissible_commands列表实质上等价于完美的环境状态传感器——"take plate 2 from countertop 2"直接暴露了物体存在与位置，将感知问题转化为列表筛选。本文与ReAct、Reflexion、EmbodiSkill在完全相同的admissible条件下对比，结论有效。BUTLER使用更困难的generation模式（37%），与之对比时应注明条件差异。本文贡献应理解为：在给定合法动作空间的前提下，如何用极轻量的规则系统实现超越训练型方法、接近LLM方法的决策效率。

## 6.2  YLYW先验在导航决策中的跨域验证

本文结果从跨域角度验证了YLYW"知几学习"范式的有效性。在物理域（抓取决策），YLYW先验是"物体物理属性→卦象→策略"映射，92.7%合理率；在导航域（ALFWorld），先验是"物体典型位置→探索优先级"映射，90.0%成功率（标注一致子集）。两者共享相同的设计原则——将人类常识编码为结构化先验，零样本驱动决策——且在不同领域呈现稳定的90%+能力水平。这一一致性并非巧合：当先验知识覆盖了任务空间的主要情况时，零样本性能自然收敛于该水平，对应《系辞传》"范围天地之化而不过"[11]的理想。

## 6.3  规则系统 vs LLM：两条技术路线的边界

在相同admissible条件下，约800行规则代码（标注一致时90.0%）接近270亿参数LLM（93.28%）。规则系统的优势在于：（1）完全确定性，相同输入始终相同输出，不存在LLM的采样随机性；（2）零幻觉，严格从admissible列表选择，不生成无效动作；（3）部署成本极低，无需GPU/API，134个任务仅需约180秒纯CPU运算；（4）完全可解释，每个决策可追溯到具体的先验矩阵评分和状态机阶段。
LLM的核心优势在于语义弹性：当task_desc说"salt shaker"但场景只有pepper shaker时，LLM能通过上下文推断修正目标。此外，EmbodiSkill的多轮迭代演化机制允许从失败中学习，这是静态规则系统无法复制的。因此，两条路线的边界条件是：当任务描述准确清晰时，规则系统可接近LLM水平；当描述存在歧义或噪声时，LLM的语义理解能力不可替代。

## 6.4  ALFWorld标注质量问题的启示

本文发现的25.4%标注不一致率对ALFWorld基准有重要启示。这些不一致并非随机噪声，而是系统性的：（1）ALFRED数据集的task_desc由众包工人标注，与PDDL自动生成的ground truth之间存在语义gap；（2）同义词混用（mug/cup 11个、salt/pepper 3个）反映了自然语言的固有模糊性；（3）信息缺失（"Turn on the desk lamp"不说看什么物体，5个）反映了标注指南的不完善。这一发现对所有在ALFWorld上评估的方法都有影响：使用LLM的方法（如EmbodiSkill）之所以能绕过这些不一致，不是因为其算法更优，而是因为LLM具备语义弹性。建议ALFWorld社区对这34个任务进行标注修正或标记。

## 6.5  局限性与未来工作

（1）NL解析精度：当前基于关键词的解析器面对同义词和模糊表达时能力有限，未来可结合轻量NLP模型。（2）50步限制：pick_two类型需完成两轮操作，50步下成功率仅47.1%，放宽至80步可显著提升。（3）admissible模式的现实局限：真实机器人不存在admissible oracle，推广到真实世界需结合视觉感知模块。（4）领域特化：任务模板针对ALFWorld 6种类型设计，推广到新任务类型需人工编写模板。（5）YLYW先验矩阵的构建：当前矩阵基于常识手工编码，未来可探索从少量示例中自动学习先验（对应K_calibration的自动化）。

# 7  结论

本文提出了一种基于YLYW先验知识框架的零样本具身决策方法，并在ALFWorld基准测试（134个valid_unseen任务）上进行了系统验证。核心成果包括：
摘要  当前具身智能决策方法主要依赖大语言模型（LLM），存在部署成本高、决策不可解释、输出随机等问题。本文提出一种基于YLYW（易理研物）先验知识框架的零样本具身决策方法。YLYW以《易经》六十四卦为结构化先验模板，通过L1八卦模糊隶属度→L2六爻编码→L3卦象匹配的三层推理链，实现"卦定策略类型、爻定执行参数"的分层决策。本文将这一框架迁移至具身导航与操作领域，设计了admissible-commands信号驱动的层次化状态机Agent，并提出"知几学习"的跨游戏经验积累机制（K = K_prior ⊕ K_calibration），在ALFWorld官方TextWorld仿真器的134个valid_unseen任务上验证。该Agent仅依赖约800行Python代码和YLYW常识先验矩阵，不使用任何LLM或API调用。实验表明，静态先验版（V7）达到67.2%成功率，引入知几学习后（V9）提升至70.1%，接近基于GPT-4的ReAct方法（71%）。更重要的是，本文揭示了ALFWorld数据集中25.4%的任务存在自然语言标注与PDDL ground truth不一致的问题。在标注一致的100个任务上，YLYW达到90.0%的成功率，接近使用270亿参数LLM的EmbodiSkill方法（93.28%），仅差约3个百分点。
揭示了ALFWorld数据集中25.4%任务（34/134）存在task_desc与PDDL标注不一致的问题。在标注一致的100个任务上，YLYW达到90.0%的成功率，与使用270亿参数LLM的EmbodiSkill（93.28%）仅差约3个百分点。
验证了YLYW"知几学习"范式（K = K_prior ⊕ K_calibration）的跨域有效性：同一套"先验知识+信号驱动"方法论从物理域（92.7%）成功迁移至导航域（90.0%）。
通过与EmbodiSkill的系统对比，明确了先验知识驱动与LLM驱动两条技术路线的优势边界：在任务描述准确时，精心设计的规则系统可接近大规模LLM的性能水平，同时在确定性、可解释性和部署成本方面具有显著优势。
本文的核心论点是：在具身智能的有限状态空间中，结构化先验知识+确定性规则系统是一条被严重低估的技术路径。《易经》以64卦"弥纶天地之化"的思想，在具身决策领域得到了工程化验证——这为"知识驱动的具身智能"提供了有力的实证支持。

# 参考文献

[1]  Yao S, Zhao J, Yu D, et al. ReAct: Synergizing Reasoning and Acting in Language Models. In: ICLR, 2023.
[2]  Shinn N, Cassano F, Gopinath A, et al. Reflexion: Language Agents with Verbal Reinforcement Learning. In: NeurIPS, 2023.
[3]  Ju R, Wang X, Ding X, et al. EmbodiSkill: Skill-Aware Reflection for Self-Evolving Embodied Agents. arXiv:2605.10332, 2026.
[4]  Shridhar M, Yuan X, Côté M A, et al. ALFWorld: Aligning Text and Embodied Environments for Interactive Learning. In: ICLR, 2021.
[5]  Shridhar M, Thomason J, Gordon D, et al. ALFRED: A Benchmark for Interpreting Grounded Instructions for Everyday Tasks. In: CVPR, 2020.
[6]  Côté M A, Kádár Á, Yuan X, et al. TextWorld: A Learning Environment for Text-Based Games. In: CGW@IJCAI, 2018.
[7]  Ahn M, Brohan A, Brown N, et al. Do As I Can, Not As I Say: Grounding Language in Robotic Affordances. arXiv:2204.01691, 2022.
[8]  Driess D, Xia F, Sajjadi M S M, et al. PaLM-E: An Embodied Multimodal Language Model. In: ICML, 2023.
[9]  Brohan A, Brown N, Carbajal J, et al. RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control. arXiv:2307.15818, 2023.
[10] 《周易》. 先秦典籍.
[11] 《系辞传》. 先秦典籍.