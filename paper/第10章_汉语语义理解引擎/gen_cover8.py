#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面方案F：苗条拟人机器人 + 突出的易理（64卦神经核）大脑。"""
import math, os
BASE = os.path.dirname(os.path.abspath(__file__))

def gua(bits, L=30):
    out = []
    for i, b in enumerate(reversed(bits)):
        y = -L / 2 + i * (L / 5)
        if b:
            out.append(f'<line x1="{-L/2:.1f}" y1="{y:.1f}" x2="{L/2:.1f}" y2="{y:.1f}"/>')
        else:
            out.append(f'<line x1="{-L/2:.1f}" y1="{y:.1f}" x2="{-L/8:.1f}" y2="{y:.1f}"/>'
                       f'<line x1="{L/8:.1f}" y1="{y:.1f}" x2="{L/2:.1f}" y2="{y:.1f}"/>')
    return ''.join(out)

TRIGRAMS = [(1,1,1),(0,1,1),(1,0,1),(0,0,1),(1,1,0),(0,1,0),(1,0,0),(0,0,0)]

ring = []
# 内环：8 个三爻卦（半径 150）
R1 = 150
for k in range(8):
    ang = k * 45.0
    rad = math.radians(ang - 90)
    x, y = R1*math.cos(rad), R1*math.sin(rad)
    ring.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate({-ang:.1f})" '
                f'stroke="#ffd979" stroke-width="3" stroke-linecap="round" opacity="0.98">'
                + gua(TRIGRAMS[k], L=32) + '</g>')
# 外环：16 个小卦（半径 195）加密，象征 64 卦全空间
R2 = 195
for k in range(16):
    ang = k * 22.5 + 11.25
    rad = math.radians(ang - 90)
    x, y = R2*math.cos(rad), R2*math.sin(rad)
    bits = [(k >> 2) & 1, (k >> 1) & 1, k & 1, (k >> 3) & 1, (k >> 4 if False else 0) & 1, 1]
    # 简易 6 爻模式
    bits = [ (k>>i)&1 for i in range(6) ]
    ring.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate({-ang:.1f})" '
                f'stroke="#f4c957" stroke-width="1.6" stroke-linecap="round" opacity="0.62">'
                + gua(bits, L=17) + '</g>')

# 环内连接 + 向心汇聚
links = []
for k in range(8):
    a1 = math.radians(k*45 - 90); a2 = math.radians(((k+1)%8)*45 - 90)
    links.append(f'<line x1="{R1*math.cos(a1):.1f}" y1="{R1*math.sin(a1):.1f}" '
                 f'x2="{R1*math.cos(a2):.1f}" y2="{R1*math.sin(a2):.1f}" '
                 f'stroke="#f6cb5c" stroke-width="1.1" opacity="0.45"/>')
    links.append(f'<line x1="{R1*math.cos(a1):.1f}" y1="{R1*math.sin(a1):.1f}" x2="0" y2="0" '
                 f'stroke="#ffd979" stroke-width="0.8" opacity="0.3"/>')
BRAIN = ''.join(links) + ''.join(ring)

# 大脑射线
RAYS = []
for k in range(24):
    ang = math.radians(k*15)
    r0, r1 = 205, 250
    RAYS.append(f'<line x1="{r0*math.cos(ang):.1f}" y1="{r0*math.sin(ang):.1f}" '
                f'x2="{r1*math.cos(ang):.1f}" y2="{r1*math.sin(ang):.1f}"/>')

svg = open(os.path.join(BASE, 'cover8_template.svg'), encoding='utf-8').read()
svg = svg.replace('__BRAIN_RING__', BRAIN).replace('__RAYS__', ''.join(RAYS))
out = os.path.join(BASE, 'cover8.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
import cairosvg
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover8_hires.png'),
                 output_width=2480, output_height=3508)
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover8_full.png'),
                 output_width=1240, output_height=1754)
print('wrote previews')
