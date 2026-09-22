import docx
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

doc = Document('易理研物（初稿）.docx')
paras = doc.paragraphs
body = doc.element.body
print(f"Document loaded. Total paragraphs: {len(paras)}")

def make_paragraph(style_name, text):
    """Create a new w:p element with given style and text."""
    new_p = OxmlElement('w:p')
    if style_name:
        style_elem = OxmlElement('w:pStyle')
        style_elem.set(qn('w:val'), style_name)
        new_p.insert(0, style_elem)
    if text is not None:
        run_elem = OxmlElement('w:r')
        new_p.append(run_elem)
        t_elem = OxmlElement('w:t')
        t_elem.text = text
        t_elem.set(qn('xml:space'), 'preserve')
        run_elem.append(t_elem)
    return new_p

def insert_paras_at(doc, before_idx, paras_data):
    """
    Insert paragraphs in correct order before a given paragraph index.
    paras_data is a list of {style, text} dicts in document order.
    """
    body = doc.element.body
    # Get fresh reference
    fresh_paras = doc.paragraphs
    target_elem = fresh_paras[before_idx]._element
    target_pos = list(body).index(target_elem)
    
    # Insert in order: first item goes first, so insert each at target_pos
    # and increment target_pos each time
    for i, pdata in enumerate(paras_data):
        new_p = make_paragraph(pdata.get('style'), pdata.get('text'))
        body.insert(target_pos + i, new_p)
    
    return before_idx + len(paras_data)


# ============================================================
# MODIFICATION 1: Insert 2.6 section before para 379 (H2 "2.5 本章小结")
# ============================================================
print("\n===== MODIFICATION 1: Insert 2.6 section =====")

