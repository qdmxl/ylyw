#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_corpus_suwen.py — 从《黄帝内经素问》(王冰注本)提取干净文言正文

"中医世家数据库"排版格式清理：
  - 去掉 <目录>/<篇名>/书名/作者/朝代/年份/属性 等结构标记
  - 正文为"属性："后的文言原文，含 '∶' 分隔问答
  - 合并折行、去空白
输出：corpus_suwen_wenyan.json（分句后的文言原文列表），供自组织验证。
"""
import os, json, re
HERE = os.path.dirname(os.path.abspath(__file__))

SRC = os.path.join(HERE, "内经语料/黄帝内经素问_王冰注.txt")
OUT = os.path.join(HERE, "corpus_suwen_wenyan.json")

def clean():
    t = open(SRC, encoding="utf-8", errors="ignore").read()
    # 1) 去掉所有 <xxx> 标记（篇名/目录等）
    t = re.sub(r'<[^>]+>', '', t)
    # 2) 去掉书头信息行
    lines = [l for l in t.split('\n')]
    keep = []
    for l in lines:
        s = l.strip()
        if re.match(r'^(书名|作者|朝代|年份|版本|书名)：', s):
            continue
        if s in ('目录',):
            continue
        keep.append(s)
    t = '\n'.join(keep)
    # 3) 去掉'属性：'前缀(保留其后正文)
    t = re.sub(r'属性：?', '', t)
    # 4) 去掉空行与折行,并规范全角冒号前的空格
    t = re.sub(r'\s+', '', t)  # 合并所有空白(含折行)——文言无必要空格
    # 5) 全角 '∶' 统一为 '，' 分隔(问答),或保留；此处统一换全角冒号便于切句
    t = t.replace('∶', '：')
    return t

def split_sentences(t):
    # 按 。！？；切句,保留较长句
    parts = re.split(r'[。！？；\n]', t)
    sents = [p.strip() for p in parts if len(p.strip()) >= 4]
    return sents

def main():
    t = clean()
    sents = split_sentences(t)
    body = ''.join(sents)
    print(f"素问原文清理后: 文章总长 {len(t)} 字符")
    print(f"切句(≥4字): {len(sents)} 句, 正文合计 {len(body)} 字")
    json.dump(sents, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"已保存 {OUT}")
    print("\n--- 采样8句 ---")
    for s in sents[2:10]:
        print("  ", s[:60])

if __name__ == "__main__":
    main()
