#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《易理研物》封面：填充 64 卦网格、生态网络，输出 SVG + PNG。"""
import random, os
random.seed(64)

BASE = os.path.dirname(os.path.abspath(__file__))

# ---- 64 卦网格：8x8，每格一卦（6 条爻线，实/断） ----
cell = 44          # 格宽
gap = 6
CJ = 26            # 爻线长
hex_lines = []
for r in range(8):
    for c in range(8):
        # 用行列位模式生成 6 爻（确保每卦不同）
        bits = [(c >> i) & 1 if i < 3 else (r >> (i - 3)) & 1 for i in range(6)]
        x = c * (cell + gap)
        y = r * (cell + gap)
        for i, b in enumerate(reversed(bits)):  # 自下而上
            ly = y + i * 6
            col = '#2b3a4a' if b else '#5a6b7a'
            if b:  # 阳爻：整条
                hex_lines.append(
                    f'<line x1="{x+1}" y1="{ly}" x2="{x+1+CJ}" y2="{ly}" '
                    f'stroke="{col}" stroke-width="3.4" stroke-linecap="round"/>')
            else:  # 阴爻：断开
                half = (CJ - 8) / 2
                hex_lines.append(
                    f'<line x1="{x+1}" y1="{ly}" x2="{x+1+half}" y2="{ly}" '
                    f'stroke="{col}" stroke-width="3.4" stroke-linecap="round"/>'
                    f'<line x1="{x+1+CJ-half}" y1="{ly}" x2="{x+1+CJ}" y2="{ly}" '
                    f'stroke="{col}" stroke-width="3.4" stroke-linecap="round"/>')
HEXGRID = '\n        '.join(hex_lines)

# ---- 生态网络节点与连线 ----
# 三个聚簇中心，各生成若干节点
clusters = [(255, 1105), (620, 1115), (985, 1105)]
nodes = []
for cx, cy in clusters:
    for _ in range(9):
        nodes.append((cx + random.uniform(-72, 72), cy + random.uniform(-40, 40)))
# 连线：簇内近邻 + 跨簇主干
links = []
for i, (x1, y1) in enumerate(nodes):
    for j, (x2, y2) in enumerate(nodes):
        if j <= i:
            continue
        d = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        if d < 90:
            links.append((x1, y1, x2, y2, 0.45))
# 跨簇主干（连接三簇中心）
for a in range(3):
    for b in range(a + 1, 3):
        x1, y1 = clusters[a]; x2, y2 = clusters[b]
        links.append((x1, y1, x2, y2, 0.6))

NETLINKS = '\n  '.join(
    f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
    f'stroke-opacity="{o}"/>' for x1, y1, x2, y2, o in links)
NODES = '\n  '.join(
    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5"/>' for x, y in nodes)

svg = open(os.path.join(BASE, 'cover_template.svg'), encoding='utf-8').read()
svg = svg.replace('__HEXGRID__', HEXGRID)
svg = svg.replace('__NETLINKS__', NETLINKS)
svg = svg.replace('__NODES__', NODES)
out_svg = os.path.join(BASE, 'cover.svg')
open(out_svg, 'w', encoding='utf-8').write(svg)
print('wrote', out_svg)

import cairosvg
out_png = os.path.join(BASE, 'cover_preview.png')
cairosvg.svg2png(url=out_svg, write_to=out_png, output_width=992, output_height=1403)
print('wrote', out_png)
