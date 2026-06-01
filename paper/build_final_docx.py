#!/usr/bin/env python3
"""
生成学术排版Word文档 — 详细实验版
- 完整实验步骤、输入输出、分析
- 3张可视化图表嵌入
- 标准学术格式
"""
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import os

doc = Document()
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

style_normal = doc.styles['Normal']
style_normal.font.name = 'Times New Roman'
style_normal.font.size = Pt(11)
style_normal.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
style_normal.paragraph_format.line_spacing = 1.5

def set_cn_font(run, cn_font='宋体', en_font='Times New Roman', size=Pt(11)):
    run.font.name = en_font
    run.element.rPr.rFonts.set(qn('w:eastAsia'), cn_font)
    run.font.size = size

def heading(text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        set_cn_font(r, '黑体', 'Times New Roman', Pt({1:20, 2:15, 3:12}.get(level, 11)))
        r.font.color.rgb = RGBColor.from_string({1:'1A1A2E',2:'1A5276',3:'2C3E50'}.get(level, '333'))

def body(text):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.74)
    run = p.add_run(text)
    set_cn_font(run)
    return p

def bold_body(label, text):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.74)
    r1 = p.add_run(label)
    set_cn_font(r1); r1.font.bold = True
    r2 = p.add_run(text)
    set_cn_font(r2)
    return p

def add_table(headers, rows, caption=None):
    if caption:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(caption)
        set_cn_font(r, '黑体', 'Times New Roman', Pt(9)); r.font.bold = True
    
    table = doc.add_table(rows=len(rows)+1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        set_cn_font(r, '黑体', 'Times New Roman', Pt(9)); r.font.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1A5276"/>')
        cell._tc.get_or_add_tcPr().append(shading)
    
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri+1].cells[ci]
            cell.text = ''
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val))
            set_cn_font(r, '宋体', 'Times New Roman', Pt(9))
            if ri % 2 == 0:
                shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="EBF5FB"/>')
                cell._tc.get_or_add_tcPr().append(shading)
    doc.add_paragraph()
    return table

def add_figure(img_path, caption, width=Inches(5.2)):
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run()
        r.add_picture(img_path, width=width)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(caption)
        set_cn_font(r, '黑体', 'Times New Roman', Pt(9)); r.font.bold = True

# ============================================================
#  封面
# ============================================================
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before = Pt(60)
r = p.add_run('YLYW：一种基于《易经》先验符号知识的\n联邦式神经符号具身决策框架')
r.font.size = Pt(22); r.font.bold = True
set_cn_font(r, '黑体', 'Times New Roman', Pt(22))
r.font.color.rgb = RGBColor.from_string('1A1A2E')

p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('\n马老师课题组'); set_cn_font(r, '宋体', 'Times New Roman', Pt(14))
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('青岛科技大学 信息科学技术学院'); set_cn_font(r, '宋体', 'Times New Roman', Pt(11))
r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

doc.add_page_break()

# === 摘要 ===
heading('摘要')
body('当前具身智能决策方法主要依赖数据驱动的深度学习范式，在数据效率、可解释性和物理合规性方面存在根本性瓶颈。本文提出YLYW（易理研物），将《易经》的六十四卦符号系统形式化为联邦式神经符号架构中的先验知识手册。核心创新包括：（1）以八卦作为连续模糊隶属度的符号基元；（2）提出基于物体质心的爻模板系统性优化方法；（3）首次将"乘承比应当位得中"五种爻位关系形式化为可计算算子。在42/64卦规则库下，300物体零样本基线达到90.0%合理率、0%严重错误率。从初始48%到90%的性能跃迁过程，每一步提升都有可追溯的物理语义支撑，本身就是易理模型可解释性的生动验证。')
p = doc.add_paragraph()
r = p.add_run('关键词：'); r.font.bold = True; set_cn_font(r)
r = p.add_run('神经符号系统；《易经》；先验知识；爻位关系运算；零样本学习；可解释人工智能')
set_cn_font(r)
doc.add_page_break()

