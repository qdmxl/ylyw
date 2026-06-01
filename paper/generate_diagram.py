#!/usr/bin/env python3
"""生成YLYW架构图 — PNG图片"""
from PIL import Image, ImageDraw, ImageFont
import os

W = 1200
H = 1600
img = Image.new('RGB', (W, H), 'white')
draw = ImageDraw.Draw(img)

# 尝试加载中文字体
font_paths = [
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]
font_title = None
font_body = None
font_small = None
for fp in font_paths:
    if os.path.exists(fp):
        try:
            font_title = ImageFont.truetype(fp, 28)
            font_body = ImageFont.truetype(fp, 20)
            font_small = ImageFont.truetype(fp, 16)
            font_tiny = ImageFont.truetype(fp, 13)
            break
        except:
            continue

if font_body is None:
    font_title = ImageFont.load_default()
    font_body = font_title
    font_small = font_title
    font_tiny = font_title

# 颜色
COLOR_BG = '#FFFFFF'
COLOR_TITLE = '#1A1A2E'
COLOR_BOX_FILL = {
    'physical': '#E8F5E9',
    'L1': '#E3F2FD',
    'L2': '#FFF3E0',
    'L3': '#F3E5F5',
    'L3plus': '#FFEBEE',
    'decision': '#E0F7FA',
    'physics_constraint': '#F5F5F5',
}
COLOR_BOX_BORDER = {
    'physical': '#2E7D32',
    'L1': '#1565C0',
    'L2': '#E65100',
    'L3': '#6A1B9A',
    'L3plus': '#C62828',
    'decision': '#00838F',
    'physics_constraint': '#9E9E9E',
}
COLOR_ARROW = '#455A64'

def draw_rounded_box(draw, x, y, w, h, fill, border, radius=12):
    """画圆角矩形"""
    draw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=fill, outline=border, width=2)

