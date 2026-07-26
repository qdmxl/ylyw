#!/usr/bin/env python3
"""Figure 3: YLYW Scoring & Decision Process"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
OUT = "/home/lijinhan/MXL/科研/ylyw/figures"
os.makedirs(OUT, exist_ok=True)

def fnt(size=14): return ImageFont.truetype(FONT, size)

def box(draw, xy, fill, r=8, outline=None, w=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=w)

def arr(draw, x1,y1,x2,y2, c='#555'):
    draw.line([(x1,y1),(x2,y2)], fill=c, width=2)
    draw.polygon([(x2,y2), (x2-10,y2-5), (x2-10,y2+5)], fill=c)

def fig3_scoring():
    w,h = 880, 720
    img = Image.new('RGB', (w,h), '#FAFAFA')
    draw = ImageDraw.Draw(img)
    f14=fnt(14); f16=fnt(16); f12=fnt(12); f18=fnt(18); f11=fnt(11); f13=fnt(13)
    
    draw.text((310,5), "YLYW 决策推理流程", fill='#222', font=f18)
    
    # 1. Goal Parse
    box(draw, (300,40,580,95), '#E3F2FD', outline='#1565C0', w=2)
    draw.text((315,50), "任务目标解析", fill='#1565C0', font=f16)
    draw.text((315,73), "GoalParser: 目标物体/容器/工序", fill='#333', font=f12)
    
    arr(draw, 440,95, 440,125)
    
    # 2. Strategy Pool
    box(draw, (100,128,780,195), '#FFF3E0', outline='#E65100', w=2)
    draw.text((115,138), "策略池 → 候选动作集", fill='#E65100', font=f16)
    draw.text((115,163), "12+策略: go_to  pickup  put  open  close  heat  cool  clean  examine  search  look", fill='#333', font=f12)
    
    arr(draw, 440,195, 440,225)
    
    # 3. For each candidate
    box(draw, (250,228,630,283), '#FCE4EC', outline='#C62828', w=2)
    draw.text((265,238), "对每个候选动作 a ∈ A", fill='#C62828', font=f16)
    draw.text((265,260), "计算六爻编码 Y(a) = [y₁ ... y₆]", fill='#333', font=f12)
    
    # 4. Six Yao detail
    box(draw, (60,310,400,410), '#F3E5F5', outline='#6A1B9A', w=2)
    draw.text((75,318), "六爻评分向量", fill='#6A1B9A', font=f16)
    draws = [
        ("y₁(初爻) 目标差距减少", "σ(0.05+0.90×goal_progress)"),
        ("y₂(二爻) 持有连续性", "0.85/0.25/0.50"),
        ("y₃(三爻) 过程推进", "0.90/0.10/0.50"),
        ("y₄(四爻) 容器可用性", "0.85/0.15/0.50"),
        ("y₅(五爻) 目标关联", "0.90/0.65/0.20"),
        ("y₆(上爻) 新颖性vs失败", "σ(0.50-0.40×fail)"),
    ]
    dy = 340
    for label, val in draws:
        draw.text((85,dy), label, fill='#333', font=f12)
        draw.text((330,dy), val, fill='#888', font=f11)
        dy += 22
    
    # 5. 64 Hexagram match
    box(draw, (460,310,780,380), '#E0F7FA', outline='#00838F', w=2)
    draw.text((475,318), "64卦模板匹配", fill='#00838F', font=f16)
    draw.text((475,345), "Y(a) · H̃ᵢ", fill='#333', font=f14)
    draw.text((475,368), "cos* = max sim(Y(a), Hᵢ)", fill='#555', font=f12)
    
    arr(draw, 400,360, 460,345)
    
    arr(draw, 440,410, 440,440)
    
    # 6. Score computation
    box(draw, (200,443,680,510), '#E8F5E9', outline='#2E7D32', w=2)
    draw.text((215,453), "最终评分计算", fill='#2E7D32', font=f16)
    draw.text((215,478), "score(a) = linear(a) × f(H*) × (0.75 + 0.25 × cos* × aff(a))", fill='#333', font=f13)
    
    arr(draw, 440,510, 440,545)
    
    # 7. Select & Execute
    box(draw, (280,548,600,610), '#FFF8E1', outline='#F57F17', w=2)
    draw.text((300,558), "选最高分动作", fill='#F57F17', font=f16)
    draw.text((300,582), "a* = argmax score(a)", fill='#333', font=f14)
    
    arr(draw, 440,610, 440,645)
    
    # 8. Execute
    box(draw, (340,648,540,695), '#E8EAF6', outline='#3F51B5', w=2)
    draw.text((365,660), "执行动作", fill='#3F51B5', font=f16)
    draw.text((365,678), "更新世界状态", fill='#555', font=f12)
    
    path = os.path.join(OUT, "fig3_scoring.png")
    img.save(path)
    print(f"✅ {path} ({os.path.getsize(path)} bytes)")

fig3_scoring()
