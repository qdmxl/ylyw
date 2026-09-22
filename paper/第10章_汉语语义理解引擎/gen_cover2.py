#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面方案B：环形卦象 + 中心太极 + 三阶段。"""
import math, os
BASE = os.path.dirname(os.path.abspath(__file__))

# 环上 64 卦：沿半径 330 和 170 两环排布，每卦 6 爻
def gua_lines(cx, cy, r_scale, angle, length):
    # 在 (cx,cy) 处，按 angle 旋转一条竖排 6 爻
    els = []
    for i in range(6):
        # 位模式（随机但固定）
        b = (int(angle / 5.625) >> (i % 4)) & 1
        y = -length / 2 + i * (length / 5)
        col = '#2b3a4a'
        if b:
            els.append(f'<line x1="{-length/2:.1f}" y1="{y:.2f}" x2="{length/2:.1f}" y2="{y:.2f}" stroke="{col}" stroke-width="1.6"/>')
        else:
            h = length / 2 - 3
            els.append(f'<line x1="{-length/2:.1f}" y1="{y:.2f}" x2="{-3:.1f}" y2="{y:.2f}" stroke="{col}" stroke-width="1.6"/>'
                       f'<line x1="{3:.1f}" y1="{y:.2f}" x2="{length/2:.1f}" y2="{y:.2f}" stroke="{col}" stroke-width="1.6"/>')
    return (f'<g transform="rotate({-angle:.2f}) translate(0,{-r_scale:.1f})">'
            + ''.join(els) + '</g>')

ring = []
for k in range(64):
    ang = k * 5.625
    if k % 1 == 0:
        ring.append(gua_lines(0, 0, 290, ang, 24))
RING = ''.join(ring)

svg = open(os.path.join(BASE, 'cover2_template.svg'), encoding='utf-8').read()
svg = svg.replace('__RING__', RING)
out = os.path.join(BASE, 'cover2.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
import cairosvg
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover2_full.png'),
                 output_width=1240, output_height=1754)
print('wrote cover2_full.png')
