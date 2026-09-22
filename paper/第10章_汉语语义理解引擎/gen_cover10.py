#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面方案J：写实侧脸（朝左）+ 头发为发光电子器件；八卦神经核于后脑。"""
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

# --- 头发中的电子器件：分布在颅顶弧面（局部坐标：中心(0,0), 颅顶约 y=-140..-40, x=-40..230）
random.seed(9)
hair = []
def on_scalp(x, y):
    # 颅顶椭弧：中心(60,-60), rx 200, ry 120（外沿）
    return ((x-60)/210.0)**2 + ((y+70)/150.0)**2 <= 1.05 and y < -20
pts = []
for _ in range(70):
    x = random.uniform(-70, 250); y = random.uniform(-200, -10)
    if on_scalp(x, y):
        pts.append((x, y))
# 电路走线
for _ in range(16):
    if not pts: break
    x0, y0 = random.choice(pts)
    seg = [(x0, y0)]
    for _ in range(3):
        x0 += random.choice([-1, 1]) * random.uniform(16, 34)
        y0 += random.choice([-1, 1]) * random.uniform(8, 22)
        seg.append((x0, y0))
    path = 'M' + ' L'.join(f'{px:.1f} {py:.1f}' for px, py in seg)
    hair.append(f'<path d="{path}" fill="none" stroke="#4fb6dd" stroke-width="1.3" opacity="0.65"/>')
# 水平排针（发丝）
for i in range(26):
    y = -200 + i * 7.5
    x0 = 40 - abs(y + 70) * 0.28
    x1 = x0 + random.uniform(30, 70)
    if on_scalp(x0, y) or on_scalp(x1, y):
        hair.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
                    f'stroke="#6fc6e6" stroke-width="1.3" opacity="0.5"/>')
# 芯片
for _ in range(11):
    if not pts: break
    x, y = random.choice(pts); s = random.uniform(8, 14)
    rot = random.choice([0, 45])
    hair.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" '
                f'transform="rotate({rot} {x:.1f} {y:.1f})" fill="none" stroke="#8fe6ff" '
                f'stroke-width="1.5" opacity="0.8"/>')
# 发光点
for _ in range(60):
    if not pts: break
    x, y = random.choice(pts); r = random.uniform(2, 5.5)
    col = random.choice(['#7fe3ff', '#a9ecff', '#5fc8ea', '#eafcff'])
    hair.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{col}" opacity="0.95"/>')
HAIR = ''.join(hair)

svg = open(os.path.join(BASE, 'cover10_template.svg'), encoding='utf-8').read()
svg = svg.replace('__BRAIN_RING__', BRAIN).replace('__HAIR__', HAIR)
out = os.path.join(BASE, 'cover10.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
import cairosvg
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover10_hires.png'),
                 output_width=2480, output_height=3508)
cairosvg.svg2png(url=out, write_to=os.path.join(BASE, 'cover10_full.png'),
                 output_width=1240, output_height=1754)
print('wrote previews')
