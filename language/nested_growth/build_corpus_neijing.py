#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_corpus_neijing.py — 从《黄帝内经》(素问王冰注 + 灵枢张志聪集注)提取干净文言经文

"中医世家数据库"排版清理 + 去注：
  - 去掉 <目录>/<篇名>/书名/作者/朝代/年份/属性 结构标记
  - 去掉集注本的"按、…"注文（张志聪按语）
  - 合并折行、去空白
输出分句文言原文列表：
  corpus_suwen_wenyan.json   素问 81篇
  corpus_lingshu_wenyan.json 灵枢 81篇
  corpus_neijing_wenyan.json 素问+灵枢 合并
"""
import os, json, re
HERE = os.path.dirname(os.path.abspath(__file__))

FILES = {
    "suwen":   os.path.join(HERE, "内经语料/黄帝内经素问_王冰注.txt"),
    "lingshu": os.path.join(HERE, "内经语料/黄帝内经灵枢集注_张志聪.txt"),
}

def clean(source, drop_zhuyi=True):
    t = open(source, encoding="utf-8", errors="ignore").read()
    t = re.sub(r'<[^>]+>', '', t)          # 去 <xxx>
    lines = []
    for l in t.split('\n'):
        s = l.strip()
        if re.match(r'^(书名|作者|朝代|年份|版本|书名)：', s):
            continue
        if s == '目录':
            continue
        lines.append(s)
    t = '\n'.join(lines)
    t = re.sub(r'属性：?', '', t)
    if drop_zhuyi:
        # 去"按、…"按语：按注往往到下一个<句读>或较长；这里按"按、xxx。"整段删除，
        # 更稳健：删除"按、"开头到下一个换行后圆整——但正文也换行。改为按逗号/句号切,遇"按、"则跳过该注句
        pass
    t = re.sub(r'\s+', '', t)
    t = t.replace('∶', '：')
    # 集注按语：形如"按、本纪。帝经土设井…" —— 删除从"按、"到所在标点分句
    # 简易：以'按、'为起点，删到下一个注释结束（此处用'。'但会误伤），更稳做法在split里按'按'过滤
    return t

def split_and_drop_annotation(t):
    """切句并剔除按注句：经文句 vs 按注(以'按'开头)。"""
    # 先按句号/分号切
    parts = re.split(r'[。；]', t)
    sents = []
    for p in parts:
        p = p.strip()
        if not p or len(p) < 4:
            continue
        # 剔除按注：'按、'或'按：'开头,或包含'按：'
        if p.startswith('按') or p.startswith('注') or '按、' in p[:6] or re.match(r'^注[：:、]', p):
            continue
        sents.append(p)
    return sents

def build_one(source, drop):
    t = clean(source)
    sents = split_and_drop_annotation(t)
    return sents, len(t)

def main():
    suwen, _ = build_one(FILES["suwen"], True)
    lingshu, _ = build_one(FILES["lingshu"], True)
    nel = list(suwen) + list(lingshu)
    outs = {
        "corpus_suwen_wenyan.json": suwen,
        "corpus_lingshu_wenyan.json": lingshu,
        "corpus_neijing_wenyan.json": nel,
    }
    for fn, ss in outs.items():
        path = os.path.join(HERE, fn)
        json.dump(ss, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
        body = ''.join(ss)
        print(f"{fn}: {len(ss)}句, {len(body)}字")
    print("\n素问采样:")
    for s in suwen[:6]: print("  ", s[:55])
    print("\n灵枢采样:")
    for s in lingshu[:6]: print("  ", s[:55])

if __name__ == "__main__":
    main()
