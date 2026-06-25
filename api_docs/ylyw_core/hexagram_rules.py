"""
六十四卦规则库模块 (L3: Hexagram Rules)

每个卦象关联一个预定义的抓取策略。
这些策略来自对《周易》卦辞、爻辞的工程化转译。

规则来源：
    - 卦名 → 策略类型（如"震"→动态抓取）
    - 卦辞 → 策略描述/注意事项
    - 爻位关系 → 力预设、接近角度

每个卦都有一组理想爻模板——这是"卦象"的数学表示。
通过余弦相似度匹配，判断当前六爻状态属于哪个卦。
"""

import numpy as np
from enum import Enum


class Hexagram(Enum):
    """六十四卦枚举"""
    # 上经（30卦）
    QIAN = 0       # 01. 乾为天 ☰☰
    KUN = 1        # 02. 坤为地 ☷☷
    ZHUN = 2       # 03. 水雷屯 ☵☳
    MENG = 3       # 04. 山水蒙 ☶☵
    XU = 4         # 05. 水天需 ☵☰
    SONG = 5       # 06. 天水讼 ☰☵
    SHI = 6        # 07. 地水师 ☷☵
    BI = 7         # 08. 水地比 ☵☷
    XIAOXU = 8     # 09. 风天小畜 ☴☰
    LU = 9         # 10. 天泽履 ☰☱
    TAI = 10       # 11. 地天泰 ☷☰
    PI = 11        # 12. 天地否 ☰☷
    TONGREN = 12   # 13. 天火同人 ☰☲
    DAYOU = 13     # 14. 火天大有 ☲☰
    QIAN_GUA = 14  # 15. 地山谦 ☷☶
    YU = 15        # 16. 雷地豫 ☳☷
    SUI = 16       # 17. 泽雷随 ☱☳
    GU = 17        # 18. 山风蛊 ☶☴
    LIN = 18       # 19. 地泽临 ☷☱
    GUAN = 19      # 20. 风地观 ☴☷
    SHIHE = 20     # 21. 火雷噬嗑 ☲☳
    BI_GUA = 21    # 22. 山火贲 ☶☲
    BO = 22        # 23. 山地剥 ☶☷
    FU = 23        # 24. 地雷复 ☷☳
    WUWANG = 24    # 25. 天雷无妄 ☰☳
    DACHU = 25     # 26. 山天大畜 ☶☰
    YI = 26        # 27. 山雷颐 ☶☳
    DAGUO = 27     # 28. 泽风大过 ☱☴
    KAN_GUA = 28   # 29. 坎为水 ☵☵
    LI_GUA = 29    # 30. 离为火 ☲☲
    # 下经（34卦）
    XIAN = 30      # 31. 泽山咸 ☱☶
    HENG = 31      # 32. 雷风恒 ☳☴
    DUN = 32       # 33. 天山遁 ☰☶
    DAZHUANG = 33  # 34. 雷天大壮 ☳☰
    JIN = 34       # 35. 火地晋 ☲☷
    MINGYI = 35    # 36. 地火明夷 ☷☲
    JIAREN = 36    # 37. 风火家人 ☴☲
    KUI = 37       # 38. 火泽睽 ☲☱
    JIAN = 38      # 39. 水山蹇 ☵☶
    XIE = 39       # 40. 雷水解 ☳☵
    SUN = 40       # 41. 山泽损 ☶☱
    YI_GUA = 41    # 42. 风雷益 ☴☳
    GUAI = 42      # 43. 泽天夬 ☱☰
    GOU = 43       # 44. 天风姤 ☰☴
    CUI = 44       # 45. 泽地萃 ☱☷
    SHENG = 45     # 46. 地风升 ☷☴
    KUN_GUA = 46   # 47. 泽水困 ☱☵
    JING = 47      # 48. 水风井 ☵☴
    GE = 48        # 49. 泽火革 ☱☲
    DING = 49      # 50. 火风鼎 ☲☴
    ZHEN_GUA = 50  # 51. 震为雷 ☳☳
    GEN_GUA = 51   # 52. 艮为山 ☶☶
    JIAN_GUA = 52  # 53. 风山渐 ☴☶
    GUIMEI = 53    # 54. 雷泽归妹 ☳☱
    FENG = 54      # 55. 雷火丰 ☳☲
    LU_GUA = 55    # 56. 火山旅 ☲☶
    XUN_GUA = 56   # 57. 巽为风 ☴☴
    DUI_GUA = 57   # 58. 兑为泽 ☱☱
    HUAN = 58      # 59. 风水涣 ☴☵
    JIE = 59       # 60. 水泽节 ☵☱
    ZHONGFU = 60   # 61. 风泽中孚 ☴☱
    XIAOGUO = 61   # 62. 雷山小过 ☳☶
    JIJI = 62      # 63. 水火既济 ☵☲
    WEIJI = 63     # 64. 火水未济 ☲☵


