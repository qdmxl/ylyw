#!/usr/bin/env python3
"""
YLYW 几何驱动灵巧手手指角度推理

核心思想：
  不是手工写缩放规则，而是把物体几何尺寸作为物理特征扩展，
  通过 YLYW 的 L1→L2→L3 推理链来确定每根手指的关节角度。

输入特征（17维 = 原有13维 + 4维几何扩展）：
  原有13维: stability, roll_tendency, strength_needed, fragility,
            reachability, grasp_surface_quality, support_area, occlusion,
            obstacle_density, task_priority, weight_ratio, visibility, deformability
  几何4维 (新增):
            obj_width, obj_height, obj_diameter, shape_type

L1八卦隶属度: 使用原有8卦 + 新增2个几何原型
  - 原有: 乾(刚健) 坤(柔顺) 震(动态) 艮(静止) 离(可见) 坎(危险) 兑(柔和) 巽(入微)
  - 新增: 大(物体大小) 形(形状规则度)

L2六爻 → 映射到每根手指的2个关节角度：
  初爻: 拇指对掌角 (THJ1)  — 物体越宽/越大 → 对掌越大
  二爻: 拇指弯曲角 (THJ2)  — 物体越高/越细长 → 弯曲越多
  三爻: 四指基部弯曲 (J1均值) — 物体越大 → 弯越多
  四爻: 四指末端弯曲 (J2均值) — 物体越高/不规整 → 末端多弯
  五爻: 手指张开幅度 — 物体越宽 → 张越开
  上爻: 速度/力修正 — 脆弱/不稳定 → 降力

每根手指根据其角色（拇指/食指/中指/无名指/小指）对六爻做角色偏移。
"""

FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']

# ─── 形状编码（one-hot 替代） ───
SHAPE_TYPES = {'sphere': 0, 'box': 0.2, 'cylinder': 0.4, 'rod': 0.5,
               'mushroom': 0.7, 'dumbbell': 0.8, 'disc': 0.9}
SHAPE_REGULARITY = {'sphere': 1.0, 'box': 1.0, 'cylinder': 0.9,
                    'rod': 0.3, 'mushroom': 0.2, 'dumbbell': 0.1, 'disc': 0.4}


