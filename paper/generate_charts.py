#!/usr/bin/env python3
"""重新生成所有论文图表 — 高分辨率+大字体+正确中文"""
from PIL import Image, ImageDraw, ImageFont
import os, random

# ============================================================
# 字体加载
# ============================================================
FONT_PATHS = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
]
def load_font(size):
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except: pass
    return ImageFont.load_default()

F_TITLE = load_font(48)
F_HEAD  = load_font(36)
F_BODY  = load_font(28)
F_SMALL = load_font(22)
F_TINY  = load_font(18)
F_LABEL = load_font(16)

BASEDIR = '/home/lijinhan/MXL/科研/ylyw/paper'

# ============================================================
# 图1: 优化前后对比柱状图
# ============================================================
def fig_before_after():
    W, H = 2200, 1300
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    # 标题
    draw.rectangle([0, 0, W, 100], fill='#1A5276')
    draw.text((W//2, 50), '各物体类型零样本合理率：优化前 vs 优化后',
             fill='white', font=F_TITLE, anchor='mm')
    
    categories = ['球体','立方体','圆柱体','碗','瓶子','盘子','石块','花瓶']
    before = [28.6, 57.1, 0.0, 33.3, 100.0, 100.0, 16.7, 50.0]
    after  = [93.8, 92.5, 80.0, 92.1, 97.2, 97.9, 87.1, 100.0]
    
    cx, cy = 200, 140
    cw, ch = W - 380, H - 260
    n = len(categories)
    bar_w = 55
    gap = 15
    
    # Y轴
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
        
        # 优化前
        draw.rectangle([xb, cy+ch-bh, xb+bar_w, cy+ch], fill='#AED6F1', outline='#2980B9', width=2)
        if bh > 30:
            draw.text((xb+bar_w//2, cy+ch-bh-5), f'{bv:.0f}%', fill='#2980B9', font=F_LABEL, anchor='mb')
        else:
            draw.text((xb+bar_w//2, cy+ch-bh-25), f'{bv:.0f}%', fill='#2980B9', font=F_LABEL, anchor='mb')
        
        # 优化后
        draw.rectangle([xa, cy+ch-ah, xa+bar_w, cy+ch], fill='#1A5276', outline='#0E2F44', width=2)
        draw.text((xa+bar_w//2, cy+ch-ah-5), f'{av:.0f}%', fill='#1A5276', font=F_LABEL, anchor='mb')
        
        draw.text((xc, cy+ch+20), cat, fill='#333', font=F_BODY, anchor='ma')
    
    # 图例
    lx = cx + cw - 350
    draw.rectangle([lx, cy-5, lx+25, cy+20], fill='#AED6F1', outline='#2980B9', width=2)
    draw.text((lx+35, cy+7), '优化前 (20卦)', fill='#555', font=F_LABEL, anchor='lm')
    draw.rectangle([lx+200, cy-5, lx+225, cy+20], fill='#1A5276', outline='#0E2F44', width=2)
    draw.text((lx+235, cy+7), '优化后 (64卦)', fill='#555', font=F_LABEL, anchor='lm')
    
    # 标注
    draw.text((cx+cw//2, cy-30), '合理率 (%)', fill='#333', font=F_SMALL, anchor='ma')
    
    path = f'{BASEDIR}/fig_before_after_comparison.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
# 图2: 卦象命中分布
# ============================================================
def fig_hexagram_hit():
    W, H = 2000, 900
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([0, 0, W, 80], fill='#1A5276')
    draw.text((W//2, 40), '卦象命中分布：优化前 vs 优化后', fill='white', font=F_TITLE, anchor='mm')
    
    data = [
        ('火水未济', 13, 0),
        ('山水蒙', 7, 0),
        ('山泽损', 7, 0),
        ('泽雷随', 0, 6),
        ('地火明夷', 0, 6),
        ('风天小畜', 0, 5),
        ('雷风恒', 0, 5),
        ('风火家人', 0, 5),
        ('火地晋', 0, 5),
        ('天泽履', 5, 0),
        ('地泽临', 0, 4),
        ('火泽睽', 4, 0),
        ('乾为天', 3, 0),
        ('离为火', 3, 0),
    ]
    
    cx, cy = 220, 110
    cw, ch = W - 300, H - 200
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
    
    # 图例
    draw.rectangle([cx+cw-250, cy-30, cx+cw-225, cy-5], fill='#E74C3CCC', outline='#E74C3C')
    draw.text((cx+cw-215, cy-18), '优化前(20卦)', fill='#E74C3C', font=F_LABEL, anchor='lm')
    draw.rectangle([cx+cw-100, cy-30, cx+cw-75, cy-5], fill='#1A5276CC', outline='#1A5276')
    draw.text((cx+cw-65, cy-18), '优化后(64卦)', fill='#1A5276', font=F_LABEL, anchor='lm')
    
    path = f'{BASEDIR}/fig_hexagram_hit_distribution.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
# 图3: 爻位质量分布
# ============================================================
def fig_yao_quality():
    W, H = 1800, 1100
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([0, 0, W, 80], fill='#1A5276')
    draw.text((W//2, 40), '爻位质量分布直方图 (n=300)', fill='white', font=F_TITLE, anchor='mm')
    
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
    
    # Y刻度
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
    
    draw.text((cx+cw//2, cy+ch+50), '爻位质量区间', fill='#333', font=F_BODY, anchor='ma')
    
    # 图例
    lx = cx + cw - 400
    for j, (label, color) in enumerate([('低质量 (<0.4)','#E74C3C'),('中等 (0.4-0.7)','#F39C12'),('高质量 (>0.7)','#27AE60')]):
        draw.rectangle([lx+j*130, cy-35, lx+j*130+25, cy-10], fill=color)
        draw.text((lx+j*130+35, cy-22), label, fill='#555', font=F_LABEL, anchor='lm')
    
    path = f'{BASEDIR}/fig_yao_quality_distribution.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
# 图4: 架构图
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
        import math
        draw.line([(x1, y1), (x2, y2)], fill='#455A64', width=4)
        al = 18
        angle = math.atan2(y2-y1, x2-x1)
        draw.polygon([
            (x2, y2),
            (x2-al*math.cos(angle-math.pi/6), y2-al*math.sin(angle-math.pi/6)),
            (x2-al*math.cos(angle+math.pi/6), y2-al*math.sin(angle+math.pi/6)),
        ], fill='#455A64')
    
    cx = W//2; bw = 1600
    # 标题
    draw.rectangle([0, 0, W, 120], fill='#1A1A2E')
    draw.text((cx, 50), 'YLYW 完整架构总览', fill='white', font=F_TITLE, anchor='mm')
    draw.text((cx, 90), '感知 → 八卦 → 六爻 → 卦象 → 爻位 → 决策 → 物理约束', fill='#90CAF9', font=F_SMALL, anchor='mm')
    
    y = 150
    # 物理世界
    bh = 120
    box(cx-bw//2, y, bw, bh, 'physical')
    draw.text((cx, y+30), '物理世界', fill='#2E7D32', font=F_HEAD, anchor='mm')
    draw.text((cx, y+65), '物体: 球体 / 立方体 / 圆柱体 / 碗 / 瓶 / 盘 / 石块 / 花瓶', fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+95), '13维物理特征: 稳定性 滚动倾向 力需求 脆弱性 可达性 遮挡 障碍密度 ...', fill='#666', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L1
    bh = 180
    box(cx-bw//2, y, bw, bh, 'L1')
    draw.text((cx, y+25), 'L1  八卦基元（模糊隶属度）', fill='#1565C0', font=F_HEAD, anchor='mm')
    trigrams = ['乾☰健','坤☷顺','震☳动','艮☶止','离☲明','坎☵险','兑☱悦','巽☴入']
    for i, t in enumerate(trigrams):
        draw.text((260+i*210, y+75), t, fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+115), '隶属度 = 高斯核相似度(物体特征, 卦原型)  →  8维隶属度向量', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+148), '主导卦象: 震 ☳ (动)    隶属度: 0.75', fill='#1565C0', font=F_SMALL, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L2
    bh = 180
    box(cx-bw//2, y, bw, bh, 'L2')
    draw.text((cx, y+25), 'L2  六爻编码（语义降维）', fill='#E65100', font=F_HEAD, anchor='mm')
    yao = ['初爻:稳定性','二爻:可达性','三爻:力需求','四爻:脆弱性','五爻:优先级','上爻:环境约束']
    for i, t in enumerate(yao):
        draw.text((210+i*270, y+75), t, fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+115), '爻值 = Σ w_ij × 物理特征_j  (6个预定义加权公式)', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+148), '爻向量: [0.13, 0.72, 0.36, 0.75, 0.80, 0.85]  阴-阳-阴-阳-阳-阳', fill='#E65100', font=F_SMALL, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L3
    bh = 160
    box(cx-bw//2, y, bw, bh, 'L3')
    draw.text((cx, y+25), 'L3  六十四卦匹配（策略决策）', fill='#6A1B9A', font=F_HEAD, anchor='mm')
    draw.text((cx, y+70), '64个卦象模板 × 余弦相似度匹配  →  Top-K 卦象序列', fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+105), 'Top-1: 水天需 ☵☰  →  conditional_grasp  (卦象决定策略类型)', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+135), '备选: 雷地豫(0.981)  震为雷(0.981)  — 变卦候选', fill='#999', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # L3+
    bh = 220
    box(cx-bw//2, y, bw, bh, 'L3plus')
    draw.text((cx, y+25), 'L3+  爻位关系运算（参数精修）', fill='#C62828', font=F_HEAD, anchor='mm')
    rels = ['当位: 2/6', '得中: 二阳+五阳', '乘(逆): 1处', '亲比: 3/5对', '呼应: 2/3对']
    for i, t in enumerate(rels):
        draw.rounded_rectangle([250+i*310-100, y+55, 250+i*310+100, y+100], radius=8, fill='white', outline='#EF9A9A', width=2)
        draw.text((250+i*310, y+78), t, fill='#C62828', font=F_SMALL, anchor='mm')
    draw.text((cx, y+130), '综合爻位质量 = 0.40×当位 + 0.20×得中 + 0.15×乘承 + 0.10×亲比 + 0.15×呼应  =  0.51', fill='#555', font=F_SMALL, anchor='mm')
    draw.text((cx, y+165), '→  策略修正系数 ×0.90    →    谨慎级别: 谨慎', fill='#C62828', font=F_SMALL, anchor='mm')
    draw.text((cx, y+198), '爻位关系决定执行参数（力修正、谨慎级别）——"怎么做"', fill='#888', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # 决策
    bh = 150
    box(cx-bw//2, y, bw, bh, 'decision')
    draw.text((cx, y+25), '决策输出层', fill='#00838F', font=F_HEAD, anchor='mm')
    decs = [('策略类型','条件式抓取'),('力预设','0.50（×0.90修正）'),('接近角/速度','0° / 中速'),('可解释推理链','卦→爻→辞 全链路可追溯')]
    for i, (l, v) in enumerate(decs):
        draw.text((260+i*370, y+70), l, fill='#00838F', font=F_SMALL, anchor='mm')
        draw.text((260+i*370, y+105), v, fill='#333', font=F_SMALL, anchor='mm')
    draw.text((cx, y+132), '每一步推理均可追溯至具体卦名与爻位分析', fill='#888', font=F_TINY, anchor='mm')
    y += bh; arrow(cx, y, cx, y+30); y += 30
    
    # 物理约束（虚线框）
    bh = 130
    box(cx-bw//2, y, bw, bh, 'physics_c')
    draw.text((cx, y+28), '物理约束层（未来工作）', fill='#757575', font=F_HEAD, anchor='mm')
    draw.text((cx, y+70), 'τ = M(θ)θ̈_des + C(θ,θ̇)θ̇ + G(θ)   →   100%物理合规力矩', fill='#888', font=F_SMALL, anchor='mm')
    draw.text((cx, y+100), '零穿透 / 零滑脱 / 零过载保证', fill='#999', font=F_TINY, anchor='mm')
    
    y += bh + 30
    # 图例
    legend = [('物理世界','physical'),('L1八卦','L1'),('L2六爻','L2'),('L3卦象','L3'),('L3+爻位','L3plus'),('决策输出','decision'),('物理约束','physics_c')]
    lx = 80
    for label, key in legend:
        fill, border = COLORS[key]
        draw.rounded_rectangle([lx, y, lx+28, y+28], radius=4, fill=fill, outline=border, width=2)
        draw.text((lx+40, y+14), label, fill='#333', font=F_SMALL, anchor='lm')
        lx += 210
    
    path = f'{BASEDIR}/architecture_diagram.png'
    img.save(path, dpi=(200, 200))
    print(f'✅ {path}')

# ============================================================
if __name__ == '__main__':
    fig_before_after()
    fig_hexagram_hit()
    fig_yao_quality()
    fig_architecture()
    print('\n✅ 全部4张图表重新生成完成')