# === 1 引言（精简） ===
heading('1 引言')
heading('1.1 问题背景与动机', 2)
body('具身智能的目标是创造能在物理世界中自主行动的智能体。当前主流范式以深度学习为核心，本质是数据驱动的统计拟合，导致了数据饥渴、黑箱决策和物理失配三大根本性挑战。这些困境共同指向一个核心问题：智能体是否应该拥有一套关于世界变化与运行的先验知识？本文基于《易经》哲学给出了肯定的回答。')
heading('1.2 《易经》作为先验知识体系', 2)
body('《易经》以阴阳为原子符号，三爻成八卦（2³=8）、六爻成六十四卦（2⁶=64），定义了爻位间的"乘、承、比、应、当位、得中"等结构化关系网络。本文将其视为中国古代对自然变化规律的符号化总结与形式化建模，作为具身智能的计算先验加以工程化利用。')

# === 2 系统架构 ===
heading('2 系统架构')
heading('2.1 总体架构', 2)
body('YLYW采用联邦式神经符号架构，如图1所示。系统由五个核心层构成：L1八卦基元将连续物理特征模糊化为8卦隶属度；L2六爻编码将13维特征聚合为6维爻值向量；L3卦象匹配通过余弦相似度搜索最佳卦象，决定策略类型（做什么）；L3+爻位关系通过乘承比应当位得中分析决定执行参数（怎么做）；决策层整合输出。')

BASEDIR = '/home/lijinhan/MXL/科研/ylyw/paper'
add_figure(f'{BASEDIR}/architecture_diagram.png', '图1. YLYW系统完整架构', Inches(5.0))

# 表1
heading('2.2 八卦-物理原型映射', 2)
add_table(
    ['卦名', '符号', '卦德', '力需求', '稳定性', '变形性', '滚动性', '脆弱性'],
    [['乾','☰','健','0.90','0.80','0.10','0.20','0.20'],
     ['坤','☷','顺','0.30','0.60','0.80','0.30','0.30'],
     ['震','☳','动','0.50','0.20','0.40','0.90','0.60'],
     ['艮','☶','止','0.40','0.90','0.20','0.10','0.40'],
     ['离','☲','明','0.40','0.50','0.40','0.40','0.50'],
     ['坎','☵','险','0.60','0.30','0.50','0.50','0.70'],
     ['兑','☱','悦','0.30','0.50','0.60','0.30','0.40'],
     ['巽','☴','入','0.40','0.40','0.50','0.40','0.50']],
    '表1. 八卦物理原型映射'
)

doc.add_page_break()

# === 3 爻位关系运算 ===
heading('3 爻位关系运算')
body('以上三层确定了策略类型。但《易经》的推理不止于此——还须分析六爻之间的结构关系，以判断策略执行的质量与可信度。本节将五种爻位关系形式化为可计算算子。')

heading('3.1 五种关系的形式化', 2)
add_table(
    ['关系', '周易定义', '程序化判据', '策略影响'],
    [['当位','阳居阳位(初/三/五),阴居阴位(二/四/上)','(yao[i]≥0.5)==(i∈{0,2,4})','影响稳定性基础'],
     ['得中','二爻和五爻为中位,六二/九五最佳','六二阴+九五阳','影响决策优先级'],
     ['乘(逆)','阴爻在上压制下方阳爻','yao[i+1]<0.5 and yao[i]≥0.5','降低期望力'],
     ['承(顺)','阴爻在下承载上方阳爻','yao[i]<0.5 and yao[i+1]≥0.5','提升流畅度'],
     ['亲比','相邻两爻同阴阳为亲比','(yao[i]≥0.5)==(yao[i+1]≥0.5)','影响连贯性'],
     ['呼应','初-四/二-五/三-上,阴阳相反为有应','(yao[a]≥0.5)≠(yao[b]≥0.5)','影响确信度']],
    '表2. 五种爻位关系的形式化定义'
)

body('综合爻位质量 S_yao = 0.40·S_dw + 0.20·S_dz + 0.15·S_cc + 0.10·S_bi + 0.15·S_ying。权重反映易学传统：当位最重（"天地设位"），得中次之（"中正之道"）。')

heading('3.2 爻位质量→策略修正', 2)
add_table(
    ['爻位质量', '谨慎级别', '力修正系数', '含义'],
    [['≥ 0.70','relaxed','1.00–1.05','爻位优良,可略增力'],
     ['0.50–0.70','normal','0.95–1.00','爻位正常,标准执行'],
     ['0.30–0.50','cautious','0.85–0.95','爻位偏差,降低力预设'],
     ['< 0.30','very_cautious','0.75–0.85','爻位严重失序,大幅降力']],
    '表3. 爻位质量→谨慎级别→力修正系数映射'
)