def draw_arrow(draw, x1, y1, x2, y2, color=COLOR_ARROW):
    """画箭头"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    # 箭头尖
    import math
    angle = math.atan2(y2-y1, x2-x1)
    arrow_len = 12
    draw.polygon([
        (x2, y2),
        (x2 - arrow_len*math.cos(angle-math.pi/6), y2 - arrow_len*math.sin(angle-math.pi/6)),
        (x2 - arrow_len*math.cos(angle+math.pi/6), y2 - arrow_len*math.sin(angle+math.pi/6)),
    ], fill=color)

# ============================================================
#  标题
# ============================================================
draw.rectangle([0, 0, W, 80], fill=COLOR_TITLE)
draw.text((W//2, 20), 'YLYW 完整架构总览', fill='white', font=font_title, anchor='ma')
draw.text((W//2, 58), '感知→八卦→六爻→卦象→爻位→决策→物理', fill='#90CAF9', font=font_small, anchor='ma')

# ============================================================
#  物理世界层
# ============================================================
y = 100
box_w = 1000
box_h = 90
cx = W//2
draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['physical'], COLOR_BOX_BORDER['physical'])
draw.text((cx, y+15), '物理世界', fill='#2E7D32', font=font_body, anchor='ma')
draw.text((cx, y+45), '物体: 球体/立方体/圆柱体/碗/瓶/盘/石块/花瓶', fill='#333', font=font_small, anchor='ma')
draw.text((cx, y+68), '13维物理特征: 稳定性 滚动倾向 力需求 脆弱性 可达性 遮挡 ...', fill='#666', font=font_tiny, anchor='ma')

y += box_h
draw_arrow(draw, cx, y, cx, y+20)
y += 20

# ============================================================
#  L1 八卦基元
# ============================================================
box_h = 130
draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['L1'], COLOR_BOX_BORDER['L1'])
draw.text((cx, y+15), 'L1  八卦基元 (Trigram Base)', fill='#1565C0', font=font_body, anchor='ma')
# 八卦图标行
trigrams = ['乾 ☰ 健', '坤 ☷ 顺', '震 ☳ 动', '艮 ☶ 止', '离 ☲ 明', '坎 ☵ 险', '兑 ☱ 悦', '巽 ☴ 入']
for i, t in enumerate(trigrams):
    tx = 190 + i * 105
    draw.text((tx, y+55), t, fill='#333', font=font_small, anchor='ma')
draw.text((cx, y+85), '隶属度 = 高斯核相似度(物体特征, 卦原型) → 8维隶属度向量', fill='#555', font=font_tiny, anchor='ma')
draw.text((cx, y+108), '主导卦象: 震 ☳ (动)  隶属度: 0.75', fill='#1565C0', font=font_tiny, anchor='ma')

y += box_h
draw_arrow(draw, cx, y, cx, y+20)
y += 20

# ============================================================
#  L2 六爻编码
# ============================================================
box_h = 130
draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['L2'], COLOR_BOX_BORDER['L2'])
draw.text((cx, y+15), 'L2  六爻编码 (Yao Encoder)', fill='#E65100', font=font_body, anchor='ma')
yao_labels = ['初爻 稳定性', '二爻 可达性', '三爻 力需求', '四爻 脆弱性', '五爻 优先级', '上爻 环境约束']
for i, label in enumerate(yao_labels):
    tx = 170 + i * 155
    draw.text((tx, y+55), label, fill='#333', font=font_small, anchor='ma')
draw.text((cx, y+85), '爻值 = Σ w_ij × 物理特征_j  (6个预定义加权公式)', fill='#555', font=font_tiny, anchor='ma')
draw.text((cx, y+108), '爻向量: [0.13, 0.72, 0.36, 0.75, 0.80, 0.85]  阴-阳-阴-阳-阳-阳', fill='#E65100', font=font_tiny, anchor='ma')

y += box_h
draw_arrow(draw, cx, y, cx, y+20)
y += 20

# ============================================================
#  L3 卦象匹配
# ============================================================
box_h = 120
draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['L3'], COLOR_BOX_BORDER['L3'])
draw.text((cx, y+15), 'L3  六十四卦匹配 (Hexagram Matching)', fill='#6A1B9A', font=font_body, anchor='ma')
draw.text((cx, y+48), '42个卦象模板 × 余弦相似度匹配 → Top-K 卦象序列', fill='#333', font=font_small, anchor='ma')
draw.text((cx, y+75), 'Top-1: 水天需 ☵☰ → conditional_grasp  (卦象决定策略类型)', fill='#555', font=font_tiny, anchor='ma')
draw.text((cx, y+98), '备选: 雷地豫(0.981)  震为雷(0.981)  — 变卦候选', fill='#999', font=font_tiny, anchor='ma')

y += box_h
draw_arrow(draw, cx, y, cx, y+20)
y += 20

# ============================================================
#  L3+ 爻位关系
# ============================================================
box_h = 170
draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['L3plus'], COLOR_BOX_BORDER['L3plus'])
draw.text((cx, y+15), 'L3+  爻位关系运算 (Yao Relations)', fill='#C62828', font=font_body, anchor='ma')

relations = [
    ('当位 1/6', '得中 二阳五阳', '乘(逆) 1处', '亲比 2/5', '呼应 2/3'),
]
for i, col in enumerate(relations[0]):
    tx = 200 + i * 200
    draw.rounded_rectangle([tx-85, y+40, tx+85, y+80], radius=6, fill='white', outline='#EF9A9A', width=1)
    draw.text((tx, y+60), col, fill='#C62828', font=font_small, anchor='ma')

draw.text((cx, y+100), '综合爻位质量 = 0.40×当位 + 0.20×得中 + 0.15×乘承 + 0.10×亲比 + 0.15×呼应 = 0.51', fill='#555', font=font_tiny, anchor='ma')
draw.text((cx, y+125), '→ 策略修正系数 ×0.90  →  谨慎级别: cautious', fill='#C62828', font=font_small, anchor='ma')
draw.text((cx, y+150), '爻位关系决定执行参数（力修正、谨慎级别）', fill='#888', font=font_tiny, anchor='ma')

y += box_h
draw_arrow(draw, cx, y, cx, y+20)
y += 20

# ============================================================
#  决策层
# ============================================================
box_h = 115
draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['decision'], COLOR_BOX_BORDER['decision'])
draw.text((cx, y+15), '决策层  (Action Output)', fill='#00838F', font=font_body, anchor='ma')

decisions = [
    ('策略类型', 'conditional_grasp'),
    ('力预设', '0.50 (×0.90修正)'),
    ('接近角 / 速度', '0° / medium'),
    ('可解释推理链', '卦→爻→辞 全追溯'),
]
for i, (label, val) in enumerate(decisions):
    lx = 180 + i * 230
    draw.text((lx, y+50), f'{label}', fill='#00838F', font=font_small, anchor='ma')
    draw.text((lx, y+78), f'{val}', fill='#333', font=font_small, anchor='ma')
draw.text((cx, y+100), '每一步推理均可追溯至具体卦名与爻位分析', fill='#888', font=font_tiny, anchor='ma')

y += box_h
draw_arrow(draw, cx, y, cx, y+20)
y += 20

# ============================================================
#  物理约束层（虚线框）
# ============================================================
box_h = 95
dash_pattern = 5
for dx in range(0, box_w, dash_pattern*2):
    draw.line([(cx-box_w//2+dx, y), (cx-box_w//2+dx+dash_pattern, y)], fill=COLOR_BOX_BORDER['physics_constraint'], width=1)
    draw.line([(cx-box_w//2+dx, y+box_h), (cx-box_w//2+dx+dash_pattern, y+box_h)], fill=COLOR_BOX_BORDER['physics_constraint'], width=1)
    draw.line([(cx-box_w//2, y+dx), (cx-box_w//2, y+dx+dash_pattern)], fill=COLOR_BOX_BORDER['physics_constraint'], width=1)
    draw.line([(cx+box_w//2, y+dx), (cx+box_w//2, y+dx+dash_pattern)], fill=COLOR_BOX_BORDER['physics_constraint'], width=1)

draw_rounded_box(draw, cx-box_w//2, y, box_w, box_h, COLOR_BOX_FILL['physics_constraint'], COLOR_BOX_BORDER['physics_constraint'])
draw.text((cx, y+20), '物理约束层 (Physics Constraint — 未来工作)', fill='#757575', font=font_body, anchor='ma')
draw.text((cx, y+55), 'τ = M(θ)θ̈_des + C(θ,θ̇)θ̇ + G(θ)  →  100%物理合规力矩', fill='#888', font=font_small, anchor='ma')
draw.text((cx, y+78), '零穿透 / 零滑脱 / 零过载保证', fill='#999', font=font_tiny, anchor='ma')

y += box_h + 30

# ============================================================
#  图例
# ============================================================
legend_items = [
    ('物理世界', COLOR_BOX_FILL['physical'], COLOR_BOX_BORDER['physical']),
    ('L1 八卦基元', COLOR_BOX_FILL['L1'], COLOR_BOX_BORDER['L1']),
    ('L2 六爻编码', COLOR_BOX_FILL['L2'], COLOR_BOX_BORDER['L2']),
    ('L3 卦象匹配', COLOR_BOX_FILL['L3'], COLOR_BOX_BORDER['L3']),
    ('L3+ 爻位关系', COLOR_BOX_FILL['L3plus'], COLOR_BOX_BORDER['L3plus']),
    ('决策输出', COLOR_BOX_FILL['decision'], COLOR_BOX_BORDER['decision']),
]
lx = 100
for label, fill, border in legend_items:
    draw.rounded_rectangle([lx, y, lx+20, y+20], radius=3, fill=fill, outline=border, width=1)
    draw.text((lx+30, y+10), label, fill='#333', font=font_small, anchor='lm')
    lx += 180

out_path = '/home/lijinhan/MXL/科研/ylyw/paper/architecture_diagram.png'
img.save(out_path)
print(f'✅ Architecture diagram saved: {out_path}')
print(f'   Size: {W}x{H}')
