#!/usr/bin/env python3
"""
L3 六十四卦步态模板库 (Hexagram Gait Rules for Motion Control)
64种卦象 → 步态策略映射
"""
import numpy as np

class HexagramGaitRules:
    """六十四卦步态规则库"""
    
    # 步态类型定义
    GAIT_TYPES = {
        'stand': {'name': '静止站立', 'speed': 0.0, 'step_height': 0.0, 'freq': 0.0},
        'crawl': {'name': '极慢爬行', 'speed': 0.15, 'step_height': 0.02, 'freq': 0.8},
        'slow_walk': {'name': '慢走', 'speed': 0.35, 'step_height': 0.04, 'freq': 1.2},
        'walk': {'name': '正常行走', 'speed': 0.60, 'step_height': 0.05, 'freq': 1.6},
        'fast_walk': {'name': '快速行走', 'speed': 0.90, 'step_height': 0.06, 'freq': 2.0},
        'trot': {'name': '小跑步态', 'speed': 1.30, 'step_height': 0.08, 'freq': 2.5},
        'run': {'name': '奔跑', 'speed': 2.0, 'step_height': 0.10, 'freq': 3.0},
        'caution_walk': {'name': '谨慎行走', 'speed': 0.25, 'step_height': 0.03, 'freq': 1.0},
        'recovery': {'name': '恢复步态', 'speed': 0.20, 'step_height': 0.02, 'freq': 0.5},
        'transition': {'name': '过渡缓冲', 'speed': 0.40, 'step_height': 0.04, 'freq': 1.0},
        'turn': {'name': '转向步态', 'speed': 0.30, 'step_height': 0.04, 'freq': 1.2},
        'climb': {'name': '爬坡步态', 'speed': 0.30, 'step_height': 0.07, 'freq': 1.0},
        'descend': {'name': '下坡步态', 'speed': 0.25, 'step_height': 0.03, 'freq': 0.8},
        'adaptive': {'name': '自适应步态', 'speed': 0.35, 'step_height': 0.05, 'freq': 1.0},
    }
    
    # 64卦 → 步态映射 (卦序:卦名: (上卦,下卦,步态类型, 力系数))
    # 力系数: [0,1] 归一化关节力矩输出强度
    HEXAGRAM_GAIT_RULES = {
        # === 上经 (01-30) ===
        1:  ('乾为天',   'qian','qian','run',          0.95),  # 健行不息
        2:  ('坤为地',   'kun', 'kun', 'crawl',        0.25),  # 柔顺包容
        3:  ('水雷屯',   'kan', 'zhen','transition',    0.60),  # 起步艰难
        4:  ('山水蒙',   'gen', 'kan', 'caution_walk',  0.45),  # 蒙昧待启
        5:  ('水天需',   'kan', 'qian','caution_walk',  0.40),  # 等待时机
        6:  ('天水讼',   'qian','kan', 'turn',          0.55),  # 争讼转向
        7:  ('地水师',   'kun', 'kan', 'recovery',      0.35),  # 师旅重整
        8:  ('水地比',   'kan', 'kun', 'slow_walk',     0.40),  # 亲比同行
        9:  ('风天小畜', 'xun', 'qian','caution_walk',  0.45),  # 小有蓄积
        10: ('天泽履',   'qian','dui', 'caution_walk',  0.30),  # 如履薄冰
        11: ('地天泰',   'kun', 'qian','walk',          0.65),  # 通泰
        12: ('天地否',   'qian','kun', 'stand',         0.30),  # 闭塞
        13: ('天火同人', 'qian','li',  'walk',          0.60),  # 与人同行
        14: ('火天大有', 'li',  'qian','fast_walk',     0.75),  # 大有收获
        15: ('地山谦',   'kun', 'gen', 'stand',         0.20),  # 谦逊静止
        16: ('雷地豫',   'zhen','kun', 'trot',          0.55),  # 愉悦而动
        17: ('泽雷随',   'dui', 'zhen','walk',          0.55),  # 随从行走
        18: ('山风蛊',   'gen', 'xun', 'adaptive',      0.50),  # 蛊惑调整
        19: ('地泽临',   'kun', 'dui', 'slow_walk',     0.45),  # 临近
        20: ('风地观',   'xun', 'kun', 'caution_walk',  0.35),  # 观察
        21: ('火雷噬嗑', 'li',  'zhen','fast_walk',     0.70),  # 咬合前进
        22: ('山火贲',   'gen', 'li',  'walk',          0.55),  # 文饰
        23: ('山地剥',   'gen', 'kun', 'descend',       0.35),  # 剥落下坡
        24: ('地雷复',   'kun', 'zhen','recovery',      0.45),  # 复归恢复
        25: ('天雷无妄', 'qian','zhen','fast_walk',     0.80),  # 无妄之动
        26: ('山天大畜', 'gen', 'qian','slow_walk',     0.60),  # 大畜待发
        27: ('山雷颐',   'gen', 'zhen','caution_walk',  0.40),  # 颐养谨慎
        28: ('泽风大过', 'dui', 'xun', 'recovery',      0.50),  # 大过调整
        29: ('坎为水',   'kan', 'kan', 'recovery',      0.40),  # 重险恢复
        30: ('离为火',   'li',  'li',  'walk',          0.60),  # 光明行走
        
        # === 下经 (31-64) ===
        31: ('泽山咸',   'dui', 'gen', 'slow_walk',     0.50),  # 感应
        32: ('雷风恒',   'zhen','xun', 'walk',          0.60),  # 恒久
        33: ('天山遁',   'qian','gen', 'fast_walk',     0.70),  # 退避急行
        34: ('雷天大壮', 'zhen','qian','run',           0.90),  # 大壮奔跑
        35: ('火地晋',   'li',  'kun', 'walk',          0.55),  # 晋升
        36: ('地火明夷', 'kun', 'li',  'caution_walk',  0.30),  # 明夷暗行
        37: ('风火家人', 'xun', 'li',  'walk',          0.55),  # 家人
        38: ('火泽睽',   'li',  'dui', 'turn',          0.50),  # 睽违转向
        39: ('水山蹇',   'kan', 'gen', 'climb',         0.45),  # 蹇难爬坡
        40: ('雷水解',   'zhen','kan', 'recovery',      0.60),  # 解散恢复
        41: ('山泽损',   'gen', 'dui', 'slow_walk',     0.40),  # 减损缓行
        42: ('风雷益',   'xun', 'zhen','fast_walk',     0.70),  # 增益提速
        43: ('泽天夬',   'dui', 'qian','walk',          0.65),  # 决断
        44: ('天风姤',   'qian','xun', 'adaptive',      0.55),  # 邂逅适应
        45: ('泽地萃',   'dui', 'kun', 'slow_walk',     0.45),  # 聚集
        46: ('地风升',   'kun', 'xun', 'climb',         0.50),  # 上升爬坡
        47: ('泽水困',   'dui', 'kan', 'recovery',      0.30),  # 困厄恢复
        48: ('水风井',   'kan', 'xun', 'slow_walk',     0.45),  # 井养
        49: ('泽火革',   'dui', 'li',  'turn',          0.55),  # 变革转向
        50: ('火风鼎',   'li',  'xun', 'walk',          0.60),  # 鼎立
        51: ('震为雷',   'zhen','zhen','run',           0.85),  # 震动奔跑
        52: ('艮为山',   'gen', 'gen', 'stand',         0.15),  # 静止如山
        53: ('风山渐',   'xun', 'gen', 'slow_walk',     0.45),  # 渐进
        54: ('雷泽归妹', 'zhen','dui', 'trot',          0.65),  # 归妹小跑
        55: ('雷火丰',   'zhen','li',  'fast_walk',     0.75),  # 丰盈快行
        56: ('火山旅',   'li',  'gen', 'walk',          0.50),  # 旅人
        57: ('巽为风',   'xun', 'xun', 'adaptive',      0.50),  # 随风适应
        58: ('兑为泽',   'dui', 'dui', 'walk',          0.55),  # 和悦行走
        59: ('风水涣',   'xun', 'kan', 'transition',    0.45),  # 涣散过渡
        60: ('水泽节',   'kan', 'dui', 'slow_walk',     0.45),  # 节制缓行
        61: ('风泽中孚', 'xun', 'dui', 'walk',          0.55),  # 中孚
        62: ('雷山小过', 'zhen','gen', 'caution_walk',  0.40),  # 小过谨慎
        63: ('水火既济', 'kan', 'li',  'transition',    0.50),  # 既济过渡
        64: ('火水未济', 'li',  'kan', 'recovery',      0.35),  # 未济待定
    }
    
    # 理想爻模板: 每个卦的6爻理想值 [初爻..上爻]
    # 基于卦辞语义 + 步态特征设计
    HEXAGRAM_YAO_TEMPLATES = {
        # 核心卦象模板（基于步态语义 + 爻位工程语义优化）
        1:  [0.90, 0.88, 0.92, 0.78, 0.60, 0.82],   # 乾 - 奔跑（高各维+中低扰动=动态）
        2:  [0.08, 0.15, 0.12, 0.25, 0.15, 0.35],   # 坤 - 全阴柔顺爬行
        3:  [0.50, 0.55, 0.42, 0.38, 0.50, 0.48],   # 屯 - 起步过渡
        10: [0.30, 0.38, 0.22, 0.18, 0.28, 0.28],   # 履 - 极度谨慎
        15: [0.95, 0.82, 0.68, 0.94, 0.98, 0.55],   # 谦 - 静止站立（高稳定性+极低扰动）
        24: [0.20, 0.22, 0.18, 0.14, 0.22, 0.38],   # 复 - 跌倒恢复
        29: [0.18, 0.22, 0.18, 0.14, 0.15, 0.35],   # 坎 - 重险恢复（极低全维度）
        34: [0.82, 0.85, 0.88, 0.72, 0.52, 0.78],   # 大壮 - 高速奔跑
        39: [0.68, 0.42, 0.52, 0.32, 0.48, 0.15],   # 蹇 - 爬坡（地形成瓶颈）
        51: [0.70, 0.72, 0.78, 0.52, 0.50, 0.72],   # 震 - 快速动态
        52: [0.95, 0.82, 0.72, 0.95, 0.98, 0.55],   # 艮 - 静止如山（最大化稳定性维度）
        54: [0.70, 0.75, 0.70, 0.62, 0.65, 0.70],   # 归妹 - 小跑
        63: [0.48, 0.52, 0.48, 0.42, 0.52, 0.50],   # 既济 - 过渡缓冲（避免catch-all偏中）
        64: [0.08, 0.12, 0.08, 0.08, 0.08, 0.12],   # 未济 - 极端（仅真正未定态激活）
    }
    
    def __init__(self):
        self._build_full_templates()
    
    def _build_full_templates(self):
        """为所有64卦生成爻模板（未定义的用默认值）"""
        default_template = [0.50, 0.50, 0.50, 0.50, 0.50, 0.50]
        for i in range(1, 65):
            if i not in self.HEXAGRAM_YAO_TEMPLATES:
                # 基于卦德生成默认模板
                rule = self.HEXAGRAM_GAIT_RULES[i]
                force = rule[4]
                gait_type = rule[3]
                # 根据步态类型推断模板
                if gait_type == 'stand':
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [0.92, 0.78, 0.65, 0.92, 0.96, 0.55]
                elif gait_type == 'run':
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [0.82, 0.82, 0.85, 0.70, 0.52, 0.78]
                elif gait_type == 'crawl':
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [0.45, 0.28, 0.32, 0.50, 0.38, 0.48]
                elif gait_type == 'recovery':
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [0.22, 0.25, 0.18, 0.15, 0.20, 0.38]
                elif gait_type == 'climb':
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [0.65, 0.42, 0.52, 0.32, 0.48, 0.18]
                elif gait_type == 'caution_walk':
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [0.42, 0.48, 0.38, 0.32, 0.42, 0.38]
                else:
                    self.HEXAGRAM_YAO_TEMPLATES[i] = [
                        0.48 + force * 0.35, 
                        0.48 + force * 0.30,
                        0.48 + force * 0.30,
                        0.48 + force * 0.30,
                        0.55 + force * 0.25,
                        0.55
                    ]
    
    def match_hexagram(self, yao_vector):
        """
        六爻向量 → 卦象匹配
        
        Args:
            yao_vector: 6维爻值 [0,1]
        
        Returns:
            hexagram_id: 卦序(1-64)
            hexagram_name: 卦名
            similarity: 余弦相似度
            gait_info: 步态信息 dict
            top3: Top-3匹配 [(卦序, 卦名, 相似度)]
        """
        y = np.array(yao_vector)
        
        similarities = {}
        for i in range(1, 65):
            t = np.array(self.HEXAGRAM_YAO_TEMPLATES[i])
            sim = np.dot(y, t) / (np.linalg.norm(y) * np.linalg.norm(t) + 1e-10)
            similarities[i] = sim
        
        # Top-3
        top3 = sorted(similarities.items(), key=lambda x: -x[1])[:3]
        best_id, best_sim = top3[0]
        
        rule = self.HEXAGRAM_GAIT_RULES[best_id]
        gait_type = rule[3]
        force_coef = rule[4]
        gait = self.GAIT_TYPES[gait_type].copy()
        gait['force_coefficient'] = force_coef
        
        top3_info = [(hid, self.HEXAGRAM_GAIT_RULES[hid][0], sim) 
                     for hid, sim in top3]
        
        return best_id, rule[0], best_sim, gait, top3_info
    
    def get_reasoning_chain(self, yao_vector, yin_yang, descriptions, hexagram_id, sim):
        """生成可解释推理链"""
        rule = self.HEXAGRAM_GAIT_RULES[hexagram_id]
        gait = self.GAIT_TYPES[rule[3]]
        
        yao_str = ''.join(yin_yang)
        
        chain = f"""
【YLYW 运动控制推理链】
▎L1 八卦基元 → (见隶属度输出)
▎L2 六爻分析
  {yao_str}
  {chr(10).join('  ' + d for d in descriptions)}
▎L3 卦象匹配
  卦象: {rule[0]} ({rule[1]}{rule[2]})
  匹配度: {sim:.3f}
  步态: {gait['name']}
  速度: {gait['speed']:.2f} m/s
  步高: {gait['step_height']:.2f} m
  力系数: {rule[4]:.2f}
  推理: {self._get_gait_reason(hexagram_id)}
"""
        return chain
    
    def _get_gait_reason(self, hexagram_id):
        reasons = {
            1: "乾卦全阳，健行不息→高速奔跑",
            2: "坤卦全阴，柔顺包容→极慢爬行",
            10: "履卦如履薄冰→极度谨慎行走",
            15: "谦卦谦逊守静→静止站立",
            24: "复卦一阳来复→跌倒恢复",
            29: "坎卦重险→抗扰恢复",
            34: "大壮卦刚健而动→全力奔跑",
            39: "蹇卦山上有水→爬坡步态",
            51: "震卦双雷交动→快速动态",
            52: "艮卦兼山静止→稳定站立",
            63: "既济卦事已成→过渡缓冲",
            64: "未济卦事未成→待定恢复",
        }
        return reasons.get(hexagram_id, f"卦象{hexagram_id}→步态决策")