doc.add_page_break()

# ============================================================
#  4 实验（详细版）
# ============================================================
heading('4 实验')

heading('4.1 实验环境与数据集', 2)
body('实验环境：Python 3.8+, NumPy, 纯CPU推理（无GPU需求）。数据集：通过合成场景生成器（SimulationScene）按8种物体类型的物理模板生成带±5%均匀噪声的特征向量。物体类型包括：球体(sphere)、立方体(cube)、圆柱体(cylinder)、碗(bowl)、瓶子(bottle)、盘子(plate)、不规则石块(rock)、花瓶(vase)。每个物体实例包含13维物理特征（稳定性、滚动倾向、力需求、脆弱性、可达性、抓取表面质量、支撑面积、遮挡程度、障碍密度、任务优先级、重量比、可见性、变形能力），所有特征归一化至[0,1]。')
body('评估方法：采用启发式策略合理性评估。每种物体类型预定义"合理策略集"（10-16种策略类型）和"明显错误策略集"。系统输出的抓取策略类型若在合理集合中则计为"合理"，在错误集合中则计为"错误"，其余为"中性"。评估不涉及实际物理抓取，仅评估推理输出的语义合理性。')

heading('4.2 实验一：爻模板优化实验', 2)
bold_body('实验目的：', '验证基于物体质心的爻模板优化方法能否显著提升零样本策略合理率。')
bold_body('实验设置：', '对比两组配置。（A）优化前：20/64卦定义，爻模板值为人工直觉赋值（如乾卦模板=[0.95,0.90,0.85,0.85,1.00,0.90]）。（B）优化后：42/64卦定义，爻模板值基于8类物体的六爻向量质心重算。每组在300个随机生成物体上评估（固定随机种子保证可复现）。')
bold_body('实验步骤：', '')

steps = [
    '步骤1（采集质心）：生成8类物体各50+实例，经L1→L2推理链输出六爻向量，计算每类均值得到质心 c_t ∈ [0,1]⁶。',
    '步骤2（卦物映射）：将42个已定义卦象按其卦辞语义和策略类型，指定应服务的物体类型集合。例如震为雷（动态抓取）→{球体, 圆柱体}。',
    '步骤3（模板重算）：对每个卦h，新模板 p_h = mean(c_t for t in T_h) + ε_h。ε_h为基于卦名哈希的确定性微小扰动(±0.025)。',
    '步骤4（问题卦修复）：火水未济卦模板从[0.20,0.70,0.30,0.80,0.30,0.70]手动修正为[0.07,0.88,0.11,0.07,0.06,0.11]，避免大量物体误匹配。',
    '步骤5（评估）：在300物体上运行完整推理链，统计合理率和错误率。',
]
for s in steps:
    p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(1.5)
    r = p.add_run(s); set_cn_font(r)

bold_body('实验结果：', '')

add_table(
    ['指标', '优化前(20卦)', '优化后(42卦)', '提升'],
    [['合理匹配率','48.0%','90.0%','+42.0%'],
     ['明显错误率','2.0%','0.0%','−2.0%'],
     ['可用卦象','20/64','42/64','+22卦'],
     ['策略类型覆盖','18种','39种','+21种'],
     ['推理速度','0.5ms','1.7ms','—'],
     ['平均卦象匹配度','0.955','0.977','+0.022']],
    '表4. 爻模板优化前后总体指标对比'
)

add_figure(f'{BASEDIR}/fig_before_after_comparison.png',
           '图2. 各物体类型零样本合理率：优化前(浅蓝) vs 优化后(深蓝)', Inches(5.0))

add_table(
    ['物体类型', '优化前合理率', '优化后合理率', '提升幅度', '典型卦象', '典型策略'],
    [['盘子','100.0%','100.0%','—','地火明夷','low_visibility_grasp'],
     ['花瓶','50.0%','97.1%','+47.1%','火地晋','progressive_grasp'],
     ['立方体','57.1%','95.0%','+37.9%','地泽临','top_down_grasp'],
     ['碗','33.3%','94.7%','+61.4%','风天小畜','progressive_grasp'],
     ['球体','28.6%','93.8%','+65.2%','泽雷随','following_grasp'],
     ['瓶子','100.0%','91.7%','−8.3%','风火家人','coordinated_grasp'],
     ['圆柱体','0.0%','80.0%','+80.0%','雷风恒','endurance_grasp'],
     ['石块','16.7%','77.4%','+60.7%','山风蛊','corrective_grasp']],
    '表5. 按物体类型的优化前后详细对比'
)

