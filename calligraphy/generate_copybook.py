#!/usr/bin/env python3
"""
字帖生成器 — 用系统楷体字体渲染 + 从网络下载真实字帖

两种模式：
1. 字体渲染：用 Pillow + AR PL UKai CN 楷体渲染汉字
2. 在线字帖：从书法字典网下载真实字帖图片（备用）
"""

import os, sys, io, hashlib
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTDIR = Path(__file__).parent / 'input' / 'copybook'
OUTDIR.mkdir(parents=True, exist_ok=True)


def render_char(char: str, font_path: str = None,
                size: int = 256, output: str = None) -> np.ndarray:
    """
    用楷体渲染单个汉字为字帖图像
    
    Args:
        char: 汉字
        font_path: 字体路径（None = 自动找楷体）
        size: 输出图像大小
        output: 保存路径（None = 不保存）
    
    Returns:
        (256, 256) 灰度 numpy 数组
    """
    # 找楷体
    if font_path is None:
        candidates = [
            '/usr/share/fonts/truetype/arphic/ukai.ttc',
            '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc',
        ]
        font_path = next((p for p in candidates if os.path.exists(p)), None)
    
    if font_path is None:
        raise FileNotFoundError("找不到中文字体")
    
    # 渲染
    font = ImageFont.truetype(font_path, int(size * 0.7))
    img = Image.new('L', (size, size), 255)
    draw = ImageDraw.Draw(img)
    
    bbox = draw.textbbox((0, 0), char, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    
    draw.text((x, y), char, fill=30, font=font)
    
    # 保存
    if output:
        img.save(output)
        print(f"  → {output}")
    
    return np.array(img)


def download_from_shufazidian(char: str, output_dir: str = None) -> bool:
    """
    从书法字典网下载真实字帖。
    因为需要解析HTML，这里留作备用接口。
    """
    # 书法字典网搜索URL: https://www.shufazidian.com/s.php?q=大
    import urllib.request
    import urllib.parse
    
    url = f"https://www.shufazidian.com/s.php?q={urllib.parse.quote(char)}"
    print(f"  尝试下载: {url}")
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        
        # 查找图片URL
        import re
        img_urls = re.findall(r'<img[^>]+src="([^"]+)"', html)
        char_imgs = [u for u in img_urls if 'shufa' in u.lower() or 'zi' in u.lower()]
        
        if char_imgs:
            img_url = char_imgs[0]
            if not img_url.startswith('http'):
                img_url = 'https://www.shufazidian.com' + img_url
            
            req2 = urllib.request.Request(img_url, headers={
                'User-Agent': 'Mozilla/5.0'
            })
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                img_data = resp2.read()
            
            outpath = os.path.join(output_dir or OUTDIR, f'{char}_真实字帖.png')
            with open(outpath, 'wb') as f:
                f.write(img_data)
            print(f"  ✅ 下载成功: {outpath}")
            return True
    except Exception as e:
        print(f"  ❌ 下载失败: {e}")
    
    return False


def generate_all_copybooks(characters: list = None):
    """批量生成所有字帖"""
    if characters is None:
        characters = ['大', '人', '中', '永', '心', '山', '天', '地', '国', '水']
    
    print(f"=== YLYW 字帖生成 ===")
    print(f"  楷体渲染: {len(characters)} 个字")
    print(f"  输出目录: {OUTDIR}")
    print()
    
    # 楷体渲染
    print("[楷体渲染]")
    for char in characters:
        outpath = OUTDIR / f'{char}_楷体.png'
        render_char(char, output=str(outpath))
    
    print(f"\n  完成! 字帖在: {OUTDIR}")
    return OUTDIR


if __name__ == '__main__':
    generate_all_copybooks()
