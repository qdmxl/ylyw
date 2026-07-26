#!/usr/bin/env python3
"""Part 1: Generate all figures for YLYW paper"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
OUT = "/home/lijinhan/MXL/科研/ylyw/figures"
os.makedirs(OUT, exist_ok=True)

def font(size=14):
    return ImageFont.truetype(FONT, size)

def rounded_box(draw, xy, fill, r=8, outline=None, width=1):
    x1,y1,x2,y2 = xy
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

def arrow(draw, x1,y1,x2,y2, color=(100,100,100)):
    draw.line([(x1,y1),(x2,y2)], fill=color, width=2)
    # arrowhead
    mx,my = (x1+x2)//2, (y1+y2)//2
    draw.polygon([(x2,y2), (x2-8,y2-4), (x2-8,y2+4)], fill=color)

# ─── Figure 1: System Architecture ───
def fig1_architecture():
    w,h = 900, 650
    img = Image.new('RGB', (w,h), '#FAFAFA')
    draw = ImageDraw.Draw(img)
    f14 = font(14)
    f16 = font(16)
    f12 = font(12)
    
    # Layer 1: English Interface
    y0 = 30
    rounded_box(draw, (50,y0,850,y0+100), '#E3F2FD', outline='#1565C0', width=2)
    draw.text((60,y0+10), "第一层：英文接口适配层 (Interface Adapter)", fill='#1565C0', font=f16)
    draw.text((80,y0+40), "ALFWorld 环境 ↔ 英文正则解析 → 结构化信息 → ChineseBridge 英→汉翻译", fill='#333', font=f14)
    draw.text((80,y0+65), "提取: 位置/容器/物体/工序/动作结果  |  正则: arrive at / pick up / put in / clean/heat/cool", fill='#555', font=f12)
    
    # Arrow
    arrow(draw, 450, 130, 450, 160, '#1565C0')
    
    # Layer 2: Hanzi Semantic Layer
    y1 = 165
    rounded_box(draw, (50,y1,850,y1+200), '#FFF3E0', outline='#E65100', width=2)
    draw.text((60,y1+10), "第二层：汉字语义层 (Hanzi YLYW Inference)", fill='#E65100', font=f16)
    
    # Sub-components
    rounded_box(draw, (70,y1+45,380,y1+150), '#FFECB3', outline='#E65100')
    draw.text((85,y1+55), "汉字易理推理引擎", fill='#BF360C', font=f14)
    draw.text((85,y1+80), "HanziEngine.char(汉字)", fill='#333', font=f12)
    draw.text((85,y1+100), "部首分解 → 卦象模糊映射", fill='#555', font=f12)
    draw.text((85,y1+120), "→ 乘承比应 → 六爻 → 64卦", fill='#555', font=f12)
    
    rounded_box(draw, (420,y1+45,830,y1+150), '#FFECB3', outline='#E65100')
    draw.text((435,y1+55), "万物类象知识库", fill='#BF360C', font=f14)
    draw.text((435,y1+80), "GuaKnowledgeBase (单例)", fill='#333', font=f12)
    draw.text((435,y1+100), "先验156条 + 运行时学习85条", fill='#555', font=f12)
    draw.text((435,y1+120), "LRU缓存 @lru_cache 4096", fill='#555', font=f12)
    
    draw.text((80,y1+165), "→ GuaReceptacle(汉字名+卦象+六爻)  |  GuaObject(汉字名+卦象+六爻)  |  情境卦象(64卦匹配)", fill='#E65100', font=f12)
    
    # Arrow
    arrow(draw, 450, 365, 450, 395, '#2E7D32')
    
    # Layer 3: Decision Layer
    y2 = 400
    rounded_box(draw, (50,y2,850,y2+150), '#E8F5E9', outline='#2E7D32', width=2)
    draw.text((60,y2+10), "第三层：决策推理层 (YLYW Decision Engine)", fill='#2E7D32', font=f16)
    
    rounded_box(draw, (70,y2+50,380,y2+135), '#C8E6C9', outline='#2E7D32')
    draw.text((85,y2+60), "YLYW评分器", fill='#1B5E20', font=f14)
    draw.text((85,y2+85), "六爻编码(6维) → 64卦匹配", fill='#333', font=f12)
    draw.text((85,y2+105), "→ 吉凶评分 → 选最高分", fill='#555', font=f12)
    
    rounded_box(draw, (420,y2+50,830,y2+135), '#C8E6C9', outline='#2E7D32')
    draw.text((435,y2+60), "策略池 (12+种策略)", fill='#1B5E20', font=f14)
    draw.text((435,y2+85), "go_to / pickup / put / open / close", fill='#333', font=f12)
    draw.text((435,y2+105), "heat / cool / clean / examine / search", fill='#555', font=f12)
    
    # Title
    draw.text((280,5), "YLYW 系统架构图", fill='#222', font=ImageFont.truetype(FONT, 20))
    
    path = os.path.join(OUT, "fig1_architecture.png")
    img.save(path)
    print(f"✅ {path} ({os.path.getsize(path)} bytes)")
    return path

fig1_architecture()
