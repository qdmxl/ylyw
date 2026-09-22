#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qyuf_world_model.py — QYUF版汉字世界模型

用QYUF的多特征分形 + 八卦相荡替代V20 cn_world_model的HanziEngine汉字推理。
覆盖链路：
  经典: 实体名 → 汉字(HanziEngine → 部首分解 → 卦象L1→L2→L3) → 八卦隶属度
  量子: 实体名 → 6维物理特征 → U_摩八卦相荡 → 64维酉演化 → 概率分布 → 八卦隶属度

这是纯量子方案的关键一步：汉字语义理解也来自量子机制而非经典YLYW。
"""

from __future__ import annotations
import os, sys
from typing import Dict, List, Optional, Tuple, Set
import numpy as np

# 继承CnWorldModel的完整接口
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "v20"))
from cn_world_model import CnWorldModel

# 引入QYUF的YaoBuilder
_QYUF_ROOT = '/home/lijinhan/MXL/科研/ylyw/QYUF/experiment'
_QYUF_PARENT = '/home/lijinhan/MXL/科研/ylyw/QYUF'
_YLYW_ROOT = '/home/lijinhan/MXL/科研/ylyw'
if _QYUF_ROOT not in sys.path:
    sys.path.insert(0, _QYUF_ROOT)
if _QYUF_PARENT not in sys.path:
    sys.path.insert(0, _QYUF_PARENT)

_BAGUA_NAMES = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]


class QYUFWorldModel(CnWorldModel):
    """
    QYUF版汉字世界模型
    
    继承CnWorldModel的全部公共接口（init_from_reset, observe_transition, state_key等），
    仅覆盖内部的`_get_bagua`和`_get_yao`方法，用YaoBuilder的多特征分形签名替代
    HanziEngine的汉字→部首→卦象L1→L2→L3的经典推理链。
    
    这样V21 Agent的act/score_candidate/phase等全部逻辑不变，
    但最底层的汉字语义感知已替换为量子机制。
    """
    
    def __init__(self):
        super().__init__()
        # 引入QYUF的YaoBuilder（惰性初始化避免循环依赖）
        self._qyuf_yao_builder = None
        self._qyuf_init_ok = False
    
    def _init_qyuf(self):
        """惰性初始化QYUF引擎"""
        if self._qyuf_init_ok:
            return
        try:
            for p in [_QYUF_ROOT, _QYUF_PARENT, _YLYW_ROOT]:
                if p not in sys.path:
                    sys.path.insert(0, p)
            from qyuf_model import YaoBuilder
            self._qyuf_yao_builder = YaoBuilder()
            self._qyuf_init_ok = True
        except Exception as e:
            print(f"[QYUFWorldModel] 初始化失败: {e}，回退经典CnWorldModel")
            self._qyuf_init_ok = False
    
    def _get_bagua(self, hanzi: str) -> Tuple[str, List[float]]:
        """
        覆盖父类：用QYUF多特征分形替代HanziEngine汉字推理
        
        步骤：
          1. 将汉字通过bridge转为英文实体类型（如果可用）
          2. 用YaoBuilder._compute_prob_dist获取64维概率分布
          3. 从分布提取8维八卦隶属度（上/下卦各边际化）
          4. 取主导八卦
        """
        if hanzi in self._bagua_cache:
            return self._bagua_cache[hanzi]
        
        self._init_qyuf()
        if not self._qyuf_init_ok or self._qyuf_yao_builder is None:
            # 回退父类
            return super()._get_bagua(hanzi)
        
        try:
            # 汉字 → 英文实体名（通过bridge的反向映射）
            en_name = hanzi
            if hasattr(self.bridge, 'OBJ_MAP_EN2CN'):
                en2cn = self.bridge.OBJ_MAP_EN2CN
                for en, cn in en2cn.items():
                    if cn == hanzi:
                        en_name = en
                        break
            
            # 用QYUF的64维概率签名
            probs64 = self._qyuf_yao_builder._compute_prob_dist(en_name)
            if probs64 is None:
                return super()._get_bagua(hanzi)
            
            # 64维 → 8维八卦隶属度
            # 取上卦边际化（边缘求和）作为八卦隶属度
            # 上卦 = 高3位(bit[5:3])，下卦 = 低3位(bit[2:0])
            bagua = np.zeros(8, dtype=float)
            for idx in range(64):
                upper = (idx >> 3) & 0x7  # 上卦索引
                # 仅上卦求和——使用边际分布而非上下卦平均
                bagua[upper] += probs64[idx]
            
            # 归一化
            bg_sum = bagua.sum()
            if bg_sum > 1e-10:
                bagua /= bg_sum
            
            dom_idx = int(np.argmax(bagua))
            dom_name = _BAGUA_NAMES[dom_idx]
            result = (dom_name, [float(v) for v in bagua])
            
            self._bagua_cache[hanzi] = result
            return result
            
        except Exception:
            return super()._get_bagua(hanzi)
    
    def _get_yao(self, en_id: str, cls: str = "") -> List[float]:
        """
        覆盖父类：用QYUF多特征分形替代HanziEngine的六爻编码
        
        步骤：
          1. 从实体名的64维概率分布中提取6维特征作为六爻
          2. 特征提取：概率分布的香农熵(y0)、峰度(y1)、top3占比(y2)、
             主导卦概率(y3)、上下卦对称度(y4)、分布稀疏度(y5)
        """
        cache_key = f"{en_id}:{cls}"
        if cache_key in self._yao_cache:
            return self._yao_cache[cache_key]
        
        self._init_qyuf()
        if not self._qyuf_init_ok or self._qyuf_yao_builder is None:
            return super()._get_yao(en_id, cls)
        
        try:
            # 获取64维概率分布
            probs64 = self._qyuf_yao_builder._compute_prob_dist(en_id)
            if probs64 is None:
                return super()._get_yao(en_id, cls)
            
            p = probs64.flatten() + 1e-12
            p /= p.sum()
            
            # y0 = 熵（复杂度→阳，集中→阴）
            ent = -np.sum(p * np.log2(p + 1e-12)) / 6.0
            y0 = 0.3 + 0.4 * ent
            
            # y1 = 峰度（峰→稳定刚, 均匀→柔）
            kurt = np.mean((p - np.mean(p))**4) / (np.std(p + 1e-8)**4 + 1e-8)
            y1 = 0.3 + 0.4 * min(kurt / 20.0, 1.0)
            
            # y2 = Top-5占比（集中→动, 分散→静）
            top5 = np.sort(p)[-5:].sum()
            y2 = 0.3 + 0.4 * min(top5 * 3.0, 1.0)
            
            # y3 = 主导卦概率（确信→丽, 不确定→险）
            dom_prob = p.max()
            y3 = 0.2 + 0.6 * min(dom_prob * 10.0, 1.0)
            
            # y4 = 上下卦对称度
            top_half = p[:32].sum()
            bottom_half = p[32:].sum()
            symmetry = 1.0 - abs(top_half - bottom_half)
            y4 = 0.2 + 0.6 * symmetry
            
            # y5 = 稀疏度（零概率比例→纹理粗糙）
            sparse = (p < 0.001).sum() / 64.0
            y5 = 0.2 + 0.6 * sparse
            
            yao = [y0, y1, y2, y3, y4, y5]
            self._yao_cache[cache_key] = yao
            return yao
            
        except Exception:
            return super()._get_yao(en_id, cls)
