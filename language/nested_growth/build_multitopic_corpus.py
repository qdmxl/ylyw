#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_multitopic_corpus.py — 构造主题均衡的多主题语料
验证：系统通过大量(多领域)阅读 → 自动分化出清晰语义类 → 内建知识库。
每个主题给足句子量（模拟多领域持续阅读），主题间字词不重叠，共现才能分化。"""
import json, random
random.seed(0)

# 六个主题，各 150 句，字词主题内强共现、主题间弱共现
TOPICS = {
 "计算技术": ["算法", "模型", "神经网络", "机器", "学习", "数据", "特征", "训练", "深度", "参数",
              "梯度", "分类", "识别", "预测", "优化", "计算", "结构", "表示", "推理", "生成"],
 "自然物理": ["水", "流动", "江", "河", "海", "深", "山", "石", "石头", "火", "燃烧", "热",
              "温度", "木头", "树", "森林", "金属", "钢铁", "刀", "锋利", "冰雪", "霜"],
 "伦理治理": ["人", "君子", "小人", "仁", "义", "礼", "智", "信", "道德", "德", "谦", "恭",
              "贤", "善", "恶", "忠", "孝", "敬", "慎", "诚"],
 "生命身心": ["心", "思", "想", "意", "情", "感", "爱", "怕", "怒", "痛", "身", "体", "手",
              "足", "目", "耳", "口", "食", "行", "走"],
 "制度规模": ["国", "家", "君", "臣", "政", "治", "社", "稷", "天", "地", "日", "月", "星",
              "年", "春", "秋", "朝", "夕", "中", "外"],
 "学习成长": ["学", "习", "问", "温", "故", "新", "师", "朋", "友", "远", "方", "来", "乐",
              "知", "识", "见", "闻", "教", "育", "木"],
}
PHRASES = ["其中", "因此", "并且", "而且", "所谓", "认为", "基于", "可以", "表示", "即为",
           "在于", "方面", "进行", "主要", "以及", "通过", "针对", "具有", "成为", "包括"]

def generate(sentences_per=150):
    out = []
    for topic, words in TOPICS.items():
        for _ in range(sentences_per):
            k = random.randint(3, 6)
            chosen = random.sample(words, min(k, len(words)))
            sentence = "".join(chosen)
            # 每句加短语，制造"句内共现"结构
            if random.random() < 0.7:
                p = random.choice(PHRASES)
                pos = random.randint(0, len(chosen))
                sentence = "".join(chosen[:pos]) + p + "".join(chosen[pos:])
            out.append(sentence)
    random.shuffle(out)
    return out

if __name__ == "__main__":
    corpus = generate()
    json.dump(corpus, open("corpus_multitopic2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("已生成主题均衡多主题语料:", len(corpus), "句, 6主题×150句")
    # 预览
    for t, w in TOPICS.items():
        print(f"  {t}: {len(w)}词")
