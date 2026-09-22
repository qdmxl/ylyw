#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面方案I：拟真人的侧脸 + 头发为发光电子器件；八卦神经核嵌于后脑。"""
import math, os, random
BASE = os.path.dirname(os.path.abspath(__file__))

def gua(bits, L=26):
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
ring = []; R1 = 128
for k in range(8):
    ang = k*45.0; rad = math.radians(ang-90)
    x, y = R1*math.cos(rad), R1*math.sin(rad)
    ring.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate({-ang:.1f})" '
                f'stroke="#a9ecff" stroke-width="2.6" stroke-linecap="round" opacity="0.98">'
                + gua(TRIGRAMS[k], L=30) + '</g>')
R2 = 168
for k in range(16):
    ang = k*22.5 + 11.25; rad = math.radians(ang-90)
    x, y = R2*math.cos(rad), R2*math.sin(rad)
    bits = [(k >> i) & 1 for i in range(6)]
    ring.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate({-ang:.1f})" '
                f'stroke="#7fd4f0" stroke-width="1.4" stroke-linecap="round" opacity="0.55">'
                + gua(bits, L=16) + '</g>')
links = []
for k in range(8):
    a1 = math.radians(k*45-90); a2 = math.radians(((k+1)%8)*45-90)
    links.append(f'<line x1="{R1*math.cos(a1):.1f}" y1="{R1*math.sin(a1):.1f}" '
                 f'x2="{R1*math.cos(a2):.1f}" y2="{R1*math.sin(a2):.1f}" '
                 f'stroke="#7fe3ff" stroke-width="1.1" opacity="0.45"/>')
    links.append(f'<line x1="{R1*math.cos(a1):.1f}" y1="{R1*math.sin(a1):.1f}" x2="0" y2="0" '
                 f'stroke="#a9ecff" stroke-width="0.8" opacity="0.3"/>')
BRAIN = ''.join(links) + ''.join(ring)

# --- 头发：电路/芯片/光点 ---
random.seed(5)
hair = []
# 发光点
for _ in range(46):
    x = random.uniform(-96, 88); y = random.uniform(-206, -52)
    # 限制在颅顶弧线附近
    d = ((x + 4) ** 2) / 110 ** 2 + ((y + 150) ** 2) / 100 ** 2
    if d > 0.55:
        r = random.uniform(2.2, 5.6)
        col = random.choice(['#7fe3ff', '#a9ecff', '#5fc8ea', '#e8fbff'])
        hair.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{col}" opacity="0.95"/>')
# 电路走线（沿颅顶的折线）
for _ in range(14):
    x0 = random.uniform(-94, 84); y0 = random.uniform(-200, -60)
    pts = [(x0, y0)]
    for _ in range(3):
        x0 += random.choice([-1, 1]) * random.uniform(14, 30)
        y0 += random.choice([-1, 1]) * random.uniform(10, 24)
        pts.append((x0, y0))
    path = 'M' + ' L'.join(f'{px:.1f} {py:.1f}' for px, py in pts)
    hair.append(f'<path d="{path}" fill="none" stroke="#4fb6dd" stroke-width="1.2" opacity="0.6"/>')
# 小芯片方块
for _ in range(9):
    x = random.uniform(-88, 80); y = random.uniform(-198, -66)
    s = random.uniform(7, 13)
    rot = random.choice([0, 45])
    hair.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" '
                f'transform="rotate({rot} {x:.1f} {y:.1f})" fill="none" stroke="#8fe6ff" '
                f'stroke-width="1.4" opacity="0.75"/>')
# 水平排针（发丝感）
for i in range(20):
    y = -196 + i * 7
    x0 = -92 + abs(y + 150) * 0.55
    x1 = x0 + random.uniform(20, 46)
    hair.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
                f'stroke="#7fd4f0" stroke-width="1.3" opacity="0.5"/>')
HAIR = ''.join(hair)

svg = open(os.path.join(BASE, 'cover9_template.svg'), encoding='utf-8').read()
svg = svg.replace('__BRAIN_RING__', BRAIN).replace('__HAIR__', HAIR)
out = os.path.join(BASE, 'cover9.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
import cairosvg
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover9_hires.png'),
                 output_width=2480, output_height=3508)
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover9_full.png'),
                 output_width=1240, output_height=1754)
print('wrote previews')
