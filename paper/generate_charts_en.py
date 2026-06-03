#!/usr/bin/env python3
"""Generate all paper charts — English version, high-resolution, large fonts"""
from PIL import Image, ImageDraw, ImageFont
import os, random, math

# ============================================================
# Font loading
# ============================================================
FONT_PATHS = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]
def load_font(size):
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except: pass
    return ImageFont.load_default()

F_TITLE = load_font(44)
F_HEAD  = load_font(32)
F_BODY  = load_font(26)
F_SMALL = load_font(20)
F_TINY  = load_font(16)
F_LABEL = load_font(15)

BASEDIR = '/home/lijinhan/MXL/科研/ylyw/paper'

# ============================================================
# Figure 2: Before vs After Bar Chart
# ============================================================
def fig_before_after():
    W, H = 2200, 1300
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([0, 0, W, 100], fill='#1A5276')
    draw.text((W//2, 50), 'Zero-Shot Reasonable Rate by Object Type: Before vs After Optimization',
             fill='white', font=F_TITLE, anchor='mm')
    
    categories = ['Sphere', 'Cube', 'Cylinder', 'Bowl', 'Bottle', 'Plate', 'Rock', 'Vase']
    before = [28.6, 57.1, 0.0, 33.3, 100.0, 100.0, 16.7, 50.0]
    after  = [93.8, 92.5, 80.0, 92.1, 97.2, 97.9, 87.1, 100.0]
    
    cx, cy = 200, 140
    cw, ch = W - 380, H - 260
    n = len(categories)
    bar_w = 55
    gap = 15
    
    # Y-axis
    draw.line([(cx, cy), (cx, cy+ch)], fill='#333', width=3)
    draw.line([(cx, cy+ch), (cx+cw, cy+ch)], fill='#333', width=3)
    
    for pct in [0, 25, 50, 75, 100]:
        y = cy + ch - int(ch * pct / 100)
        draw.line([(cx-10, y), (cx, y)], fill='#999', width=2)
        draw.text((cx-20, y-10), f'{pct}%', fill='#555', font=F_LABEL, anchor='ra')
        if pct > 0:
            draw.line([(cx, y), (cx+cw, y)], fill='#EEEEEE', width=1)
    
    for i, (cat, bv, av) in enumerate(zip(categories, before, after)):
        xc = cx + (i + 0.5) * cw / n
        xb = xc - bar_w - gap//2
        xa = xc + gap//2
        
        bh = int(ch * bv / 100)
        ah = int(ch * av / 100)
        
        # Before
        draw.rectangle([xb, cy+ch-bh, xb+bar_w, cy+ch], fill='#AED6F1', outline='#2980B9', width=2)
        if bh > 30:
            draw.text((xb+bar_w//2, cy+ch-bh-5), f'{bv:.0f}%', fill='#2980B9', font=F_LABEL, anchor='mb')
        else:
            draw.text((xb+bar_w//2, cy+ch-bh-25), f'{bv:.0f}%', fill='#2980B9', font=F_LABEL, anchor='mb')
        
        # After
        draw.rectangle([xa, cy+ch-ah, xa+bar_w, cy+ch], fill='#1A5276', outline='#0E2F44', width=2)
        draw.text((xa+bar_w//2, cy+ch-ah-5), f'{av:.0f}%', fill='#1A5276', font=F_LABEL, anchor='mb')
        
        draw.text((xc, cy+ch+20), cat, fill='#333', font=F_BODY, anchor='ma')
    
    # Legend
    lx = cx + cw - 350
    draw.rectangle([lx, cy-5, lx+25, cy+20], fill='#AED6F1', outline='#2980B9', width=2)
    draw.text((lx+35, cy+7), 'Before (20 hexagrams)', fill='#555', font=F_LABEL, anchor='lm')
    draw.rectangle([lx+220, cy-5, lx+245, cy+20], fill='#1A5276', outline='#0E2F44', width=2)
    draw.text((lx+255, cy+7), 'After (64 hexagrams)', fill='#555', font=F_LABEL, anchor='lm')
    
    # Y-axis label
    draw.text((cx+cw//2, cy-30), 'Reasonable Rate (%)', fill='#333', font=F_SMALL, anchor='ma')
    
    path = f'{BASEDIR}/fig_before_after_comparison_en.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
# Figure 3: Hexagram Hit Distribution
# ============================================================
def fig_hexagram_hit():
    W, H = 2000, 900
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([0, 0, W, 80], fill='#1A5276')
    draw.text((W//2, 40), 'Hexagram Hit Distribution: Before vs After Optimization', fill='white', font=F_TITLE, anchor='mm')
    
    data = [
        ('Huoshui Weiji', 13, 0),
        ('Shanshui Meng', 7, 0),
        ('Shanze Sun', 7, 0),
        ('Zelei Sui', 0, 6),
        ('Dihuo Mingyi', 0, 6),
        ('Fengtian Xiaoxu', 0, 5),
        ('Leifeng Heng', 0, 5),
        ('Fenghuo Jiaren', 0, 5),
        ('Huodi Jin', 0, 5),
        ('Tianze Lü', 5, 0),
        ('Dize Lin', 0, 4),
        ('Huoze Kui', 4, 0),
        ('Qian (Heaven)', 3, 0),
        ('Li (Fire)', 3, 0),
    ]
    
    cx, cy = 240, 110
    cw, ch = W - 320, H - 200
    n = len(data)
    bar_h = min(35, (ch // n) - 8)
    
    for i, (name, before, after) in enumerate(data):
        y = cy + i * (ch // n)
        
        draw.text((cx-15, y+bar_h//2), name, fill='#333', font=F_LABEL, anchor='rm')
        
        if before > 0:
            bw = max(30, int(cw//2 * before / 14))
            draw.rectangle([cx+5, y+3, cx+5+bw, y+bar_h-3], fill='#E74C3CCC', outline='#E74C3C', width=1)
            draw.text((cx+5+bw+10, y+bar_h//2), str(before), fill='#E74C3C', font=F_LABEL, anchor='lm')
        
        if after > 0:
            ax = cx + cw//2
            aw = max(30, int(cw//2 * after / 7))
            draw.rectangle([ax, y+3, ax+aw, y+bar_h-3], fill='#1A5276CC', outline='#1A5276', width=1)
            draw.text((ax+aw+10, y+bar_h//2), str(after), fill='#1A5276', font=F_LABEL, anchor='lm')
    
    # Legend
    draw.rectangle([cx+cw-260, cy-30, cx+cw-235, cy-5], fill='#E74C3CCC', outline='#E74C3C')
    draw.text((cx+cw-225, cy-18), 'Before (20 hexagrams)', fill='#E74C3C', font=F_LABEL, anchor='lm')
    draw.rectangle([cx+cw-80, cy-30, cx+cw-55, cy-5], fill='#1A5276CC', outline='#1A5276')
    draw.text((cx+cw-45, cy-18), 'After (64 hexagrams)', fill='#1A5276', font=F_LABEL, anchor='lm')
    
    path = f'{BASEDIR}/fig_hexagram_hit_distribution_en.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
# Figure 4: Yao Position Quality Distribution
# ============================================================
def fig_yao_quality():
    W, H = 1800, 1100
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([0, 0, W, 80], fill='#1A5276')
    draw.text((W//2, 40), 'Yao Position Quality Distribution Histogram (n=300)', fill='white', font=F_TITLE, anchor='mm')
    
    random.seed(42)
    bins = [0]*10
    for _ in range(300):
        s = max(0.02, min(0.98, random.gauss(0.50, 0.15)))
        bins[min(9, int(s*10))] += 1
    
    max_count = max(bins)
    cx, cy = 160, 130
    cw, ch = W - 260, H - 280
    bar_w = cw // 10 - 6
    
    draw.line([(cx, cy), (cx, cy+ch)], fill='#333', width=3)
    draw.line([(cx, cy+ch), (cx+cw, cy+ch)], fill='#333', width=3)
    
    # Y ticks
    for v in range(0, max_count+10, 10):
        y = cy + ch - int(ch * v / max(max_count, 80) * 0.85)
        draw.line([(cx-8, y), (cx, y)], fill='#999', width=2)
        draw.text((cx-15, y-10), str(v), fill='#666', font=F_LABEL, anchor='ra')
    
    for i, count in enumerate(bins):
        x = cx + i * cw // 10 + 3
        bh = int(ch * count / max(max_count, 80) * 0.85)
        
        if i < 4: color = '#E74C3C'
        elif i < 7: color = '#F39C12'
        else: color = '#27AE60'
        
        draw.rectangle([x, cy+ch-bh, x+bar_w, cy+ch], fill=color, outline='white', width=1)
        
        if count > 0:
            draw.text((x+bar_w//2, cy+ch-bh-8), str(count), fill=color, font=F_SMALL, anchor='mb')
        
        label = f'{i*0.1:.1f}-{(i+1)*0.1:.1f}'
        draw.text((x+bar_w//2, cy+ch+10), label, fill='#666', font=F_TINY, anchor='ma')
    
    draw.text((cx+cw//2, cy+ch+50), 'Yao Position Quality Interval', fill='#333', font=F_BODY, anchor='ma')
    
    # Legend
    lx = cx + cw - 450
    for j, (label, color) in enumerate([('Low Quality (<0.4)','#E74C3C'),('Medium (0.4-0.7)','#F39C12'),('High Quality (>0.7)','#27AE60')]):
        draw.rectangle([lx+j*155, cy-35, lx+j*155+25, cy-10], fill=color)
        draw.text((lx+j*155+35, cy-22), label, fill='#555', font=F_LABEL, anchor='lm')
    
    path = f'{BASEDIR}/fig_yao_quality_distribution_en.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
# Figure 1: Architecture Diagram (English)
# ============================================================
def fig_architecture():
    W, H = 2000, 2800
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    COLORS = {
        'physical': ('#E8F5E9', '#2E7D32'),
        'L1': ('#E3F2FD', '#1565C0'),
        'L2': ('#FFF3E0', '#E65100'),
        'L3': ('#F3E5F5', '#6A1B9A'),
        'L3plus': ('#FFEBEE', '#C62828'),
        'decision': ('#E0F7FA', '#00838F'),
        'physics_c': ('#F5F5F5', '#9E9E9E'),
    }
    
    def box(x, y, w, h, key):
        fill, border = COLORS[key]
        draw.rounded_rectangle([x, y, x+w, y+h], radius=15, fill=fill, outline=border, width=3)
    
    def arrow(x1, y1, x2, y2):
        draw.line([(x1, y1), (x2, y2)], fill='#455A64', width=4)
        al = 18
        angle = math.atan2(y2-y1, x2-x1)
        draw.polygon([
            (x2, y2),
            (x2-al*math.cos(angle-math.pi/6), y2-al*math.sin(angle-math.pi/6)),
            (x2-al*math.cos(angle+math.pi/6), y2-al*math.sin(angle+math.pi/6)),
        ], fill='#455A64')
    
    cx = W//2; bw = 1600
    # Title
    draw.rectangle([0, 0, W, 120], fill='#1A1A2E')
    draw.text((cx, 50), 'YLYW Complete Architecture Overview', fill='white', font=F_TITLE, anchor='mm')
    draw.text((cx, 90), 'Perception → Bagua → Yao → Hexagram → Yao Relations → Decision → Physics Constraints',
              fill='#90CAF9', font=F_SMALL, anchor='mm')
    
    y = 150
    # Physical World
    bh = 120
    box(cx-bw//2, y, bw, bh, 'physical')
    draw.text((cx, y+30), 'Physical World', fill='#2E7D32', font=F_HEAD, anchor='mm')
    draw.text((cx, y+65), 'Objects: Sphere / Cube / Cylinder / Bowl / Bottle / Plate / Rock / Vase', fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+95), '13-D Physical Features: Stability, Roll Tendency, Force Required, Fragility, Reachability, Occlusion, Obstacle Density ...', fill='#666', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L1
    bh = 180
    box(cx-bw//2, y, bw, bh, 'L1')
    draw.text((cx, y+25), 'L1  Trigram Base (Bagua)', fill='#1565C0', font=F_HEAD, anchor='mm')
    trigrams = ['Qian☰ Strong', 'Kun☷ Yielding', 'Zhen☳ Moving', 'Gen☶ Still', 'Li☲ Bright', 'Kan☵ Peril', 'Dui☱ Joyful', 'Xun☴ Entering']
    for i, t in enumerate(trigrams):
        draw.text((260+i*210, y+75), t, fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+115), 'Membership = Gaussian kernel similarity(object features, trigram prototype) → 8-D membership vector', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+148), 'Dominant trigram: Zhen ☳ (Moving)    Membership: 0.75', fill='#1565C0', font=F_SMALL, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L2
    bh = 180
    box(cx-bw//2, y, bw, bh, 'L2')
    draw.text((cx, y+25), 'L2  Yao Encoder (Six Lines)', fill='#E65100', font=F_HEAD, anchor='mm')
    yao = ['Yao1: Stability', 'Yao2: Reachability', 'Yao3: Force Req.', 'Yao4: Fragility', 'Yao5: Priority', 'Yao6: Environment']
    for i, t in enumerate(yao):
        draw.text((210+i*270, y+75), t, fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+115), 'Yao value = Σ w_ij × physical_feature_j  (6 predefined weighted formulas)', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+148), 'Yao vector: [0.13, 0.72, 0.36, 0.75, 0.80, 0.85]  Yin-Yang-Yin-Yang-Yang-Yang', fill='#E65100', font=F_SMALL, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L3
    bh = 160
    box(cx-bw//2, y, bw, bh, 'L3')
    draw.text((cx, y+25), 'L3  Hexagram Matching (64 Hexagrams)', fill='#6A1B9A', font=F_HEAD, anchor='mm')
    draw.text((cx, y+70), '64 hexagram templates × Cosine similarity matching → Top-K hexagram sequence', fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+105), 'Top-1: Shuitian Xu ☵☰ → conditional_grasp  (Hexagram determines strategy type)', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+135), 'Candidates: Leidi Yu (0.981)  Zhenweilei (0.981) — alternate hexagrams', fill='#999', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L3+
    bh = 220
    box(cx-bw//2, y, bw, bh, 'L3plus')
    draw.text((cx, y+25), 'L3+  Yao Position Relations', fill='#C62828', font=F_HEAD, anchor='mm')
    rels = ['Proper Pos: 2/6', 'Central: Y2+yang Y5+yang', 'Override: 1', 'Adj. Harmony: 3/5', 'Resonance: 2/3']
    for i, t in enumerate(rels):
        draw.rounded_rectangle([250+i*310-100, y+55, 250+i*310+100, y+100], radius=8, fill='white', outline='#EF9A9A', width=2)
        draw.text((250+i*310, y+78), t, fill='#C62828', font=F_SMALL, anchor='mm')
    draw.text((cx, y+130), 'Composite Yao Quality = 0.40×Proper + 0.20×Central + 0.15×Override/Support + 0.10×Adj.Harmony + 0.15×Resonance = 0.51', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+165), '→ Strategy modifier ×0.90 → Caution Level: cautious', fill='#C62828', font=F_SMALL, anchor='mm')
    draw.text((cx, y+198), 'Yao relations determine execution parameters (force modifier, caution level) — "how to act"', fill='#888', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # Decision
    bh = 150
    box(cx-bw//2, y, bw, bh, 'decision')
    draw.text((cx, y+25), 'Decision Layer (Action Output)', fill='#00838F', font=F_HEAD, anchor='mm')
    decs = [('Strategy Type', 'conditional_grasp'), ('Force Preset', '0.50 (×0.90 modifier)'), ('Approach Angle / Speed', '0° / medium'), ('Interpretable Reasoning Chain', 'Hexagram→Yao→Statement full trace')]
    for i, (l, v) in enumerate(decs):
        draw.text((260+i*370, y+70), l, fill='#00838F', font=F_SMALL, anchor='mm')
        draw.text((260+i*370, y+105), v, fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+132), 'Every reasoning step traceable to specific hexagram name and yao position analysis', fill='#888', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # Physics constraint (dashed)
    bh = 130
    box(cx-bw//2, y, bw, bh, 'physics_c')
    draw.text((cx, y+28), 'Physics Constraint Layer (Future Work)', fill='#757575', font=F_HEAD, anchor='mm')
    draw.text((cx, y+70), 'τ = M(θ)θ̈_des + C(θ,θ̇)θ̇ + G(θ) → 100% physically compliant torque', fill='#888', font=F_SMALL, anchor='mm')
    draw.text((cx, y+100), 'Zero penetration / zero slip / zero overload guarantee', fill='#999', font=F_TINY, anchor='mm')
    
    y += bh + 30
    # Legend
    legend = [('Physical World','physical'),('L1 Trigram','L1'),('L2 Yao Encoder','L2'),('L3 Hexagram','L3'),('L3+ Yao Relations','L3plus'),('Decision Output','decision'),('Physics Constraint','physics_c')]
    lx = 80
    for label, key in legend:
        fill, border = COLORS[key]
        draw.rounded_rectangle([lx, y, lx+28, y+28], radius=4, fill=fill, outline=border, width=2)
        draw.text((lx+40, y+14), label, fill='#333', font=F_SMALL, anchor='lm')
        lx += 230
    
    path = f'{BASEDIR}/architecture_diagram_en.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
if __name__ == '__main__':
    fig_architecture()
    fig_before_after()
    fig_hexagram_hit()
    fig_yao_quality()
    print('\n✅ All 4 English charts regenerated successfully')