class HexagramRuleBase:
    """
    六十四卦规则库：硬编码的抓取策略

    这些策略来自对《周易》卦辞爻辞的工程转译。
    策略字段：
        - type: 抓取类型（power/precision/dynamic/stable/cautious等）
        - force: 力预设 [0, 1]
        - approach_angle: 接近角度（度）
        - speed: 接近速度（slow/medium/fast）
        - cautions: 注意事项列表

    设计原则：
        卦名 → 策略语义
        卦辞 → 核心原则
        爻位关系（乘承比应） → 力/角/速参数
    """

    def __init__(self):
        self.rules = self._build_rule_base()

        # 默认规则（当匹配不到具体卦时兜底）
        self.default_rule = {
            'name': '未定义卦象',
            'description': '使用默认抓取策略（中庸之道）',
            'upper_lower': ('?', '?'),
            'grasp_strategy': {
                'type': 'standard_grasp',
                'force': 0.5,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['无特殊注意事项', '监控抓取过程']
            },
            'suitable_for': ['常规物体'],
            'avoid': []
        }

    def _build_rule_base(self):
        """构建64卦规则库"""
        rules = {}

        # ========== 上经 ==========

        # 01. 乾为天 ☰☰ —— 刚健中正，强力抓取
        rules[Hexagram.QIAN] = {
            'name': '乾为天',
            'upper_lower': ('☰', '☰'),
            'description': '健行不息，刚健中正，自强不息',
            'grasp_strategy': {
                'type': 'power_grasp',
                'force': 0.85,
                'approach_angle': 0,
                'speed': 'fast',
                'cautions': ['确保抓取稳定', '避免冲击力过大', '关注力矩平衡']
            },
            'suitable_for': ['坚硬物体', '重物', '稳定形态物体'],
            'avoid': ['易碎品', '柔性物体', '不规则表面']
        }

        # 02. 坤为地 ☷☷ —— 柔顺包容，精确轻抓
        rules[Hexagram.KUN] = {
            'name': '坤为地',
            'upper_lower': ('☷', '☷'),
            'description': '柔顺包容，厚德载物，顺势而为',
            'grasp_strategy': {
                'type': 'precision_grasp',
                'force': 0.25,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['轻柔接触', '避免变形', '注意物体移位']
            },
            'suitable_for': ['柔性物体', '易碎品', '不规则物体', '轻薄物体'],
            'avoid': ['重物', '需要大力固定的物体']
        }

        # 03. 水雷屯 ☵☳ —— 初生艰难，谨慎抓取
        rules[Hexagram.ZHUN] = {
            'name': '水雷屯',
            'upper_lower': ('☵', '☳'),
            'description': '万物始生，艰难险阻，需耐心盘桓',
            'grasp_strategy': {
                'type': 'cautious_grasp',
                'force': 0.45,
                'approach_angle': 10,
                'speed': 'slow',
                'cautions': ['多次试探接触', '确认稳定后再提升', '预备备用方案']
            },
            'suitable_for': ['初次抓取的不确定物体', '形状复杂的物体'],
            'avoid': ['需要快速抓取的场景']
        }

        # 04. 山水蒙 ☶☵ —— 蒙昧待启，学习式抓取
        rules[Hexagram.MENG] = {
            'name': '山水蒙',
            'upper_lower': ('☶', '☵'),
            'description': '蒙昧初开，童蒙求我，需循序渐进',
            'grasp_strategy': {
                'type': 'adaptive_grasp',
                'force': 0.50,
                'approach_angle': 5,
                'speed': 'slow',
                'cautions': ['根据反馈调整力', '从弱到强逐步增加', '记录抓取结果供学习']
            },
            'suitable_for': ['未知物体', '探索性抓取', '学习阶段'],
            'avoid': ['确定性强的场景（此时应用确定规则）']
        }

        # 05. 水天需 ☵☰ —— 等待时机，条件性抓取
        rules[Hexagram.XU] = {
            'name': '水天需',
            'upper_lower': ('☵', '☰'),
            'description': '需待时机，饮食宴乐，静候其变',
            'grasp_strategy': {
                'type': 'conditional_grasp',
                'force': 0.55,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['等待最佳抓取窗口', '检查环境是否安全', '时机不对则放弃']
            },
            'suitable_for': ['动态环境中的物体', '需要等待时机的场景'],
            'avoid': ['必须立即抓取的紧急任务']
        }

        # 06. 天水讼 ☰☵ —— 争讼冲突，避免硬碰
        rules[Hexagram.SONG] = {
            'name': '天水讼',
            'upper_lower': ('☰', '☵'),
            'description': '争讼不宁，有孚窒惕，中吉终凶',
            'grasp_strategy': {
                'type': 'non_conflict_grasp',
                'force': 0.35,
                'approach_angle': 20,
                'speed': 'medium',
                'cautions': ['避免与其他物体碰撞', '从开阔侧接近', '不可强行抓取']
            },
            'suitable_for': ['周围有障碍物的物体', '需要避让的场景'],
            'avoid': ['无障碍时的简单场景']
        }

        # 07. 地水师 ☷☵ —— 师出有名，有序抓取
        rules[Hexagram.SHI] = {
            'name': '地水师',
            'upper_lower': ('☷', '☵'),
            'description': '师出以律，行险而顺，秩序井然',
            'grasp_strategy': {
                'type': 'sequential_grasp',
                'force': 0.55,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['按顺序逐一抓取', '保持间距', '注意整体布局']
            },
            'suitable_for': ['多物体顺序抓取', '流水线任务'],
            'avoid': ['单物体快速抓取']
        }

        # 08. 水地比 ☵☷ —— 亲比依附，贴近式抓取
        rules[Hexagram.BI] = {
            'name': '水地比',
            'upper_lower': ('☵', '☷'),
            'description': '亲比辅佐，吉无不利，贴近而行',
            'grasp_strategy': {
                'type': 'close_proximity_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['从最近面接近', '利用支撑面', '保持贴合']
            },
            'suitable_for': ['紧贴平面的物体', '有支撑面的物体'],
            'avoid': ['悬空物体']
        }

        # 09. 风天小畜 ☴☰ —— 小有积蓄，渐进加力
        rules[Hexagram.XIAOXU] = {
            'name': '风天小畜',
            'upper_lower': ('☴', '☰'),
            'description': '小畜寡也，密云不雨，逐渐积蓄力量',
            'grasp_strategy': {
                'type': 'progressive_grasp',
                'force': 0.45,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['从弱到强逐步加力', '监控力反馈', '达到稳定即停止加力']
            },
            'suitable_for': ['摩擦力不确定的物体', '需要试探性施力的场景'],
            'avoid': []
        }

        # 10. 天泽履 ☰☱ —— 履虎尾般小心
        rules[Hexagram.LU] = {
            'name': '天泽履',
            'upper_lower': ('☰', '☱'),
            'description': '履虎尾不咥人，小心翼翼，如履薄冰',
            'grasp_strategy': {
                'type': 'cautious_grasp',
                'force': 0.35,
                'approach_angle': 5,
                'speed': 'slow',
                'cautions': ['极慢接近', '传感器全程监控', '发现异常立即撤回']
            },
            'suitable_for': ['高风险物体', '精密仪器', '贵重物品'],
            'avoid': ['常规任务']
        }

        # 11. 地天泰 ☷☰ —— 通顺和谐，标准抓取
        rules[Hexagram.TAI] = {
            'name': '地天泰',
            'upper_lower': ('☷', '☰'),
            'description': '天地交泰，小往大来，通顺和谐',
            'grasp_strategy': {
                'type': 'standard_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['正常操作即可', '按标准流程执行']
            },
            'suitable_for': ['大部分常规物体', '标准抓取任务'],
            'avoid': []
        }

        # 12. 天地否 ☰☷ —— 闭塞不通，避免强抓
        rules[Hexagram.PI] = {
            'name': '天地否',
            'upper_lower': ('☰', '☷'),
            'description': '天地不交，否之匪人，闭塞不通',
            'grasp_strategy': {
                'type': 'avoid_or_retry',
                'force': 0.30,
                'approach_angle': 30,
                'speed': 'slow',
                'cautions': ['判断是否可抓', '不可抓则放弃', '尝试换个角度']
            },
            'suitable_for': ['抓取困难的场景'],
            'avoid': ['强行抓取']
        }

        # 63. 水火既济 ☵☲ —— 事已成，初吉终乱
        rules[Hexagram.JIJI] = {
            'name': '水火既济',
            'upper_lower': ('☵', '☲'),
            'description': '事已成，初吉终乱，亨小利贞',
            'grasp_strategy': {
                'type': 'balanced_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['初期顺利，后期需谨慎', '全程监控', '不要因为初段顺利而掉以轻心']
            },
            'suitable_for': ['常规物体', '日常抓取任务'],
            'avoid': ['极端情况']
        }

        # 64. 火水未济 ☲☵ —— 事未成，谨慎观望
        rules[Hexagram.WEIJI] = {
            'name': '火水未济',
            'upper_lower': ('☲', '☵'),
            'description': '事未成也，小狐汔济，濡其尾',
            'grasp_strategy': {
                'type': 'abort_or_retry',
                'force': 0.40,
                'approach_angle': 10,
                'speed': 'slow',
                'cautions': ['确认条件是否满足', '不满足则暂缓', '调整后重试']
            },
            'suitable_for': ['条件不确定的场景'],
            'avoid': ['确定性强的场景']
        }

        # ========== 核心八卦的重卦（补充完整） ==========

        # 51. 震为雷 ☳☳ —— 震动不安，动态抓取
        rules[Hexagram.ZHEN_GUA] = {
            'name': '震为雷',
            'upper_lower': ('☳', '☳'),
            'description': '震动不安，恐惧修省，动态万变',
            'grasp_strategy': {
                'type': 'dynamic_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'fast',
                'cautions': ['快速响应', '跟踪物体运动', '防止物体滚动或滑落']
            },
            'suitable_for': ['球体', '圆柱体', '易滚动物体', '移动中的物体'],
            'avoid': ['静态放置的易碎物']
        }

        # 52. 艮为山 ☶☶ —— 静止不动，稳定抓取
        rules[Hexagram.GEN_GUA] = {
            'name': '艮为山',
            'upper_lower': ('☶', '☶'),
            'description': '静止如山，思不出位，稳如磐石',
            'grasp_strategy': {
                'type': 'stable_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['先固定物体', '确认稳定后再提升']
            },
            'suitable_for': ['静止放置的物体', '底部稳固的物体'],
            'avoid': ['需要快速抓取的场景', '移动物体']
        }

        # 57. 巽为风 ☴☴ —— 入微渗透，柔顺应变
        rules[Hexagram.XUN_GUA] = {
            'name': '巽为风',
            'upper_lower': ('☴', '☴'),
            'description': '随风而动，柔顺谦逊，无所不入',
            'grasp_strategy': {
                'type': 'compliant_grasp',
                'force': 0.35,
                'approach_angle': 15,
                'speed': 'medium',
                'cautions': ['顺应物体姿态', '不强行改变物体朝向', '利用柔性接触']
            },
            'suitable_for': ['不规则物体', '需要适应物体姿态的场景'],
            'avoid': ['需要精确定位的场景']
        }

        # 58. 兑为泽 ☱☱ —— 和悦交流，柔性抓取
        rules[Hexagram.DUI_GUA] = {
            'name': '兑为泽',
            'upper_lower': ('☱', '☱'),
            'description': '和悦相待，朋友讲习，以柔克刚',
            'grasp_strategy': {
                'type': 'soft_grasp',
                'force': 0.30,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['以最小力抓取', '保持柔性接触', '避免夹痕']
            },
            'suitable_for': ['软质物体', '食品', '需要保持外观的物体'],
            'avoid': ['重物', '粗糙表面']
        }

        # 29. 坎为水 ☵☵ —— 险陷深坑，谨慎绕行
        rules[Hexagram.KAN_GUA] = {
            'name': '坎为水',
            'upper_lower': ('☵', '☵'),
            'description': '重险陷也，水流而不盈，行险而不失其信',
            'grasp_strategy': {
                'type': 'cautious_grasp',
                'force': 0.50,
                'approach_angle': 20,
                'speed': 'slow',
                'cautions': ['避开凹陷和孔洞', '防止滑落', '预备备用方案']
            },
            'suitable_for': ['带孔物体', '有凹陷的物体', '不规则表面'],
            'avoid': ['精密仪器', '易碎物']
        }

        # 30. 离为火 ☲☲ —— 光明附丽，吸附抓取
        rules[Hexagram.LI_GUA] = {
            'name': '离为火',
            'upper_lower': ('☲', '☲'),
            'description': '光明附丽，日月丽乎天，百谷草木丽乎土',
            'grasp_strategy': {
                'type': 'adhesion_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['检查表面是否适合吸附', '保持接触面积', '避免空气泄漏（如用吸盘）']
            },
            'suitable_for': ['光滑表面', '平面物体', '轻质物体'],
            'avoid': ['粗糙表面', '多孔物体', '重物']
        }

        # ========== A档核心卦象补充（22卦） ==========

        # 15. 雷地豫 ☳☷ —— 预判而动，提前拦截
        rules[Hexagram.YU] = {
            'name': '雷地豫',
            'upper_lower': ('☳', '☷'),
            'description': '雷出地奋，豫。先王以作乐崇德，预判而动',
            'grasp_strategy': {
                'type': 'predictive_grasp',
                'force': 0.45,
                'approach_angle': 5,
                'speed': 'fast',
                'cautions': ['预判物体运动轨迹', '提前到达拦截点', '动态调整抓取时机']
            },
            'suitable_for': ['移动中的物体', '动态环境', '传送带上的物体'],
            'avoid': ['静止场景（用静态策略更省力）']
        }

        # 17. 泽雷随 ☱☳ —— 跟随运动，顺势而为
        rules[Hexagram.SUI] = {
            'name': '泽雷随',
            'upper_lower': ('☱', '☳'),
            'description': '泽中有雷，随。君子以向晦入宴息，随时而动',
            'grasp_strategy': {
                'type': 'following_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['跟踪物体运动方向', '匹配物体速度', '顺势抓取不逆势']
            },
            'suitable_for': ['滚动的球体', '滑动的圆柱体', '摆动的物体'],
            'avoid': ['固定不动的物体']
        }

        # 18. 山风蛊 ☶☴ —— 治理弊坏，修正重试
        rules[Hexagram.GU] = {
            'name': '山风蛊',
            'upper_lower': ('☶', '☴'),
            'description': '山下有风，蛊。君子以振民育德，治弊修复',
            'grasp_strategy': {
                'type': 'corrective_grasp',
                'force': 0.45,
                'approach_angle': 10,
                'speed': 'slow',
                'cautions': ['分析上次失败原因', '调整接近角度', '更换抓取点重试']
            },
            'suitable_for': ['首次抓取失败后重试', '需要调整策略的场景'],
            'avoid': ['一次性高成功率场景']
        }

        # 19. 地泽临 ☷☱ —— 自上而下，俯视接近
        rules[Hexagram.LIN] = {
            'name': '地泽临',
            'upper_lower': ('☷', '☱'),
            'description': '泽上有地，临。君子以教思无穷，自上临下',
            'grasp_strategy': {
                'type': 'top_down_grasp',
                'force': 0.45,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['从正上方垂直接近', '确保无顶部遮挡', '利用重力辅助定位']
            },
            'suitable_for': ['桌面上的物体', '从上方抓取的场景', '顶部无障碍的物体'],
            'avoid': ['侧面有障碍时优先侧向接近']
        }

        # 20. 风地观 ☴☷ —— 观察评估，信息优先
        rules[Hexagram.GUAN] = {
            'name': '风地观',
            'upper_lower': ('☴', '☷'),
            'description': '风行地上，观。先王以省方观民设教，察而后动',
            'grasp_strategy': {
                'type': 'observational_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['先充分观察物体特征', '评估所有可能抓取点', '信息不足时暂不动手']
            },
            'suitable_for': ['信息不充分的场景', '复杂形状物体', '需要多点评估的物体'],
            'avoid': ['紧急抓取任务']
        }

        # 21. 火雷噬嗑 ☲☳ —— 咬合啮合，钳式抓取
        rules[Hexagram.SHIHE] = {
            'name': '火雷噬嗑',
            'upper_lower': ('☲', '☳'),
            'description': '雷电噬嗑，先王以明罚敕法，啮而合之',
            'grasp_strategy': {
                'type': 'interlocking_grasp',
                'force': 0.60,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['找准啮合点', '确保咬合紧密', '避免单点受力滑脱']
            },
            'suitable_for': ['需要啮合的物体', '有凸起/把手的物体', '可从两侧夹持的物体'],
            'avoid': ['平滑无缝的物体']
        }

        # 23. 山地剥 ☶☷ —— 层层剥离，逐层操作
        rules[Hexagram.BO] = {
            'name': '山地剥',
            'upper_lower': ('☶', '☷'),
            'description': '山附于地，剥。上以厚下安宅，层层剥离',
            'grasp_strategy': {
                'type': 'peeling_grasp',
                'force': 0.35,
                'approach_angle': 15,
                'speed': 'slow',
                'cautions': ['逐层分离', '从边缘开始', '每次只剥离一层']
            },
            'suitable_for': ['堆叠物体', '需要逐层分离的场景', '片状物体'],
            'avoid': ['单体抓取']
        }

        # 24. 地雷复 ☷☳ —— 反复试探，由弱到强
        rules[Hexagram.FU] = {
            'name': '地雷复',
            'upper_lower': ('☷', '☳'),
            'description': '雷在地中，复。先王以至日闭关，反复其道',
            'grasp_strategy': {
                'type': 'iterative_grasp',
                'force': 0.35,
                'approach_angle': 5,
                'speed': 'slow',
                'cautions': ['从最小力开始逐步增加', '每次试探后评估稳定性', '找到最小可行力即停止']
            },
            'suitable_for': ['脆弱物体', '摩擦力不确定的物体', '精密操作'],
            'avoid': ['需要快速完成的场景']
        }

        # 25. 天雷无妄 ☰☳ —— 真实不虚，直截了当
        rules[Hexagram.WUWANG] = {
            'name': '天雷无妄',
            'upper_lower': ('☰', '☳'),
            'description': '天下雷行，物与无妄。先王以茂对时育万物',
            'grasp_strategy': {
                'type': 'direct_grasp',
                'force': 0.55,
                'approach_angle': 0,
                'speed': 'fast',
                'cautions': ['直接果断抓取', '不绕弯不犹豫', '确认条件满足就执行']
            },
            'suitable_for': ['常规形状物体', '抓取条件良好的场景', '高效率要求'],
            'avoid': ['复杂或不确定场景']
        }

        # 26. 山天大畜 ☶☰ —— 积蓄力量，蓄力而发
        rules[Hexagram.DACHU] = {
            'name': '山天大畜',
            'upper_lower': ('☶', '☰'),
            'description': '天在山中，大畜。君子以多识前言往行，以畜其德',
            'grasp_strategy': {
                'type': 'power_accumulating_grasp',
                'force': 0.75,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['先蓄力再施加', '缓慢增加抓取力', '达到稳定后保持']
            },
            'suitable_for': ['重物', '需要大力保持的物体', '高密度物体'],
            'avoid': ['易碎品', '轻质物体']
        }

        # 28. 泽风大过 ☱☴ —— 大为过甚，强力突破
        rules[Hexagram.DAGUO] = {
            'name': '泽风大过',
            'upper_lower': ('☱', '☴'),
            'description': '泽灭木，大过。君子以独立不惧，遁世无闷',
            'grasp_strategy': {
                'type': 'forceful_grasp',
                'force': 0.80,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['确认物体能承受大力', '一次性施力到位', '防止过冲损坏']
            },
            'suitable_for': ['极重物体', '需要极大抓取力的场景', '坚固物体'],
            'avoid': ['易碎品', '精密仪器', '柔性物体']
        }

        # 31. 泽山咸 ☱☶ —— 感知感应，触觉反馈
        rules[Hexagram.XIAN] = {
            'name': '泽山咸',
            'upper_lower': ('☱', '☶'),
            'description': '山上有泽，咸。君子以虚受人，感而遂通',
            'grasp_strategy': {
                'type': 'tactile_feedback_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['依赖触觉传感器反馈', '实时监控接触力', '根据滑脱信号调整力']
            },
            'suitable_for': ['需要触觉反馈的场景', '表面特性未知的物体', '精密力控任务'],
            'avoid': ['无触觉传感器的场景']
        }

        # 32. 雷风恒 ☳☴ —— 持久恒定，长期保持
        rules[Hexagram.HENG] = {
            'name': '雷风恒',
            'upper_lower': ('☳', '☴'),
            'description': '雷风恒，君子以立不易方，持之以恒',
            'grasp_strategy': {
                'type': 'endurance_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['保持恒定力输出', '定期检查抓取状态', '防止疲劳导致的力衰减']
            },
            'suitable_for': ['需要长时间保持的抓取', '搬运任务', '装配定位'],
            'avoid': ['短时操作']
        }

        # 33. 天山遁 ☰☶ —— 退避三舍，主动放弃
        rules[Hexagram.DUN] = {
            'name': '天山遁',
            'upper_lower': ('☰', '☶'),
            'description': '天下有山，遁。君子以远小人，不恶而严',
            'grasp_strategy': {
                'type': 'withdraw_grasp',
                'force': 0.20,
                'approach_angle': 45,
                'speed': 'slow',
                'cautions': ['评估抓取可行性', '不可抓则果断放弃', '记录不可抓原因供分析']
            },
            'suitable_for': ['抓取条件差的场景', '高风险物体', '超出能力范围的物体'],
            'avoid': []
        }

        # 34. 雷天大壮 ☳☰ —— 强壮有力，强力稳健
        rules[Hexagram.DAZHUANG] = {
            'name': '雷天大壮',
            'upper_lower': ('☳', '☰'),
            'description': '雷在天上，大壮。君子以非礼弗履，刚健有力',
            'grasp_strategy': {
                'type': 'robust_power_grasp',
                'force': 0.80,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['确保物体坚固', '用足力但不过力', '重视接触面摩擦力']
            },
            'suitable_for': ['重且坚固的物体', '金属零件', '工具类物体'],
            'avoid': ['易碎品', '柔性物体', '精密器件']
        }

        # 35. 火地晋 ☲☷ —— 渐进上升，逐步推进
        rules[Hexagram.JIN] = {
            'name': '火地晋',
            'upper_lower': ('☲', '☷'),
            'description': '明出地上，晋。君子以自昭明德，循序渐进',
            'grasp_strategy': {
                'type': 'progressive_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['逐步接近目标', '分段增加力', '每阶段检查状态']
            },
            'suitable_for': ['精密物体', '需要逐步施力的场景', '易移位物体'],
            'avoid': ['快速抓取场景']
        }

        # 36. 地火明夷 ☷☲ —— 光明受损，暗处操作
        rules[Hexagram.MINGYI] = {
            'name': '地火明夷',
            'upper_lower': ('☷', '☲'),
            'description': '明入地中，明夷。君子以莅众用晦而明',
            'grasp_strategy': {
                'type': 'low_visibility_grasp',
                'force': 0.45,
                'approach_angle': 10,
                'speed': 'slow',
                'cautions': ['依赖触觉而非视觉', '降低接近速度', '用小力试探确认位置']
            },
            'suitable_for': ['遮挡严重的物体', '光线不足的场景', '视觉传感器受限时'],
            'avoid': ['需要精确视觉定位的场景']
        }

        # 37. 风火家人 ☴☲ —— 协同合作，多指协调
        rules[Hexagram.JIAREN] = {
            'name': '风火家人',
            'upper_lower': ('☴', '☲'),
            'description': '风自火出，家人。君子以言有物而行有恒',
            'grasp_strategy': {
                'type': 'coordinated_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['多指协调用力', '保持力分布均匀', '各指按角色分工']
            },
            'suitable_for': ['需要多指协调的物体', '不规则形状', '需要多点接触的物体'],
            'avoid': ['简单二指即可抓取的物体']
        }

        # 38. 火泽睽 ☲☱ —— 乖离不合，异形适配
        rules[Hexagram.KUI] = {
            'name': '火泽睽',
            'upper_lower': ('☲', '☱'),
            'description': '上火下泽，睽。君子以同而异，求同存异',
            'grasp_strategy': {
                'type': 'adaptive_irregular_grasp',
                'force': 0.45,
                'approach_angle': 15,
                'speed': 'slow',
                'cautions': ['适应不规则形状', '根据局部几何调整指位', '容忍一定的不对称']
            },
            'suitable_for': ['不规则形状物体', '异形零件', '自然形态物体（石块等）'],
            'avoid': ['规则几何体']
        }

        # 39. 水山蹇 ☵☶ —— 艰难险阻，困难抓取
        rules[Hexagram.JIAN] = {
            'name': '水山蹇',
            'upper_lower': ('☵', '☶'),
            'description': '山上有水，蹇。君子以反身修德，知难而进',
            'grasp_strategy': {
                'type': 'difficult_grasp',
                'force': 0.50,
                'approach_angle': 20,
                'speed': 'slow',
                'cautions': ['识别困难来源', '调整策略应对', '必要时寻求辅助手段']
            },
            'suitable_for': ['高难度抓取场景', '被包围的物体', '复杂环境'],
            'avoid': ['简单场景（过度谨慎浪费资源）']
        }

        # 40. 雷水解 ☳☵ —— 解除困境，脱困取出
        rules[Hexagram.XIE] = {
            'name': '雷水解',
            'upper_lower': ('☳', '☵'),
            'description': '雷雨作，解。君子以赦过宥罪，解困脱厄',
            'grasp_strategy': {
                'type': 'extrication_grasp',
                'force': 0.50,
                'approach_angle': 10,
                'speed': 'medium',
                'cautions': ['先清除周围障碍', '从最松脱的方向取出', '避免卡住']
            },
            'suitable_for': ['堆叠中的物体', '被卡住的物体', '需要从集合中取出的物体'],
            'avoid': ['孤立物体']
        }

        # 41. 山泽损 ☶☱ —— 损下益上，轻柔减力
        rules[Hexagram.SUN] = {
            'name': '山泽损',
            'upper_lower': ('☶', '☱'),
            'description': '山下有泽，损。君子以惩忿窒欲，减损克制',
            'grasp_strategy': {
                'type': 'reduced_force_grasp',
                'force': 0.25,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['以最小力维持抓取', '持续监控是否滑脱', '力越小越好']
            },
            'suitable_for': ['易碎品', '软质物体', '表面易损的物体'],
            'avoid': ['重物', '需要大力的场景']
        }


        # ========== B档衍生卦象补充（22卦，策略复用A档） ==========

        # 13. 天火同人 ☰☲ —— 协同合作
        rules[Hexagram.TONGREN] = {
            'name': '天火同人',
            'upper_lower': ('☰', '☲'),
            'description': '类族辨物，与人协同，通天下之志',
            'grasp_strategy': {
                'type': 'coordinated_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['多指协调用力', '保持力分布均匀']
            },
            'suitable_for': ['需要多指协同的物体', '不规则形状'],
            'avoid': ['简单二指即可']
        }

        # 14. 火天大有 ☲☰ —— 大面积吸附
        rules[Hexagram.DAYOU] = {
            'name': '火天大有',
            'upper_lower': ('☲', '☰'),
            'description': '其德刚健而文明，大获所有，顺天休命',
            'grasp_strategy': {
                'type': 'adhesion_grasp',
                'force': 0.45,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['利用大面积接触', '确保吸附稳定']
            },
            'suitable_for': ['大面积光滑物体', '平面物体'],
            'avoid': ['粗糙表面', '多孔物体']
        }

        # 15. 地山谦 ☷☶ —— 谦逊轻柔
        rules[Hexagram.QIAN_GUA] = {
            'name': '地山谦',
            'upper_lower': ('☷', '☶'),
            'description': '谦谦君子，卑以自牧，天道亏盈而益谦',
            'grasp_strategy': {
                'type': 'reduced_force_grasp',
                'force': 0.25,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['以最小力维持', '持续监控滑脱']
            },
            'suitable_for': ['易碎品', '精密物体', '贵重物品'],
            'avoid': ['重物']
        }

        # 22. 山火贲 ☶☲ —— 外观观察
        rules[Hexagram.BI_GUA] = {
            'name': '山火贲',
            'upper_lower': ('☶', '☲'),
            'description': '观乎人文，以化成天下，饰也',
            'grasp_strategy': {
                'type': 'observational_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['充分观察外观特征', '选择最佳抓取面']
            },
            'suitable_for': ['外观重要的物体', '装饰品', '需要评估表面的物体'],
            'avoid': ['紧急任务']
        }

        # 27. 山雷颐 ☶☳ —— 养正保持
        rules[Hexagram.YI] = {
            'name': '山雷颐',
            'upper_lower': ('☶', '☳'),
            'description': '养正也，自求口实，观颐养正',
            'grasp_strategy': {
                'type': 'endurance_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['保持恒定力输出', '定期检查状态']
            },
            'suitable_for': ['需长时间保持的抓取', '搬运任务'],
            'avoid': ['短时操作']
        }

        # 42. 风雷益 ☴☳ —— 增益渐进
        rules[Hexagram.YI_GUA] = {
            'name': '风雷益',
            'upper_lower': ('☴', '☳'),
            'description': '损上益下，其道大光，天施地生',
            'grasp_strategy': {
                'type': 'progressive_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['从轻到重逐步加力', '每阶段评估']
            },
            'suitable_for': ['精密物体', '需逐步施力的场景'],
            'avoid': ['快速场景']
        }

        # 43. 泽天夬 ☱☰ —— 果断执行
        rules[Hexagram.GUAI] = {
            'name': '泽天夬',
            'upper_lower': ('☱', '☰'),
            'description': '决也，刚决柔也，健而说',
            'grasp_strategy': {
                'type': 'direct_grasp',
                'force': 0.60,
                'approach_angle': 0,
                'speed': 'fast',
                'cautions': ['确认条件后果断执行', '不犹豫不绕弯']
            },
            'suitable_for': ['条件明确的场景', '高效率要求'],
            'avoid': ['不确定场景']
        }

        # 44. 天风姤 ☰☴ —— 初次遭遇
        rules[Hexagram.GOU] = {
            'name': '天风姤',
            'upper_lower': ('☰', '☴'),
            'description': '遇也，天地相遇品物咸章，刚遇中正',
            'grasp_strategy': {
                'type': 'adaptive_grasp',
                'force': 0.50,
                'approach_angle': 5,
                'speed': 'slow',
                'cautions': ['首次接触需试探', '根据反馈调整']
            },
            'suitable_for': ['首次遭遇的物体', '未知物体'],
            'avoid': ['已知物体（用确定策略）']
        }

        # 45. 泽地萃 ☱☷ —— 聚集有序
        rules[Hexagram.CUI] = {
            'name': '泽地萃',
            'upper_lower': ('☱', '☷'),
            'description': '聚也，观其所聚而天地万物之情可见',
            'grasp_strategy': {
                'type': 'sequential_grasp',
                'force': 0.55,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['按顺序逐一抓取', '保持间距']
            },
            'suitable_for': ['批量物体', '流水线抓取'],
            'avoid': ['单物体']
        }

        # 46. 地风升 ☷☴ —— 自下而上
        rules[Hexagram.SHENG] = {
            'name': '地风升',
            'upper_lower': ('☷', '☴'),
            'description': '柔以时升，积小以高大，南征吉',
            'grasp_strategy': {
                'type': 'top_down_grasp',
                'force': 0.45,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['从正上方向下接近', '利用重力辅助']
            },
            'suitable_for': ['桌面物体', '从上方抓取'],
            'avoid': ['侧向优先的场景']
        }

        # 47. 泽水困 ☱☵ —— 困境难取
        rules[Hexagram.KUN_GUA] = {
            'name': '泽水困',
            'upper_lower': ('☱', '☵'),
            'description': '困也，险以说，困而不失其所',
            'grasp_strategy': {
                'type': 'difficult_grasp',
                'force': 0.50,
                'approach_angle': 20,
                'speed': 'slow',
                'cautions': ['识别困难来源', '调整策略应对']
            },
            'suitable_for': ['高难度场景', '被包围/卡住的物体'],
            'avoid': ['简单场景']
        }

        # 48. 水风井 ☵☴ —— 稳定重复
        rules[Hexagram.JING] = {
            'name': '水风井',
            'upper_lower': ('☵', '☴'),
            'description': '改邑不改井，无丧无得，往来井井',
            'grasp_strategy': {
                'type': 'stable_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['固定位置重复操作', '保持一致性']
            },
            'suitable_for': ['固定位置物体', '重复操作'],
            'avoid': ['移动物体']
        }

        # 49. 泽火革 ☱☲ —— 变革重试
        rules[Hexagram.GE] = {
            'name': '泽火革',
            'upper_lower': ('☱', '☲'),
            'description': '天地革而四时成，治历明时，顺天应人',
            'grasp_strategy': {
                'type': 'corrective_grasp',
                'force': 0.45,
                'approach_angle': 10,
                'speed': 'slow',
                'cautions': ['分析失败原因', '调整策略后重试']
            },
            'suitable_for': ['失败后调整', '需要改变策略的场景'],
            'avoid': ['首次尝试（用直接策略）']
        }

        # 50. 火风鼎 ☲☴ —— 平衡稳定
        rules[Hexagram.DING] = {
            'name': '火风鼎',
            'upper_lower': ('☲', '☴'),
            'description': '象也，以木巽火亨饪也，君子以正位凝命',
            'grasp_strategy': {
                'type': 'balanced_grasp',
                'force': 0.50,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['保持力平衡', '全程监控']
            },
            'suitable_for': ['常规物体', '多用途场景'],
            'avoid': ['极端情况']
        }

        # 53. 风山渐 ☴☶ —— 缓慢渐进
        rules[Hexagram.JIAN_GUA] = {
            'name': '风山渐',
            'upper_lower': ('☴', '☶'),
            'description': '进也，女归吉也，进得位往有功也',
            'grasp_strategy': {
                'type': 'progressive_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['以极慢速度渐进', '每步检查状态']
            },
            'suitable_for': ['需极慢渐进的操作', '精密装配'],
            'avoid': ['快速场景']
        }

        # 54. 雷泽归妹 ☳☱ —— 顺应归附
        rules[Hexagram.GUIMEI] = {
            'name': '雷泽归妹',
            'upper_lower': ('☳', '☱'),
            'description': '归也，天地之大义也，永终知敝',
            'grasp_strategy': {
                'type': 'compliant_grasp',
                'force': 0.35,
                'approach_angle': 15,
                'speed': 'slow',
                'cautions': ['顺应物体自然姿态', '不强行改变朝向']
            },
            'suitable_for': ['需顺应姿态的物体', '不规则摆放'],
            'avoid': ['需精确定位的场景']
        }

        # 55. 雷火丰 ☳☲ —— 丰盛强力
        rules[Hexagram.FENG] = {
            'name': '雷火丰',
            'upper_lower': ('☳', '☲'),
            'description': '大也，明以动故丰，日中则昃',
            'grasp_strategy': {
                'type': 'robust_power_grasp',
                'force': 0.75,
                'approach_angle': 0,
                'speed': 'medium',
                'cautions': ['确保物体坚固', '用足力但不过力']
            },
            'suitable_for': ['重且坚固的物体', '金属零件'],
            'avoid': ['易碎品', '精密器件']
        }

        # 56. 火山旅 ☲☶ —— 旅居适应
        rules[Hexagram.LU_GUA] = {
            'name': '火山旅',
            'upper_lower': ('☲', '☶'),
            'description': '旅也，柔得中乎外而顺乎刚，止而丽乎明',
            'grasp_strategy': {
                'type': 'conditional_grasp',
                'force': 0.55,
                'approach_angle': 5,
                'speed': 'medium',
                'cautions': ['适应移动环境', '动态调整策略']
            },
            'suitable_for': ['动态环境', '移动中的物体'],
            'avoid': ['静态简单场景']
        }

        # 59. 风水涣 ☴☵ —— 散乱观望
        rules[Hexagram.HUAN] = {
            'name': '风水涣',
            'upper_lower': ('☴', '☵'),
            'description': '涣也，风行水上，涣奔其机',
            'grasp_strategy': {
                'type': 'abort_or_retry',
                'force': 0.40,
                'approach_angle': 10,
                'speed': 'slow',
                'cautions': ['确认条件是否满足', '不满足则暂缓']
            },
            'suitable_for': ['散乱不确定场景', '条件不充分的'],
            'avoid': ['确定性强的场景']
        }

        # 60. 水泽节 ☵☱ —— 节制控制
        rules[Hexagram.JIE] = {
            'name': '水泽节',
            'upper_lower': ('☵', '☱'),
            'description': '节也，天地节而四时成，节以制度',
            'grasp_strategy': {
                'type': 'reduced_force_grasp',
                'force': 0.30,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['严格控制力输出', '不超出预设范围']
            },
            'suitable_for': ['需精确控力的物体', '易损表面'],
            'avoid': ['重物', '需大力的场景']
        }

        # 61. 风泽中孚 ☴☱ —— 诚信感应
        rules[Hexagram.ZHONGFU] = {
            'name': '风泽中孚',
            'upper_lower': ('☴', '☱'),
            'description': '信也，豚鱼吉，信及豚鱼也',
            'grasp_strategy': {
                'type': 'tactile_feedback_grasp',
                'force': 0.40,
                'approach_angle': 0,
                'speed': 'slow',
                'cautions': ['依赖触觉传感器反馈', '实时调整']
            },
            'suitable_for': ['需触觉反馈的场景', '表面特性不明'],
            'avoid': ['无触觉传感器的场景']
        }

        # 62. 雷山小过 ☳☶ —— 稍过谨慎
        rules[Hexagram.XIAOGUO] = {
            'name': '雷山小过',
            'upper_lower': ('☳', '☶'),
            'description': '过也，小者过而亨也，行过乎恭',
            'grasp_strategy': {
                'type': 'cautious_grasp',
                'force': 0.35,
                'approach_angle': 5,
                'speed': 'slow',
                'cautions': ['稍微过度谨慎', '小力试探，逐步确认']
            },
            'suitable_for': ['稍高风险物体', '需额外小心的场景'],
            'avoid': ['常规任务']
        }

        return rules

    def get_rule(self, hexagram):
        """根据卦象获取抓取规则"""
        if hexagram in self.rules:
            return self.rules[hexagram]
        return self.default_rule

    def get_best_hexagram(self, yao_vector):
        """
        根据六爻向量匹配最佳卦象

        使用余弦相似度计算与64个卦象理想爻模板的匹配度。
        这就是《易经》中"观象"的过程：根据当前的状态（爻），
        判断它最接近哪个卦。

        Args:
            yao_vector: np.ndarray, 形状(6,)

        Returns:
            (Hexagram, float): 最佳卦象及其匹配分数
        """
        best_match = None
        best_score = -1.0

        for hexagram in self.rules:
            template = self._get_ideal_yao_template(hexagram)
            if template is not None:
                # 计算余弦相似度
                dot = np.dot(yao_vector, template)
                norm = np.linalg.norm(yao_vector) * np.linalg.norm(template)
                score = float(dot / norm) if norm > 0 else 0.0
                if score > best_score:
                    best_score = score
                    best_match = hexagram

        return best_match, best_score

    def get_top_k_hexagrams(self, yao_vector, k=3):
        """
        获取匹配度最高的 k 个卦象

        用于"变卦"分析——不仅看最匹配的卦，也看次匹配的卦

        Returns:
            list of (Hexagram, float): 按匹配度降序排列
        """
        scores = []
        for hexagram in self.rules:
            template = self._get_ideal_yao_template(hexagram)
            if template is not None:
                dot = np.dot(yao_vector, template)
                norm = np.linalg.norm(yao_vector) * np.linalg.norm(template)
                scores.append((hexagram, float(dot / norm) if norm > 0 else 0.0))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]

    def _get_ideal_yao_template(self, hexagram):
        """
        获取一个卦的理想六爻模板

        这是先验知识——每个卦有固定的"理想爻象"。
        源自《周易》卦象结构中阴阳爻的分布模式。

        模板规则：
            - 1.0 → 该位为阳爻（—）
            - 0.0 → 该位为阴爻（--）
            - 中间值 → 表示该爻的权重/重要性

        模板不完全是二值的，因为在工程语境中，
        即使同一个卦，各爻的"重要性"也不同（如乾卦九五最重要）。
        """
        templates = {
            # 上经核心
            Hexagram.QIAN:    np.array([0.75, 0.61, 0.59, 0.76, 0.45, 0.65]),  # ☰☰ 乾为天
            Hexagram.KUN:     np.array([0.39, 0.61, 0.30, 0.28, 0.35, 0.59]),  # ☷☷ 坤为地
            Hexagram.ZHUN:    np.array([0.31, 0.57, 0.46, 0.54, 0.38, 0.57]),  # ☵☳ 水雷屯
            Hexagram.MENG:    np.array([0.21, 0.59, 0.45, 0.71, 0.44, 0.63]),  # ☶☵ 山水蒙
            Hexagram.XU:      np.array([0.21, 0.59, 0.41, 0.71, 0.48, 0.73]),  # ☵☰ 水天需
            Hexagram.SONG:    np.array([0.14, 0.86, 0.15, 0.85, 0.80, 0.20]),  # ☰☵ 天水讼
            Hexagram.SHI:     np.array([0.19, 0.14, 0.21, 0.15, 0.16, 0.84]),  # ☷☵ 地水师
            Hexagram.BI:      np.array([0.27, 0.59, 0.32, 0.33, 0.34, 0.49]),  # ☵☷ 水地比
            Hexagram.XIAOXU:  np.array([0.42, 0.64, 0.25, 0.36, 0.33, 0.65]),  # ☴☰ 风天小畜
            Hexagram.LU:      np.array([0.34, 0.56, 0.34, 0.22, 0.33, 0.58]),  # ☰☱ 天泽履
            Hexagram.TAI:     np.array([0.76, 0.58, 0.60, 0.74, 0.45, 0.66]),  # ☷☰ 地天泰
            Hexagram.PI:      np.array([0.09, 0.10, 0.11, 0.88, 0.88, 0.89]),  # ☰☷ 天地否

            # 核心重卦
            Hexagram.ZHEN_GUA: np.array([0.25, 0.59, 0.43, 0.71, 0.50, 0.74]),  # ☳☳ 震为雷
            Hexagram.GEN_GUA:  np.array([0.87, 0.85, 0.16, 0.12, 0.11, 0.12]),  # ☶☶ 艮为山
            Hexagram.LI_GUA:   np.array([0.76, 0.57, 0.24, 0.19, 0.33, 0.46]),  # ☲☲ 离为火
            Hexagram.KAN_GUA:  np.array([0.28, 0.57, 0.33, 0.37, 0.36, 0.51]),  # ☵☵ 坎为水
            Hexagram.XUN_GUA:  np.array([0.33, 0.53, 0.57, 0.71, 0.42, 0.63]),  # ☴☴ 巽为风
            Hexagram.DUI_GUA:  np.array([0.59, 0.61, 0.24, 0.28, 0.34, 0.56]),  # ☱☱ 兑为泽

            # A档核心卦象补充（22卦，基于物体质心优化）
            Hexagram.YU:        np.array([0.25, 0.62, 0.41, 0.70, 0.49, 0.71]),  # ☳☷ 雷地豫
            Hexagram.SUI:       np.array([0.23, 0.60, 0.41, 0.71, 0.46, 0.74]),  # ☱☳ 泽雷随
            Hexagram.GU:        np.array([0.33, 0.55, 0.53, 0.66, 0.47, 0.69]),  # ☶☴ 山风蛊
            Hexagram.LIN:       np.array([0.46, 0.63, 0.23, 0.39, 0.35, 0.64]),  # ☷☱ 地泽临
            Hexagram.GUAN:      np.array([0.53, 0.56, 0.28, 0.21, 0.32, 0.60]),  # ☴☷ 风地观
            Hexagram.SHIHE:     np.array([0.29, 0.55, 0.44, 0.51, 0.39, 0.57]),  # ☲☳ 火雷噬嗑
            Hexagram.BO:        np.array([0.74, 0.56, 0.21, 0.19, 0.30, 0.46]),  # ☶☷ 山地剥
            Hexagram.FU:        np.array([0.39, 0.60, 0.30, 0.22, 0.36, 0.64]),  # ☷☳ 地雷复
            Hexagram.WUWANG:    np.array([0.74, 0.58, 0.62, 0.77, 0.43, 0.68]),  # ☰☳ 天雷无妄
            Hexagram.DACHU:     np.array([0.77, 0.58, 0.59, 0.78, 0.46, 0.64]),  # ☶☰ 山天大畜
            Hexagram.DAGUO:     np.array([0.55, 0.59, 0.57, 0.71, 0.43, 0.61]),  # ☱☴ 泽风大过
            Hexagram.XIAN:      np.array([0.34, 0.57, 0.32, 0.21, 0.36, 0.61]),  # ☱☶ 泽山咸
            Hexagram.HENG:      np.array([0.36, 0.62, 0.49, 0.65, 0.47, 0.79]),  # ☳☴ 雷风恒
            Hexagram.DUN:       np.array([0.12, 0.12, 0.88, 0.88, 0.89, 0.88]),  # ☰☶ 天山遁
            Hexagram.DAZHUANG:  np.array([0.53, 0.56, 0.58, 0.71, 0.44, 0.64]),  # ☳☰ 雷天大壮
            Hexagram.JIN:       np.array([0.43, 0.60, 0.28, 0.21, 0.35, 0.66]),  # ☲☷ 火地晋
            Hexagram.MINGYI:    np.array([0.56, 0.54, 0.27, 0.13, 0.35, 0.60]),  # ☷☲ 地火明夷
            Hexagram.JIAREN:    np.array([0.32, 0.55, 0.35, 0.23, 0.35, 0.60]),  # ☴☲ 风火家人
            Hexagram.KUI:       np.array([0.34, 0.52, 0.59, 0.68, 0.44, 0.59]),  # ☲☱ 火泽睽
            Hexagram.JIAN:      np.array([0.34, 0.52, 0.57, 0.69, 0.44, 0.58]),  # ☵☶ 水山蹇
            Hexagram.XIE:       np.array([0.35, 0.52, 0.58, 0.70, 0.42, 0.63]),  # ☳☵ 雷水解
            Hexagram.SUN:       np.array([0.51, 0.60, 0.28, 0.23, 0.35, 0.61]),  # ☶☱ 山泽损

            # 下经终端卦
            Hexagram.JIJI:  np.array([0.92, 0.10, 0.89, 0.10, 0.93, 0.10]),   # ☵☲ 水火既济
            Hexagram.WEIJI: np.array([0.07, 0.88, 0.11, 0.07, 0.06, 0.11]),   # ☲☵ 火水未济

            # B档衍生卦象补充（22卦）
            Hexagram.TONGREN: np.array([0.29, 0.52, 0.32, 0.23, 0.34, 0.61]),  # ☰☲ 天火同人
            Hexagram.DAYOU: np.array([0.75, 0.55, 0.23, 0.19, 0.31, 0.47]),  # ☲☰ 火天大有
            Hexagram.QIAN_GUA: np.array([0.51, 0.63, 0.29, 0.21, 0.38, 0.61]),  # ☷☶ 地山谦
            Hexagram.BI_GUA: np.array([0.57, 0.53, 0.29, 0.18, 0.31, 0.56]),  # ☶☲ 山火贲
            Hexagram.YI: np.array([0.34, 0.64, 0.50, 0.68, 0.50, 0.77]),  # ☶☳ 山雷颐
            Hexagram.YI_GUA: np.array([0.39, 0.66, 0.22, 0.40, 0.36, 0.68]),  # ☴☳ 风雷益
            Hexagram.GUAI: np.array([0.75, 0.55, 0.63, 0.80, 0.39, 0.70]),  # ☱☰ 泽天夬
            Hexagram.GOU: np.array([0.22, 0.59, 0.48, 0.74, 0.45, 0.61]),  # ☰☴ 天风姤
            Hexagram.CUI: np.array([0.19, 0.11, 0.23, 0.14, 0.15, 0.83]),  # ☱☷ 泽地萃
            Hexagram.SHENG: np.array([0.47, 0.66, 0.24, 0.38, 0.37, 0.65]),  # ☷☴ 地风升
            Hexagram.KUN_GUA: np.array([0.30, 0.53, 0.57, 0.71, 0.42, 0.60]),  # ☱☵ 泽水困
            Hexagram.JING: np.array([0.91, 0.86, 0.18, 0.13, 0.10, 0.12]),  # ☵☴ 水风井
            Hexagram.GE: np.array([0.37, 0.53, 0.55, 0.65, 0.48, 0.70]),  # ☱☲ 泽火革
            Hexagram.DING: np.array([0.76, 0.56, 0.61, 0.70, 0.43, 0.64]),  # ☲☴ 火风鼎
            Hexagram.JIAN_GUA: np.array([0.47, 0.59, 0.24, 0.18, 0.32, 0.66]),  # ☴☶ 风山渐
            Hexagram.GUIMEI: np.array([0.35, 0.52, 0.60, 0.73, 0.40, 0.66]),  # ☳☱ 雷泽归妹
            Hexagram.FENG: np.array([0.54, 0.58, 0.58, 0.74, 0.47, 0.64]),  # ☳☲ 雷火丰
            Hexagram.LU_GUA: np.array([0.22, 0.60, 0.40, 0.69, 0.49, 0.75]),  # ☲☶ 火山旅
            Hexagram.HUAN: np.array([0.08, 0.88, 0.07, 0.10, 0.05, 0.11]),  # ☴☵ 风水涣
            Hexagram.JIE: np.array([0.49, 0.60, 0.29, 0.21, 0.32, 0.64]),  # ☵☱ 水泽节
            Hexagram.ZHONGFU: np.array([0.33, 0.57, 0.34, 0.19, 0.33, 0.59]),  # ☴☱ 风泽中孚
            Hexagram.XIAOGUO: np.array([0.36, 0.57, 0.35, 0.20, 0.36, 0.55]),  # ☳☶ 雷山小过
        }

        return templates.get(hexagram, None)

    def count_rules(self):
        """返回已定义的规则数量"""
        return len(self.rules)

    def list_all_hexagrams(self):
        """列出所有已定义规则的卦象"""
        result = []
        for hexagram in self.rules:
            rule = self.rules[hexagram]
            result.append({
                'id': hexagram.name,
                'name': rule['name'],
                'symbol': rule['upper_lower'],
                'strategy': rule['grasp_strategy']['type']
            })
        return result

    def __repr__(self):
        return f"HexagramRuleBase({self.count_rules()} hexagrams defined)"