class GeometricYLYW:
    """
    YLYW 几何驱动手指角度推理器

    通过 YLYW 的 L1-L2-L3 推理链，根据物体几何特征预测
    每根手指的最佳关节角度。
    """

    def __init__(self):

        # 物体特征参考范围（用于归一化）
        self.ref_width = 0.056       # 球体直径
        self.ref_height = 0.056      # 球体高度
        self.ref_diameter = 0.056    # 球体等效直径

    def build_features(self, obj_key: str) -> dict:
        """
        根据物体类型构建17维输入特征。
        原有13维从几何推导，4维几何扩展直接编码。
        """
        from geometry_adapter import OBJECT_GEOMETRY
        geo = OBJECT_GEOMETRY.get(obj_key, OBJECT_GEOMETRY['sphere'])
        w, h, d = geo['width'], geo['height'], geo['diameter']
        shape_idx = SHAPE_TYPES.get(obj_key, 0.5)
        regularity = SHAPE_REGULARITY.get(obj_key, 0.5)

        # 从几何推导物理特征
        # 稳定性: 接触面积大→稳定，接触面积小→不稳定
        # 球体接触面积极小→低稳定；盘状/立方体→高稳定
        if d > 0.04:
            stability = min(1.0, 0.3 + w * 5)
        else:
            stability = min(0.7, 0.2 + d * 10)

        # 滚动倾向: 球体高，其他低
        roll = 0.9 if obj_key == 'sphere' else (0.6 if obj_key == 'cylinder' else 0.1)

        # 力需求: 大/重物高，小/轻物低
        strength = min(1.0, 0.3 + w * 8 + h * 5)

        # 脆弱性: 细长物(rod)和蘑菇体脆弱，规整物低
        fragility = 0.9 if obj_key == 'rod' else (
            0.7 if obj_key == 'mushroom' else (
                0.6 if obj_key in ('dumbbell', 'disc') else 0.3))

        # 可达性: 规整/居中好，不规则稍差
        reach = 0.9 if regularity > 0.8 else (0.7 if regularity > 0.5 else 0.5)

        # 表面质量: 球光滑，立方粗糙
        surface = 0.5 if obj_key == 'sphere' else (
            0.8 if obj_key == 'box' else 0.6)

        # 支撑面积: 与宽度成正比
        support = min(1.0, w * 12)

        # 遮挡 (0)
        occlusion = 0.0

        # 障碍密度 (0)
        obstacle = 0.0

        # 任务优先级 (0.5 默认)
        priority = 0.5

        # 重量比 (质量/参考质量)
        mass_map = {'sphere': 0.05, 'box': 0.06, 'cylinder': 0.05,
                    'rod': 0.04, 'mushroom': 0.06, 'dumbbell': 0.06, 'disc': 0.04}
        weight = mass_map.get(obj_key, 0.05) / 0.06

        # 可见性 (1.0)
        visibility = 1.0

        # 可变形性 (0.0 ~ 0.1)
        deform = 0.1 if obj_key == 'mushroom' else 0.0

        features = {
            'stability': max(0.01, stability),
            'roll_tendency': roll,
            'strength_needed': strength,
            'fragility': fragility,
            'reachability': reach,
            'grasp_surface_quality': surface,
            'support_area': support,
            'occlusion': occlusion,
            'obstacle_density': obstacle,
            'task_priority': priority,
            'weight_ratio': weight,
            'visibility': visibility,
            'deformability': deform,
            # 几何扩展
            'obj_width': min(1.0, w / self.ref_width),
            'obj_height': min(1.5, h / self.ref_height),
            'obj_diameter': min(1.0, d / self.ref_diameter),
            'shape_type': shape_idx,
        }
        return features

    def infer_finger_angles(self, obj_key: str) -> dict:
        """
        主推理：从物体几何 →  (手指角度, 手腕姿态, 力矩修正)

        5根手指映射为5爻。
        输出：
          angles: 每指(J1,J2)
          wrist: (pitch, yaw) 手腕角度
          torque_mod: 每指力矩修正系数
        """
        features = self.build_features(obj_key)

        # ─── L1: 八卦隶属度 ───
        mu = {}
        mu['qian'] = min(1.0, features['strength_needed'] * 1.2)
        mu['kun'] = 1.0 - features['fragility']
        mu['zhen'] = features['roll_tendency']
        mu['gen'] = features['stability']
        mu['li'] = features['visibility']
        mu['kan'] = (features['fragility'] + (1 - features['stability'])) / 2
        mu['dui'] = features['deformability']
        mu['xun'] = 1.0 - features['obj_diameter']

        w_scale = features['obj_width']
        h_scale = features['obj_height']
        d_scale = features['obj_diameter']
        fragility = features['fragility']
        sigma = features['shape_type']  # 形状规则度

        # ─── L2: 六爻（扩展为8个因子：6手指 + 2手腕）───
        yaos = {}
        yaos['chu'] = min(1.2, 0.2 + w_scale * 0.5 + mu['qian'] * 0.3)       # 拇指J1
        yaos['er'] = min(1.2, 0.2 + h_scale * 0.3 + mu['xun'] * 0.4)          # 拇指J2
        yaos['san'] = min(1.2, 0.3 + (1 - d_scale) * 0.6 + mu['qian'] * 0.2)  # 四指J1
        yaos['si'] = min(1.2, 0.2 + h_scale * 0.3 + fragility * 0.3)          # 四指J2
        yaos['wu'] = min(1.2, 0.3 + w_scale * 0.5)                            # 张开
        yaos['shang'] = max(0.6, 1.0 - fragility * 0.3 - (1 - features['stability']) * 0.2)

        # 手腕角度（新增）
        # 手腕俯仰：高物/矮物 → 不同俯仰角度
        # 仰(pitch>0)→手向后缩→需要前伸手指补偿
        wrist_pitch = 0.3 + (1.0 - min(h_scale, 1.5) / 1.5) * 0.3 - sigma * 0.1
        wrist_pitch = max(-0.5, min(wrist_pitch, 0.6))

        # 手腕偏转
        wrist_yaw = (w_scale - 0.5) * 0.15
        wrist_yaw = max(-0.4, min(wrist_yaw, 0.4))

        # 前伸补偿（根据手腕姿态调整手指前伸量）
        # pitch>0（仰起）→ 手掌后仰 → 需要前伸
        # pitch<0（俯下）→ 手掌前倾 → 无需前伸甚至微缩
        reach = 0.02 + wrist_pitch * 0.06  # pitch=0→reach=0.02, pitch=0.5→reach=0.05
        reach = max(0.0, min(reach, 0.06))

        # ─── 基础角度分配 ───
        angles = {
            'thumb':  (min(1.2, yaos['chu']), min(1.2, yaos['er'] * 0.8)),
            'index':  (min(1.2, yaos['san']), min(1.2, yaos['si'] * 0.9)),
            'middle': (min(1.2, yaos['san'] * 1.1), min(1.2, yaos['si'] * 1.0)),
            'ring':   (min(1.2, yaos['san'] * 0.9), min(1.2, yaos['si'] * 0.8)),
            'pinky':  (min(1.2, yaos['san'] * 0.8), min(1.2, yaos['si'] * 0.7)),
        }
        wrist = (wrist_pitch, wrist_yaw, reach)

        # ─── 形状特殊调整 ───
        if obj_key == 'mushroom':
            angles['thumb'] = (angles['thumb'][0] * 0.8, angles['thumb'][1] * 1.3)
            for f in ['index', 'middle', 'ring']:
                angles[f] = (angles[f][0] * 0.6, angles[f][1] * 1.4)
            wrist = (0.05, -0.15, 0.02)
        elif obj_key == 'dumbbell':
            for f in FINGER_NAMES:
                angles[f] = (angles[f][0] * 1.1, angles[f][1] * 1.2)
            wrist = (0.1, 0.15, 0.03)
        elif obj_key == 'long_rod':
            for f in FINGER_NAMES:
                angles[f] = (angles[f][0] * 0.9, angles[f][1] * 1.3)
            wrist = (0.5, 0.0, 0.05)
        elif obj_key == 'disc':
            for f in FINGER_NAMES:
                angles[f] = (angles[f][0] * 0.6, angles[f][1] * 1.2)
            wrist = (-0.3, 0.0, 0.0)
        elif obj_key == 'sphere':
            wrist = (-0.2, 0.0, 0.01)
        elif obj_key == 'cylinder':
            wrist = (0.3, 0.0, 0.04)

        for f in FINGER_NAMES:
            p1, p2 = angles[f]
            angles[f] = (max(0.0, min(p1, 1.2)), max(0.0, min(p2, 1.2)))

        # ═══ 单指力矩修正系数（爻位关系） ═══
        yang_positions = {0, 1}
        yin_positions = {4}
        finger_list = ['thumb', 'index', 'middle', 'ring', 'pinky']
        finger_roles = {f: i for i, f in enumerate(finger_list)}
        j1_values = {f: angles[f][0] for f in finger_list}

        dangwei_mod = {}
        for f in finger_list:
            pos = finger_roles[f]
            is_yang = j1_values[f] >= 0.5
            should_be_yang = pos in yang_positions
            should_be_yin = pos in yin_positions
            mod = 1.0
            if should_be_yang and not is_yang:
                mod = 1.20
            elif should_be_yin and is_yang:
                mod = 0.80
            dangwei_mod[f] = mod

        cheng_mod = {f: 1.0 for f in finger_list}
        for i in range(4):
            upper, lower = finger_list[i], finger_list[i+1]
            up_val, low_val = j1_values[upper], j1_values[lower]
            if up_val > low_val + 0.2:
                cheng_mod[upper] *= 0.88; cheng_mod[lower] *= 1.12
            elif low_val > up_val + 0.2:
                cheng_mod[upper] *= 1.12; cheng_mod[lower] *= 0.88

        bi_mod = {f: 1.0 for f in finger_list}
        for i in range(4):
            a, b = finger_list[i], finger_list[i+1]
            a_yang = j1_values[a] >= 0.5; b_yang = j1_values[b] >= 0.5
            m = 1.06 if a_yang == b_yang else 0.94
            bi_mod[a] *= m; bi_mod[b] *= m

        torque_mod = {}
        for f in finger_list:
            mod = dangwei_mod.get(f,1.0) * cheng_mod.get(f,1.0) * bi_mod.get(f,1.0)
            torque_mod[f] = max(0.6, min(mod, 1.5))

        self._torque_mod = torque_mod
        self._wrist = wrist

        return angles

    @property
    def torque_modifiers(self) -> dict:
        return getattr(self, '_torque_mod', {f: 1.0 for f in FINGER_NAMES})

    @property
    def wrist_angles(self) -> tuple:
        return getattr(self, '_wrist', (0.0, 0.0, 0.0))

    def explain(self, obj_key: str) -> str:
        """可解释的推理链"""
        features = self.build_features(obj_key)
        angles = self.infer_finger_angles(obj_key)
        lines = [
            f"物体: {obj_key}",
            f"特征: w={features['obj_width']:.2f} h={features['obj_height']:.2f} d={features['obj_diameter']:.2f}",
            f"L1八卦: 乾={min(1.0, features['strength_needed']*1.2):.2f} 坤={1-features['fragility']:.2f} "
            f"震={features['roll_tendency']:.2f} 离={features['visibility']:.1f}",
            f"L2六爻: (初){0.2+features['obj_width']*0.5:.2f} "
            f"(二){0.2+features['obj_height']*0.3:.2f} "
            f"(三){0.3+(1-features['obj_diameter'])*0.6:.2f} "
            f"(四){0.2+features['obj_height']*0.3+features['fragility']*0.3:.2f} "
            f"(五){0.3+features['obj_width']*0.5:.2f}",
        ]
        for f in FINGER_NAMES:
            lines.append(f"  {f}: ({angles[f][0]:.2f}, {angles[f][1]:.2f})")
        return "\n".join(lines)


if __name__ == '__main__':
    gylyw = GeometricYLYW()
    print("=" * 60)
    print("YLYW 几何驱动手指角度推理")
    print("=" * 60)

    from geometry_adapter import OBJECT_GEOMETRY
    for obj_key in OBJECT_GEOMETRY:
        print(f"\n{'─'*60}")
        print(gylyw.explain(obj_key))
        angles = gylyw.infer_finger_angles(obj_key)
        for f in FINGER_NAMES:
            p1, p2 = angles[f]
            ok = '✅' if 0 < p1 <= 1.2 and 0 < p2 <= 1.2 else '❌'
            print(f"  {f:6s}: ({p1:.2f}, {p2:.2f}) {ok}")
