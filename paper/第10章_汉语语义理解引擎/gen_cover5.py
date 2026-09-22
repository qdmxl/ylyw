#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面方案D：具身智能机器人，易理系统作为大脑（八卦神经核）。"""
import math, os
BASE = os.path.dirname(os.path.abspath(__file__))

# 大脑：八卦环——8 个卦象均匀分布在一个圆上（半径 130）
def gua_local(bits, L=40):
    """返回一组 6 爻线的 SVG（局部坐标，竖排，自下而上）。"""
    out = []
    for i, b in enumerate(reversed(bits)):
        y = -L / 2 + i * (L / 5)
        if b:
            out.append(f'<line x1="{-L/2:.1f}" y1="{y:.1f}" x2="{L/2:.1f}" y2="{y:.1f}"/>')
        else:
            out.append(f'<line x1="{-L/2:.1f}" y1="{y:.1f}" x2="{-L/10:.1f}" y2="{y:.1f}"/>'
                       f'<line x1="{L/10:.1f}" y1="{y:.1f}" x2="{L/2:.1f}" y2="{y:.1f}"/>')
    return ''.join(out)

# 八个单卦（三爻）组成的环 → 实际用 8 个三爻卦重复环绕
TRIGRAMS = [
    (1, 1, 1),  # 乾
    (0, 1, 1),  # 兑
    (1, 0, 1),  # 离
    (0, 0, 1),  # 震
    (1, 1, 0),  # 巽
    (0, 1, 0),  # 坎
    (1, 0, 0),  # 艮
    (0, 0, 0),  # 坤
]
ring = []
R = 132
for k in range(8):
    ang = k * 45.0
    bits = TRIGRAMS[k]
    # 位置
    rad = math.radians(ang - 90)
    x = R * math.cos(rad)
    y = R * math.sin(rad)
    ring.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate({-ang:.1f})" '
                f'stroke="#ffd979" stroke-width="2.6" stroke-linecap="round" opacity="0.95">'
                + gua_local(bits, L=30) + '</g>')

# 内外连接线（神经连接）
links = []
for k in range(8):
    a1 = math.radians(k * 45 - 90)
    a2 = math.radians(((k + 1) % 8) * 45 - 90)
    x1, y1 = R * math.cos(a1), R * math.sin(a1)
    x2, y2 = R * math.cos(a2), R * math.sin(a2)
    links.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="#f2c65a" stroke-width="1.2" opacity="0.5"/>')
    # 向中心汇聚
    links.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="0" y2="0" '
                 f'stroke="#ffd979" stroke-width="0.9" opacity="0.35"/>')

BRAIN = ''.join(links) + ''.join(ring)

svg = open(os.path.join(BASE, 'cover5_template.svg'), encoding='utf-8').read()
svg = svg.replace('__BRAIN_RING__', BRAIN)
out = os.path.join(BASE, 'cover5.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
import cairosvg
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover5_hires.png'),
                 output_width=2480, output_height=3508)
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover5_full.png'),
                 output_width=1240, output_height=1754)
print('wrote previews')
