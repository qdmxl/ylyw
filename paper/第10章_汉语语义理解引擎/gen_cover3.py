#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面方案C：生长之树——符号先验(根) → 元胞/组织/生态(干) → 通用智能(冠)。"""
import os
BASE = os.path.dirname(os.path.abspath(__file__))

def gua(x, y, sc, bits):
    """在 (x,y) 处画一个小卦（6 爻，自下而上）。bits: 长度6列表，1=阳。"""
    out = [f'<g transform="translate({x:.1f},{y:.1f}) scale({sc})">']
    for i, b in enumerate(reversed(bits)):
        ly = -12 + i * 5
        if b:
            out.append(f'<line x1="-11" y1="{ly}" x2="11" y2="{ly}" stroke="#6d8a99" stroke-width="1.8"/>')
        else:
            out.append(f'<line x1="-11" y1="{ly}" x2="-2.5" y2="{ly}" stroke="#6d8a99" stroke-width="1.8"/>'
                       f'<line x1="2.5" y1="{ly}" x2="11" y2="{ly}" stroke="#6d8a99" stroke-width="1.8"/>')
    out.append('</g>')
    return ''.join(out)

# 根系末端小卦（5条根，坐标对应 template 根线端点）
root_pos = [(455, 1275), (540, 1290), (620, 1295), (700, 1290), (785, 1275)]
roots = ''.join(gua(x, y + 30, 0.9, [(k >> i) & 1 for i in range(6)])
                for k, (x, y) in enumerate(root_pos))
ROOTS = roots

# 叶冠网络：在冠内散布浅色节点+连线（自组织涌现）
import random
random.seed(11)
crown = []
centers = [(620, 520), (500, 640), (740, 640), (620, 660), (450, 700), (790, 700)]
for cx, cy in centers:
    for _ in range(7):
        x = cx + random.uniform(-70, 70)
        y = cy + random.uniform(-55, 55)
        # 限制在树冠圆内
        if (x - 620) ** 2 / 260 ** 2 + (y - 640) ** 2 / 230 ** 2 <= 1:
            crown.append((x, y))
# 连线
lines = []
for i, (x1, y1) in enumerate(crown):
    for j, (x2, y2) in enumerate(crown):
        if j <= i:
            continue
        d = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        if d < 95:
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#eaf3f8" stroke-width="1.3" stroke-opacity="0.7"/>')
nodes = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="#eaf3f8" fill-opacity="0.85"/>' for x, y in crown)
CROWN = ''.join(lines) + nodes

svg = open(os.path.join(BASE, 'cover3_template.svg'), encoding='utf-8').read()
svg = svg.replace('__ROOTS__', ROOTS).replace('__CROWN__', CROWN)
out = os.path.join(BASE, 'cover3.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
import cairosvg
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover3_hires.png'),
                 output_width=2480, output_height=3508)
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover3_full.png'),
                 output_width=1240, output_height=1754)
print('wrote previews')
