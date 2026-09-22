#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_xdh.py — 《现代汉语词典》(第7版) 解析器

把词典全文 TXT 解析为结构化种子数据：
  - 每个【字头】→ 释义文本 + 词性序列 + 多个义项
仅抽取"单字字头"(1个汉字)，作为 64 卦引擎的**字典种子**。

输出 dict_prior 需要的种子形态（方案A：词典初始化先天知识）。
"""
from __future__ import annotations
import re, json, os
from typing import Dict, List, Optional

# 当前文件目录
_HERE = os.path.dirname(os.path.abspath(__file__))
DICT_FILE = os.path.join(_HERE, "现代汉语词典第7版_全文.txt")

# 词性标记
POS_MARK = re.compile(r"〈([^〉]{1,4})〉")
# 义项编号 ❶❷❸❹❺❻❼❽❾❿
SENSE_NUM = re.compile(r"[❶❷❸❹❺❻❼❽❾❿⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴①②③④⑤⑥⑦⑧⑨⑩]")
# 词头行: 【词头】...
HEAD_LINE = re.compile(r"【([^】]+)】")


def parse_dict(path: str = DICT_FILE) -> Dict:
    """解析整本词典。返回 {字头: {pos:[...], senses:[str], raw:str}}"""
    text = open(path, encoding="utf-8").read()
    entries: Dict[str, List] = {}
    # 逐行找词头
    for line in text.splitlines():
        m = HEAD_LINE.search(line)
        if not m:
            continue
        head = m.group(1)
        # 只保留单字字头（1个汉字）
        if len(head) != 1 or not ("\u4e00" <= head <= "\u9fff"):
            continue
        body = line[m.end():]
        # 词性
        poss = POS_MARK.findall(body)
        # 释义: 去拼音前缀、按义项拆
        senses = split_senses(body)
        entries.setdefault(head, []).append({
            "pos": poss, "senses": senses, "raw": body,
        })
    return entries


def split_senses(body: str) -> List[str]:
    """把释义按义项1/2/3…拆开（多个词条保留所有义项文本）。"""
    # 去掉词性括号
    b = POS_MARK.sub(" ", body)
    # 按义项编号切
    parts = SENSE_NUM.split(b)
    # 过滤: 去空白、去拼音/标点残留(无汉字)
    out = []
    for p in parts:
        p = p.strip().strip("丨～")
        if not p:
            continue
        if not re.search(r"[\u4e00-\u9fff]", p):
            continue        # 无汉字 = 拼音/标点残留，跳过
        out.append(p)
    return out or [b.strip()]


def build_priors(entries: Dict, topk: Optional[int] = None) -> Dict:
    """从解析结果构建 64卦种子（方案A用）。输出每字：
    {字: {pos, senses(义项文本), n_entry(词条数), char}}"""
    priors: Dict = {}
    for ch, entry_list in entries.items():
        all_senses = []
        poss = []
        for e in entry_list:
            all_senses.extend(e["senses"])
            poss.extend(e["pos"])
        priors[ch] = {
            "char": ch,
            "pos": sorted(set(poss)),
            "senses": all_senses,
            "n_entry": len(entry_list),
            "n_sense": len(all_senses),
        }
    # 按词条数排序截取
    if topk:
        sorted_ch = sorted(priors, key=lambda c: priors[c]["n_entry"], reverse=True)
        priors = {c: priors[c] for c in sorted_ch[:topk]}
    return priors


def save_priors(priors: Dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(priors, f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"解析词典: {DICT_FILE}")
    entries = parse_dict()
    print(f"单字字头词条数: {len(entries)} 个不同字")
    # 抽样展示
    print("\n=== 抽样预览 ===")
    for ch in ["水", "火", "心", "点", "打", "金"]:
        if ch in entries:
            e = entries[ch][0]
            print(f"『{ch}』 词性={e['pos']}")
            for s in e["senses"][:4]:
                print(f"   - {s[:40]}")
    priors = build_priors(entries)
    print(f"\n构建种子: {len(priors)} 字")
    out = os.path.join(_HERE, "dict_seed.json")
    save_priors(priors, out)
    print(f"已保存: {out} ({os.path.getsize(out)//1024}KB)")