section_2_6 = [
    # Heading 2
    {'style': 'Heading 2', 'text': '2.6 汉字语义引擎：符号接地的跨模态扩展'},
    {'style': 'Normal', 'text': '第2.1到2.5节解决了物理世界的符号接地问题——将13维物理特征映射为八卦隶属度和六爻符号向量。但物理特征只是智能系统需要感知的一类输入。在ALFWorld导航任务中，智能体接收的不是物理传感器的数值，而是自然语言文本——"你看到一张桌子，上面有一个杯子"。这里存在一个新的接地问题：如何将汉字文本的语义映射到八卦符号空间？'},
    {'style': 'Normal', 'text': '本节报告汉字语义引擎的设计——一个递归的三层YLYW推理架构（字→词→句），基于部首八卦隶属度将汉字文本逐级映射为六爻向量和卦象。这一引擎是第6.4节ALFWorld实验的底层语义基础。'},
    {'style': 'Normal', 'text': '——————————————————————————————'},
    # 2.6.1
    {'style': 'Heading 3', 'text': '2.6.1 从"测字"到计算：汉字部首的八卦隶属度'},
    {'style': 'Normal', 'text': '《易传·系辞》云："古者包牺氏之王天下也，仰则观象于天，俯则观法于地，观鸟兽之文与地之宜，近取诸身，远取诸物，于是始作八卦。"这一"观物取象"的方法论，与汉字构造的"六书"原理（象形、指事、会意、形声）在认知逻辑上是同构的——两者都是从具体事物中抽象出符号。'},
    {'style': 'Normal', 'text': '汉字语义引擎的核心数据结构是一张部首→八卦模糊隶属度映射表。每个常见偏旁部首被分配一个8维隶属度向量，表示该部首在"乾兑离震巽坎艮坤"八个语义维度上的归属程度。这些隶属度来自汉字学直觉和《说卦传》的万物类象思想，不从数据学习。'},
    {'style': 'Normal', 'text': '表2.7 部分部首→八卦隶属度映射示例（共约40个部首）'},
    # Table rows as text
    {'style': 'Normal', 'text': '| 部首 | 示例字 | 主导八卦 | 主导隶属度 | 易理依据 |'},
    {'style': 'Normal', 'text': '|------|--------|----------|-----------|---------|'},
    {'style': 'Normal', 'text': '| 氵（三点水） | 江、河、湖、海 | 坎（水） | 0.95 | 水性坎险 |'},
    {'style': 'Normal', 'text': '| 火（火字旁） | 烧、烤、灯、炎 | 离（火） | 0.95 | 火为离明 |'},
    {'style': 'Normal', 'text': '| 木（木字旁） | 树、林、材、板 | 震（木） | 0.95 | 动为震木 |'},
    {'style': 'Normal', 'text': '| 扌（提手旁） | 打、推、拉、抓 | 乾（健） | 0.80 | 动手为乾 |'},
    {'style': 'Normal', 'text': '| 口（口字旁） | 吃、喝、唱、叫 | 兑（口） | 0.95 | 兑为口舌 |'},
    {'style': 'Normal', 'text': '| 土（提土旁） | 地、场、城、墙 | 坤（地） | 0.90 | 坤为地载 |'},
    {'style': 'Normal', 'text': '| 石（石字旁） | 矿、砖、破、碎 | 艮（山） | 0.85 | 艮为山石 |'},
    {'style': 'Normal', 'text': '| 日（日字旁） | 明、晴、时、晶 | 离（光） | 0.90 | 离为日明 |'},
    {'style': 'Normal', 'text': '| 女（女字旁） | 好、安、孝、始 | 坤（柔） | 0.80 | 坤为柔顺 |'},
    {'style': 'Normal', 'text': '| 月（肉月旁） | 肌、肤、肺、肝 | 坤（体） | 0.75 | 坤为肉身 |'},
    {'style': 'Normal', 'text': '| 目（目字旁） | 看、眼、睛、盯 | 离（目） | 0.85 | 离为目明 |'},
    {'style': 'Normal', 'text': '| 足（足字旁） | 跑、跳、踢、踩 | 震（动） | 0.65 | 震为足行 |'},
    {'style': 'Normal', 'text': '| 车（车字旁） | 轮、轴、辆、轨 | 震（动） | 0.85 | 震为动转 |'},
    {'style': 'Normal', 'text': '| 饣（食字旁） | 饭、饱、餐、饮 | 兑（口） | 0.75 | 兑为口食 |'},
    {'style': 'Normal', 'text': '| 钅（金字旁） | 铁、钢、银、针 | 乾（刚） | 0.85 | 乾为金玉 |'},
    {'style': 'Normal', 'text': '| 辶（走之旁） | 过、远、近、进 | 震（行） | 0.75 | 震为行动 |'},
    {'style': 'Normal', 'text': '| 宀（宝盖头） | 家、安、室、定 | 艮（止） | 0.75 | 艮为安居 |'},
    {'style': 'Normal', 'text': '当未知部首出现时，系统通过部首拆分表（约309个常用汉字的部首分解）和形似物象兜底法进行估算。例如，"品"字由三个"口"组成→整体取象为兑卦（兑为口舌）。这模拟了传统测字学中的"观形取象"方法——看字的外形像什么卦象。'},
    {'style': 'Normal', 'text': '——————————————————————————————'},
    # 2.6.2
    {'style': 'Heading 3', 'text': '2.6.2 递归三层架构：字→词→句的YLYW推理链'},
    {'style': 'Normal', 'text': '单个汉字的八卦隶属度只解决了"字"级语义。但自然语言理解需要更丰富的组合语义——"关上"不等于"关"+"上"，"打开柜子"是一个整体动作场景。汉字引擎通过递归YLYW架构解决这一问题：字、词、句三个层级各有一个完整的YLYW推理层，下层输出卦象作为上层输入的八卦隶属度。'},
    {'style': 'Normal', 'text': '字级YLYW（L0→L1字）。输入：部首拆分→部首八卦隶属度。处理：通过部首间乘承比应关系（两个部首的语义互动，如"火"+"丁"="打"→火的光明+丁的稳固→乾卦主导）计算六爻值。输出：单个汉字的8维八卦隶属度向量。'},
    {'style': 'Normal', 'text': '词级YLYW（L1字→L2词）。输入：多个汉字的八卦隶属度向量。处理：计算字间乘承比应（例如"打"的乾卦+"开"的兑卦→乾兑组合为"决断开放"语义→六爻向量的初爻和中爻被激活）。输出：该词的8维卦象、6维爻向量、最佳匹配64卦。'},
    {'style': 'Normal', 'text': '句级YLYW（L2词→L3句）。输入：多个词的卦象向量。处理：词间乘承比应关系（动词→物体的"乘"关系、形容词→名词的"承"关系、跨虚词的关联等）。输出：整句的卦象、六爻和主卦。'},
    {'style': 'Normal', 'text': '这一递归架构与第3章的L1→L2→L3架构在算法上是同构的——每一层的YLYWLayer类都使用相同的perceive_and_encode()方法，仅在输入语义和乘承比应的判据上有所不同。这验证了第1.3.1节的"道器合一"命题：同一套八卦推理框架可以跨越物理感知和语言理解两个截然不同的域。'},
    {'style': 'Normal', 'text': '六爻编码的改进：交替混合深度法。汉字引擎的六爻编码与物理域的六爻编码不同——物理域的初爻锚定稳定性、二爻锚定可达性等，而汉字域的六爻编码不再有固定的爻位语义，而是采用动作-物体交替混合深度法。每爻的值由动作元素卦象和物体元素卦象按交替权重混合得出。动作权重在奇偶爻位间交替变化，确保同一动作+不同物体的组合在每爻都有差异。'},
    {'style': 'Normal', 'text': '乘承比应在汉字域的重新定义。在汉字域中，乘承比应的判据不再基于物理力传递，而是基于词间语义关系：'},
    {'style': 'Normal', 'text': '- 乘（动作→物体）：动词在前、名词在后时，动词的卦象"作用"于名词的卦象。例："打开"（震）→ "柜子"（艮）→ 乘关系，表示动作施加于物体。'},
    {'style': 'Normal', 'text': '- 承（物体→动作）：名词在前、动词在后时，名词的卦象"承载"动词的卦象。例："用刀"（兑）→ "切菜"（震）→ 承关系，表示工具辅助动作。'},
    {'style': 'Normal', 'text': '- 比（同角色相邻）：两个同为动作或同为物体的词相邻时，判断它们是否协同。'},
    {'style': 'Normal', 'text': '- 应（同卦相隔）：间隔两个位置以上的词如果主导八卦相同，建立呼应关系。'},
    {'style': 'Normal', 'text': '这一重新定义使得汉字引擎可以处理自然语言中的各种语义结构——不仅是"动作+物体"的简单组合，还包括"属性+物体"（如"脏的盘子"）、"位置+物体"（如"水槽边的肥皂"）、以及复杂的嵌套结构。'},
    {'style': 'Normal', 'text': '——————————————————————————————'},
    # 2.6.3
    {'style': 'Heading 3', 'text': '2.6.3 汉字万物类象知识库与词义推理'},
    {'style': 'Normal', 'text': '部首隶属度提供了汉字的"底层语义"。但在ALFWorld场景中，系统需要处理的不是单个汉字，而是特定的家居物品名称和操作指令。为此，汉字引擎还维护了一个万物类象知识库——约200个ALFWorld高频实体的手工八卦向量。'},
    {'style': 'Normal', 'text': '万物类象的赋值原则遵循《说卦传》的八卦取象体系：'},
    {'style': 'Normal', 'text': '- 艮（山/止）系：果实类物体（苹果、番茄、土豆），静止的家具（柜子、桌子）——艮为山、为果实、为止。'},
    {'style': 'Normal', 'text': '- 坎（水/陷）系：液体和冷藏相关（冰箱、水槽、饮料），以及需要清洗的物品——坎为水、为陷、为洗涤。'},
    {'style': 'Normal', 'text': '- 离（火/明）系：光源和热源（台灯、灶台、微波炉），以及清洁状态（干净、热）——离为火、为明。'},
    {'style': 'Normal', 'text': '- 震（雷/动）系：动作动词（拿、去、打开），以及可动工具（刀、叉）——震为动、为雷。'},
    {'style': 'Normal', 'text': '- 巽（风/入）系：柔性放置（毛巾、布、放），以及渗透或扩散的操作——巽为风、为入。'},
    {'style': 'Normal', 'text': '- 乾（天/健）系：刚硬物体（金属锅、勺子、笔），强力的动作（用力、推）——乾为天、为刚健。'},
    {'style': 'Normal', 'text': '- 兑（悦/口）系：与口相关的物品（食物、饮料），言语交流——兑为口、为悦。'},
    {'style': 'Normal', 'text': '- 坤（地/顺）系：承载类物品（盘子、碗、碟、床），以及容器——坤为地、为载、为母。'},
    {'style': 'Normal', 'text': '万物类象的多点激活特性。一个物体通常同时激活多个卦象。例如：'},
    {'style': 'Normal', 'text': '- "苹果" → 艮（山/果）0.85 + 兑（悦/食）0.35 + 坤（载/容）0.25'},
    {'style': 'Normal', 'text': '- "微波炉" → 离（火/热）0.65 + 乾（刚/健）0.40 + 坤（载/容）0.25'},
    {'style': 'Normal', 'text': '- "冰箱" → 坎（水/冷）0.75 + 乾（刚/健）0.30 + 艮（止/藏）0.20'},
    {'style': 'Normal', 'text': '卦象语义泛化。以"橱柜"为例：橱由"木"（震卦0.95）+ "厨"的声旁（宅中有厨，坤卦0.60）组合而成——经过YLYW六爻推理后，橱柜的整体卦象为艮（止/藏，隶属度0.65）+ 坤（载/容，隶属度0.50），与"桌子"（巽+坤）、"抽屉"（艮+坤）属于同一器物家族的语义邻居。这种"卦象语义近似"使得系统可以泛化：即使从未见过"橱柜"这个物体，只要知道它属于艮+坤族，就能推断它是静止、容纳型家具——与已知的"桌子""抽屉"同类。'},
    {'style': 'Normal', 'text': '歧义消解机制。汉字语义引擎还设计了一套基于卦象的歧义消解机制。当物体有多个可能的卦象归属时（如"热咖啡"——咖啡属坎水，但"热"修饰后整体偏向离火），系统通过以下方式消歧：'},
    {'style': 'Normal', 'text': '1. 属性优先规则：形容词卦象（离/坎）对名词卦象（艮/坤）的"承"关系具有优先级——"热咖啡"中，离卦的"热"修饰坎卦的"咖啡"，主导语义为"需要加热的饮料"，卦象倾向离+坎。'},
    {'style': 'Normal', 'text': '2. 上下文增益：句级YLYW中，动词的卦象会通过乘承关系影响名词的最终卦象——"喝咖啡"中，"喝"（兑卦，口舌）的乘关系激活了咖啡的兑卦分量（饮用品属性），使咖啡从单纯的"坎水"变为"坎+兑"。'},
    {'style': 'Normal', 'text': '——————————————————————————————'},
    # 2.6.4
    {'style': 'Heading 3', 'text': '2.6.4 ALFWorld中的端到端语义推理实例'},
    {'style': 'Normal', 'text': '以ALFWorld典型任务"把加热后的杯子放到桌上"为例，展示汉字引擎的完整推理链：'},
    {'style': 'Normal', 'text': '步骤1：字级感知。'},
    {'style': 'Normal', 'text': '- 杯 → "木"（震0.85）+ "不"（否卦，否定义→坤0.40）→ YLYW输出：震+坤=容器卦象'},
    {'style': 'Normal', 'text': '- 子 → 子(儿)字（震0.45+坤0.30）→ YLYW输出：震（子为动、小儿）'},
    {'style': 'Normal', 'text': '- 桌 → "木"（震0.85）+ "卓"（高立→乾0.35）→ YLYW输出：巽+坤=平面承载'},
    {'style': 'Normal', 'text': '- 上 → 指事字（一竖之上）→ 离+兑=上方/光明'},
    {'style': 'Normal', 'text': '步骤2：词级融合。'},
    {'style': 'Normal', 'text': '- "杯子"→ 杯(震+坤)+子(震) → YLYW词级推理：主导坤(0.55) 坎(0.40)，卦象匹配→坤为地（䷁）'},
    {'style': 'Normal', 'text': '- "桌上"→ 桌(巽+坤)+上(离+兑) → YLYW词级推理：主导巽(0.50)坤(0.45)，卦象匹配→风地观（䷓）'},
    {'style': 'Normal', 'text': '步骤3：句级推理。'},
    {'style': 'Normal', 'text': '- 分词："把"（虚词）+ "加热"（动词）+ "后"（时序词）+ "的"（虚词）+ "杯子"（物体）+ "放"（动词）+ "到"（虚词）+ "桌上"（位置）'},
    {'style': 'Normal', 'text': '- 词间乘承比应：'},
    {'style': 'Normal', 'text': '  - "加热"的离卦（火/热）→ "杯子"的坤卦（容器）→ 乘关系（火作用于容器）'},
    {'style': 'Normal', 'text': '  - "放"的巽卦（放置）→ "桌上"的风地观卦 → 承关系（放置于位置）'},
    {'style': 'Normal', 'text': '- YLYW句级输出：主卦→火风鼎（䷱，鼎为烹饪、加热容器）'},
    {'style': 'Normal', 'text': '- 六爻向量→[0.28, 0.65, 0.72, 0.55, 0.38, 0.70]'},
    {'style': 'Normal', 'text': '步骤4：策略映射。'},
    {'style': 'Normal', 'text': '- 火风鼎卦的策略语义："鼎，象也。以木巽火，亨饪也"——加热容器并完成操作'},
    {'style': 'Normal', 'text': '- 策略映射：pick_and_place_with_heating，力预设=0.55，速度=slow，接近角度=45°'},
    {'style': 'Normal', 'text': '- 可解释摘要："加热后杯子置桌上，似火风鼎（䷱），鼎中烹物，以巽风吹火，熟而奉上"'},
    {'style': 'Normal', 'text': '——————————————————————————————'},
    # 2.6.5
    {'style': 'Heading 3', 'text': '2.6.5 本节小结'},
    {'style': 'Normal', 'text': '本节展示了YLYW符号接地方法从物理域到语言域的跨模态扩展。汉字语义引擎的核心贡献有三：'},
    {'style': 'Normal', 'text': '- 部首八卦隶属度表：将约40个常见偏旁部首映射到8维八卦语义空间，为汉字理解提供了先验语义基元。'},
    {'style': 'Normal', 'text': '- 递归三层架构：字→词→句，每层运行同构的YLYW推理，下层卦象输出作为上层输入，实现了从部首到句子语义的渐进式构建。'},
    {'style': 'Normal', 'text': '- 万物类象知识库：约200个高频实体的八卦向量，将《说卦传》的取象传统工程化为可计算的知识基。'},
    {'style': 'Normal', 'text': '汉字引擎的完整代码实现约1471行Python，纯CPU运行。其设计哲学与第2.1-2.5节的物理接地方案完全一致：均以八卦隶属度为底层基元，以六爻编码为结构化表示，以64卦匹配为推理终点。这一一致性验证了YLYW符号接地方案的多模态通用性。'},
    {'style': 'Normal', 'text': '关于汉字引擎在ALFWorld端到端系统中的集成、六爻编码为任务规划提供的结构化驱动，以及从V7到V20的技术演进，将在第6.4.3.1节详细报告。'},
    {'style': 'Normal', 'text': '——————————————————————————————'},
    {'style': 'Normal', 'text': '*本节完。下一节：第三章 六十四卦联邦架构设计。*'},
]

print(f"  Inserting {len(section_2_6)} paragraphs before para 379 (H2 '2.5 本章小结')...")

# Insert in order before the target element using addprevious
target_elem = paras[379]._element

for pdata in section_2_6:
    new_p = make_paragraph(pdata.get('style'), pdata.get('text'))
    # Insert directly before target element
    target_elem.addprevious(new_p)

print("  Done! Section 2.6 inserted.")

doc.save('temp1.docx')
print("  Saved to temp1.docx")

# Reload to check
del doc, paras, body

doc2 = Document('temp1.docx')
paras2 = doc2.paragraphs
print(f"Total paragraphs after mod1: {len(paras2)}")
for i, p in enumerate(paras2):
    if p.style.name.startswith('Heading') and ('2.5' in p.text[:10] or '2.6' in p.text[:10]):
        print(f"  [{i}] {p.style.name}: {p.text[:60]}")
    if '2.6 汉字语义引擎' in p.text:
        print(f"  [{i}] style={p.style.name}: {p.text[:60]}")