if __name__ == '__main__':
    hgr = HexagramGaitRules()
    print(f"Loaded {len(hgr.HEXAGRAM_GAIT_RULES)} hexagram gait rules")
    print(f"Defined {len(hgr.HEXAGRAM_YAO_TEMPLATES)} yao templates")
    
    # Test matching
    from trigram_base_motion import TrigramMotionBase
    from yao_encoder_motion import MotionYaoEncoder
    
    tmb = TrigramMotionBase()
    encoder = MotionYaoEncoder()
    
    # Test 1: Stable standing
    state = [0.9, 0.85, 0.80, 0.90, 0.05, 0.80]
    yao, yy, desc = encoder.encode(dict(zip(
        ['posture','com_height','force_dist','zmp_margin','disturbance','terrain'], state)))
    hid, name, sim, gait, top3 = hgr.match_hexagram(yao)
    print(f"\n=== 稳定站立 ===")
    print(hgr.get_reasoning_chain(yao, yy, desc, hid, sim))
    
    # Test 2: Disturbed
    state2 = [0.2, 0.35, 0.30, 0.15, 0.80, 0.45]
    yao2, yy2, desc2 = encoder.encode(dict(zip(
        ['posture','com_height','force_dist','zmp_margin','disturbance','terrain'], state2)))
    hid2, name2, sim2, gait2, top3_2 = hgr.match_hexagram(yao2)
    print(f"\n=== 受扰动 ===")
    print(hgr.get_reasoning_chain(yao2, yy2, desc2, hid2, sim2))