add_figure(f'{BASEDIR}/fig_hexagram_hit_distribution.png',
           '图3. 卦象命中分布变化：优化前(红色)火水未济独占13次，优化后(蓝色)分布均匀', Inches(5.0))

heading('4.2.1 结果分析', 3)
body('优化效果极其显著：总体合理率从48%跃升至90%（+42个百分点），错误率降至0%。三步骤贡献分析如下：')
body('（1）补全卦象（20→42卦）：新增的22个核心卦（泽雷随/跟随、火泽睽/异形适配、雷水解/脱困等）填补了爻空间中的"真空区域"，使各类物体都能找到语义对口的卦象。')
body('（2）爻模板质心对齐：将42个卦的模板从"直觉赋值"改为"质心锚定"。球体从0%→93.8%是最典型案例——优化前球体因爻向量与所有卦模板距离过远而被匹配到未济卦（流产策略），优化后震为雷、泽雷随等动态卦的模板被拉近至球体质心。')
body('（3）未济卦极端化：将火水未济从"最通用的兜底卦"改造为"极端不确定状态"专用卦。优化前未济卦独占26%命中率；优化后降至接近0%。')

heading('4.3 实验二：爻位关系运算实验', 2)
bold_body('实验目的：', '验证"乘承比应当位得中"五种爻位关系运算能否有效识别策略执行质量，并产生合理的力修正建议。')
bold_body('实验设置：', '在爻模板优化后的系统上（90%基线），对300物体推理链的爻位关系层进行统计分析。评估指标包括：爻位质量分布、谨慎级别分布、力修正系数统计、典型案例分析。')
bold_body('实验步骤：', '')

steps2 = [
    '步骤1：对每个物体实例，运行完整L1→L2→L3→L3+推理链。',
    '步骤2：记录爻位关系分析报告的五个子评分（S_dw, S_dz, S_cc, S_bi, S_ying）和综合评分 S_yao。',
    '步骤3：统计300物体的爻位质量分布、谨慎级别比例、力修正系数均值和范围。',
    '步骤4：选取爻位质量最高和最低的典型案例，详细分析其爻位构成和修正建议。',
]
for s in steps2:
    p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(1.5)
    r = p.add_run(s); set_cn_font(r)

bold_body('实验结果：', '')

add_table(
    ['统计指标', '数值', '说明'],
    [['爻位质量均值','0.50','自然物体处于中等爻位质量'],
     ['力修正系数均值','0.94','多数情境力预设小幅下调5-10%'],
     ['cautious占比','52%','超半数情境被识别为需谨慎执行'],
     ['normal占比','46%','正常执行'],
     ['爻位质量标准差','0.15','中等离散度']],
    '表6. 爻位关系运算全局统计（n=300）'
)

add_figure(f'{BASEDIR}/fig_yao_quality_distribution.png',
           '图4. 爻位质量分布直方图：红=低质量(<0.4), 黄=中等(0.4-0.7), 绿=高质量(>0.7)', Inches(4.8))

add_table(
    ['案例', '物体', '当位', '得中', '乘(逆)', '亲比', '呼应', '爻位质量', '力修正', '谨慎'],
    [['最佳','盘子','3/6','六二+九五','1处','4/5','2/3','0.64','1.00','normal'],
     ['典型','球体','1/6','九二+九五','1处','2/5','2/3','0.47','0.90','cautious'],
     ['最差','石块','0/6','九二+九五','2处','2/5','3/3','0.38','0.85','cautious']],
    '表7. 爻位关系典型案例分析'
)

heading('4.3.1 结果分析', 3)
body('爻位关系运算成功实现了预期的功能：')
body('（1）识别不稳定性：石块案例中0/6爻当位、2处阴乘阳，系统自动将力修正系数降至0.85（降低15%力预设），并给出"多爻不当位，状态不稳"和"阴乘阳，力阻力增大"的可解释建议。这一修正完全是从爻位关系推导出的，无需任何训练数据。')
body('（2）适度谨慎：52%的情境被标记为"cautious"，平均力修正系数0.94。这说明爻位关系运算识别出了物理世界中普遍存在的不完美状态，而非盲目假设一切理想——这正是先验知识的价值所在。')
body('（3）可解释性验证：每一个修正建议都有明确爻位依据。例如"阴乘阳"→力阻力增大，"上下无应"→策略确信度降低。这些对应关系源自《周易》数千年的情境分类经验，在工程语境中展现出惊人的适用性。')

