#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_corpus_zhongyi.py — 多典籍中医语料统一清洗

统一处理多部中医经典原文 → 分句语料 json。
典籍：
  内经(素问+灵枢,已清洗,直接读) / 难经 / 伤寒论 / 金匮要略 / 神农本草经 / 温病条辨 / 脉经
输出：
  每部: corpus_<名>_wenyan.json
  合并: corpus_zhongyi_all.json   (全部医经)
"""
import os, json, re
HERE = os.path.dirname(os.path.abspath(__file__))
YIYI = os.path.join(HERE, "医经语料")

# 典籍清单: (键, 文件名, 是否续接已清洗的内经语料)
BOOKS = [
    ("neijing", None, True),          # 内经: 读既有 corpus_neijing_wenyan.json
    # 第一批(2026-08-16)
    ("nannjing", "难经_原文.txt", False),
    ("shanghan", "伤寒论_原文.txt", False),
    ("jinkui", "金匮要略_原文.txt", False),
    ("bencao", "神农本草经_原文.txt", False),
    ("wenbing", "温病条辨_原文.txt", False),
    ("maijing", "脉经_原文.txt", False),
    # 第二批(2026-08-16 针灸甲乙经等): 针灸/理论/辨证
    ("zhenjiu_jia", "针灸甲乙经_原文.txt", False),
    ("zhenjiu_da", "针灸大成_原文.txt", False),
    ("zhongcang", "中藏经_原文.txt", False),
    ("piwei", "脾胃论_原文.txt", False),
    ("bingyuan", "诸病源候论_原文.txt", False),
    ("danxi", "丹溪心法_原文.txt", False),
]

def clean_book(path):
    """清洗单部典籍(中医世家/中国龙数据库排版) → 分句列表。"""
    t = open(path, encoding="utf-8", errors="ignore").read()
    t = re.sub(r'<[^>]+>', '', t)
    t = '\n'.join(l.strip() for l in t.split('\n')
                  if l.strip() and not re.match(r'^(书名|作者|朝代|年份|版本)', l.strip()) and l.strip() != '目录')
    t = re.sub(r'属性：?', '', t)
    t = re.sub(r'\s+', '', t)
    t = t.replace('∶', '：')
    t = t.replace('﹔', '；').replace('〖','').replace('〗','')
    # 去方剂组成的剂量符号残留
    t = re.sub(r'\\[xX]', '', t)
    # 难经特殊: 去掉"X难X难曰"的篇头重复前缀(保留首个)
    if '难经' in path:
        t = re.sub(r'第?[一二三四五六七八九十百]+难', '', t)  # 简化
        t = re.sub(r'(?<=曰)(.*?)(?=二难|三难|四难|五难|六难|七难|八难|九难|十难|十一难|十二难|十三难|十四难|十五难|十六难|十七难|十八难|十九难|二十难|二十一难|二十二难|二十三难|二十四难|二十五难|二十六难|二十七难|二十八难|二十九难|三十难)', r'\1\n', t)
    # 切句
    parts = re.split(r'[。；！？\n]', t)
    sents = [p.strip() for p in parts if len(p.strip()) >= 4]
    return sents

def main():
    all_sents = []
    for key, fn, is_neijing in BOOKS:
        if is_neijing:
            path = os.path.join(HERE, "corpus_neijing_wenyan.json")
            sents = json.load(open(path, encoding="utf-8"))
            src = "内经(既有语料)"
        else:
            path = os.path.join(YIYI, fn)
            if not os.path.exists(path):
                print(f"⚠️  缺 {fn}, 跳过"); continue
            sents = clean_book(path)
            src = fn
        body = ''.join(sents)
        out = os.path.join(HERE, f"corpus_{key}_wenyan.json")
        json.dump(sents, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f"✅ {key:<8} {src:<22} {len(sents):>6}句  {len(body):>7}字")
        all_sents.extend(sents)
    out_all = os.path.join(HERE, "corpus_zhongyi_all.json")
    json.dump(all_sents, open(out_all, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"\n总计: {len(all_sents)}句, {sum(len(s) for s in all_sents)}字 → {out_all}")

if __name__ == "__main__":
    main()
