#!/usr/bin/env python3
"""Figure 2: Hanzi-to-Hexagram inference pipeline"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
OUT = "/home/lijinhan/MXL/科研/ylyw/figures"
os.makedirs(OUT, exist_ok=True)

def font(size=14): return ImageFont.truetype(FONT, size)

def box(draw, xy, fill, r=6, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

def arrow(draw, x1,y1,x2,y2, color='#555'):
    draw.line([(x1,y1),(x2,y2)], fill=color, width=2)
    draw.polygon([(x2,y2), (x2-10,y2-5), (x2-10,y2+5)], fill=color)

def fig2_pipeline():
    w,h = 850, 700
    img = Image.new('RGB', (w,h), '#FAFAFA')
    draw = ImageDraw.Draw(img)
    f14 = font(14); f16 = font(16); f12 = font(12); f18 = font(18)
    
    draw.text((280,5), "汉字→卦象推理链路", fill='#222', font=f18)
    
    # Step boxes
    steps = [
        (100,40,  340,95,   '#E3F2FD', '#1565C0', '输入汉字', '"橱柜"、"苹果"、"台灯"'),
        (460,40,  700,95,   '#E8F5E9', '#2E7D32', '英文转汉字', 'ChineseBridge 映射表'),
        (280,125, 560,185,  '#FFF3E0', '#E65100', '部首分解', 'radical_fuzzy_base.json'),
        (100,215, 340,280,  '#FCE4EC', '#C62828', '卦象模糊映射', '部首→8维隶属度'),
        (460,215, 700,280,  '#F3E5F5', '#6A1B9A', '乘承比应推理', '字间语义关系'),
        (280,310, 560,375,  '#E0F7FA', '#00838F', '六爻编码 (6维)', 'Y → [y₁...y₆]'),
        (100,405, 360,470,  '#FFF8E1', '#F57F17', '64卦模板匹配', '余弦相似度'),
        (440,405, 700,470,  '#E8F5E9', '#2E7D32', '知识库回退', '先验/学习查询'),
        (280,500, 560,560,  '#F5F5F5', '#616161', '最终卦象', '主导卦名+隶属度向量'),
    ]
    
    for x1,y1,x2,y2,fill,outline,title,sub in steps:
        box(draw, (x1,y1,x2,y2), fill, outline=outline, width=2)
        draw.text((x1+10,y1+8), title, fill=outline, font=f16)
        draw.text((x1+10,y1+36), sub, fill='#555', font=f12)
    
    # arrows
    arrow(draw, 340, 68,  460, 68)   # input→translate
    arrow(draw, 490, 130, 490, 185)  # step→dir
    arrow(draw, 340, 248, 460, 248)  # fuzzy→cheng
    arrow(draw, 490, 280, 490, 310)  # cheng→yao
    arrow(draw, 360, 438, 440, 438)  # match→kb
    arrow(draw, 420, 470, 420, 500)  # result→final
    
    # vertical flows
    arrow(draw, 150, 95,  150, 215)
    arrow(draw, 150, 280, 280, 362)
    arrow(draw, 150, 362, 100, 405)
    
    arrow(draw, 580, 95,  580, 215)
    arrow(draw, 580, 280, 560, 362)
    arrow(draw, 580, 362, 700, 405)
    arrow(draw, 700, 438, 560, 530)
    
    # info box
    box(draw, (80,590,770,670), '#F5F5F5', outline='#9E9E9E')
    draw.text((100,600), "完整推理链：", fill='#333', font=f14)
    draw.text((100,622), "汉字 → char() → 部首分解 → 卦象模糊映射 → 乘承比应 → 六爻编码 → 64卦匹配", fill='#555', font=f12)
    draw.text((100,644), "回退链路: char()失败→word()→部首推理→知识库查询→默认坤卦", fill='#888', font=f12)
    
    path = os.path.join(OUT, "fig2_pipeline.png")
    img.save(path)
    print(f"✅ {path} ({os.path.getsize(path)} bytes)")

fig2_pipeline()