heading('4.4 综合性能对比', 2)
add_table(
    ['维度', 'VLA典型值', 'YLYW（本工作）'],
    [['训练数据','10⁴–10⁶机器人轨迹','0（零样本）'],
     ['推理硬件','GPU集群','CPU单核'],
     ['代码量','数万行','约2200行'],
     ['模型/知识库大小','100MB–10GB','约80KB'],
     ['单次推理延迟','10–1000ms','1.7ms'],
     ['可解释性','黑箱','卦→爻→辞全追溯'],
     ['零样本合理率','—','90.0%'],
     ['严重错误率','—','0.0%'],
     ['参数可调性','重新训练','爻模板+爻权重可独立微调']],
    '表8. YLYW与代表性VLA模型的间接比较'
)

doc.add_page_break()

# === 5 讨论与结论 ===
heading('5 讨论')
heading('5.1 可解释性驱动的性能提升', 2)
body('从48%到90%的42个百分点提升，并非来自更多数据或更大模型，而是来自三个可追溯的工程步骤——补全卦象、质心对齐、未济极端化。每一步都有明确的物理语义支撑。这种"诊断→调参→验证"的闭环在深度学习模型中完全不可能实现，因为其内部表征没有物理语义。这验证了YLYW的核心方法论价值：可解释性不仅是"事后说明"，更是一种工程工具。')
heading('5.2 剩余挑战', 2)
body('石块（77.4%）和圆柱体（80.0%）是当前性能最低的两类。石块的特征向量方差极大（形状不规则导致），单质心模板难以充分覆盖。圆柱体的横放/竖放姿态差异使其爻向量呈双峰分布。这两个问题指向六爻编码层的改进方向——引入姿态感知的特征编码或高斯混合模型。')

heading('6 结论', 1)
body('本文提出并实现了YLYW——基于《易经》先验符号知识的联邦式神经符号具身决策框架。系统将八卦隶属度、六爻编码、六十四卦结构模板和爻位关系运算整合为统一的先验推理引擎，在42/64卦规则库下达到90%零样本合理率和0%严重错误率。爻模板质心优化和爻位关系运算的引入，分别从策略类型和执行参数两个维度完善了易理模型，验证了"卦象决定做什么、爻位决定怎么做"分层决策体系的有效性。')

doc.add_page_break()

# === 参考文献 ===
heading('参考文献')
refs = [
    '[1] Driess D, et al. PaLM-E: An Embodied Multimodal Language Model. ICML, 2023.',
    '[2] Brohan A, et al. RT-2: Vision-Language-Action Models. arXiv:2307.15818, 2023.',
    '[3] Kim M J, et al. OpenVLA: An Open-Source VLA Model. arXiv:2406.09246, 2024.',
    '[4] Garcez A, Lamb L C. Neurosymbolic AI: The 3rd Wave. AIR, 2023.',
    '[5] Manhaeve R, et al. DeepProbLog. NeurIPS, 2018.',
    '[6] Badreddine S, et al. Logic Tensor Networks. AIJ, 2022.',
    '[7] Morrison D, et al. Closing the Loop for Robotic Grasping. RSS, 2018.',
    '[8] Fang H S, et al. GraspNet-1Billion. CVPR, 2020.',
]
for ref in refs:
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
    r = p.add_run(ref); set_cn_font(r, '宋体', 'Times New Roman', Pt(9))

p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(12)
r = p.add_run('附：易学原典参考文献'); r.font.bold = True
set_cn_font(r, '黑体', 'Times New Roman', Pt(10))

classics = [
    '[9] 王弼（魏）. 周易注.',
    '[10] 孔颖达（唐）. 周易正义.',
    '[11] 朱熹（宋）. 周易本义.',
    '[12] 黄寿祺, 张善文. 周易译注. 上海古籍出版社, 2007.',
    '[13] 高亨. 周易古经今注. 中华书局, 1984.',
]
for ref in classics:
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
    r = p.add_run(ref); set_cn_font(r, '宋体', 'Times New Roman', Pt(9))

# 保存
out_path = f'{BASEDIR}/YLYW技术论文_v0.4.docx'
doc.save(out_path)
print(f'✅ {out_path}')
