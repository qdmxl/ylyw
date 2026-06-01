#!/usr/bin/env python3
"""
补全 A档 22个核心卦象的规则和爻模板

这些卦象对应实际抓取场景中的关键情境，
补全后可显著改善零样本匹配效果。

卦象结构（六爻从下往上：初、二、三、四、五、上）：
  下卦 → 初爻 二爻 三爻
  上卦 → 四爻 五爻 上爻

八卦爻结构（从下往上）：
  乾 ☰: 阳阳阳 → [1,1,1]    坤 ☷: 阴阴阴 → [0,0,0]
  震 ☳: 阳阴阴 → [1,0,0]    艮 ☶: 阴阴阳 → [0,0,1]
  离 ☲: 阳阴阳 → [1,0,1]    坎 ☵: 阴阳阴 → [0,1,0]
  兑 ☱: 阳阳阴 → [1,1,0]    巽 ☴: 阴阳阳 → [0,1,1]

爻值约定: 阳爻=0.80~0.95, 阴爻=0.05~0.20
         重要爻位偏高/偏低，普通爻位居中
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# 22个卦的规则定义
# ============================================================

NEW_RULES = """
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
"""

# ============================================================
# 22个卦的爻模板定义
# ============================================================

NEW_TEMPLATES = """
            # A档核心卦象补充
            Hexagram.YU:        np.array([0.10, 0.10, 0.15, 0.85, 0.15, 0.10]),  # ☳☷ 雷地豫
            Hexagram.SUI:       np.array([0.85, 0.15, 0.20, 0.80, 0.85, 0.15]),  # ☱☳ 泽雷随
            Hexagram.GU:        np.array([0.10, 0.85, 0.80, 0.20, 0.15, 0.85]),  # ☶☴ 山风蛊
            Hexagram.LIN:       np.array([0.85, 0.80, 0.15, 0.10, 0.10, 0.10]),  # ☷☱ 地泽临
            Hexagram.GUAN:      np.array([0.10, 0.10, 0.15, 0.15, 0.85, 0.80]),  # ☴☷ 风地观
            Hexagram.SHIHE:     np.array([0.85, 0.15, 0.20, 0.80, 0.20, 0.85]),  # ☲☳ 火雷噬嗑
            Hexagram.BO:        np.array([0.10, 0.10, 0.10, 0.15, 0.15, 0.90]),  # ☶☷ 山地剥
            Hexagram.FU:        np.array([0.90, 0.15, 0.15, 0.10, 0.10, 0.10]),  # ☷☳ 地雷复
            Hexagram.WUWANG:    np.array([0.85, 0.15, 0.20, 0.85, 0.90, 0.90]),  # ☰☳ 天雷无妄
            Hexagram.DACHU:     np.array([0.85, 0.85, 0.90, 0.15, 0.15, 0.85]),  # ☶☰ 山天大畜
            Hexagram.DAGUO:     np.array([0.10, 0.85, 0.85, 0.85, 0.85, 0.10]),  # ☱☴ 泽风大过
            Hexagram.XIAN:      np.array([0.10, 0.15, 0.85, 0.85, 0.85, 0.15]),  # ☱☶ 泽山咸
            Hexagram.HENG:      np.array([0.10, 0.85, 0.80, 0.85, 0.15, 0.10]),  # ☳☴ 雷风恒
            Hexagram.DUN:       np.array([0.10, 0.15, 0.85, 0.85, 0.90, 0.90]),  # ☰☶ 天山遁
            Hexagram.DAZHUANG:  np.array([0.85, 0.85, 0.90, 0.85, 0.15, 0.10]),  # ☳☰ 雷天大壮
            Hexagram.JIN:       np.array([0.10, 0.10, 0.15, 0.85, 0.20, 0.85]),  # ☲☷ 火地晋
            Hexagram.MINGYI:    np.array([0.85, 0.20, 0.85, 0.10, 0.10, 0.10]),  # ☷☲ 地火明夷
            Hexagram.JIAREN:    np.array([0.85, 0.20, 0.85, 0.15, 0.85, 0.80]),  # ☴☲ 风火家人
            Hexagram.KUI:       np.array([0.85, 0.80, 0.15, 0.85, 0.20, 0.85]),  # ☲☱ 火泽睽
            Hexagram.JIAN:      np.array([0.10, 0.15, 0.85, 0.20, 0.85, 0.15]),  # ☵☶ 水山蹇
            Hexagram.XIE:       np.array([0.10, 0.85, 0.20, 0.85, 0.15, 0.10]),  # ☳☵ 雷水解
            Hexagram.SUN:       np.array([0.85, 0.80, 0.15, 0.15, 0.15, 0.85]),  # ☶☱ 山泽损
"""

if __name__ == '__main__':
    print("这是22个卦的规则和爻模板数据定义。")
    print("请通过edit工具将这些内容插入到 hexagram_rules.py 中。")
    print(f"\n新增规则数: {NEW_RULES.count('name')}")
    print(f"新增模板数: {NEW_TEMPLATES.count('Hexagram.')}")
