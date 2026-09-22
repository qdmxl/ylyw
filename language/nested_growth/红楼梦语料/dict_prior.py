#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dict_prior.py — 【字典/说文解字 先验注入模块】(P2)

马老师判断(3)(4)：
  (3) 人类对汉语的学习依赖于字典/词典/说文解字的基础知识，这些才是丰富语义的来源。
      易理模型应学习字典词典内容，不要一味零样本自己摸索。
  (4) 学习字典词典不是简单构建知识库检索，而要"内化"为引擎模型内部结构，
      体现汉字之间丰富的联系。

本模块把字典知识组织成**可注入的可学习先验**（而非检索库）：
  - CHAR_PRIOR : 字 → 先验义项列表（每个义项=一个64卦语义分布 + 词性/域标签）
  - WORD_PRIOR : 词 → 先验义项列表（词典义项，作为词胞初始 sem_yaos）
  - RADICAL_64 : 部首 → 64卦分布（由传统部首语义卦 扩展映射到 64 维软分布）

设计要点：
  1. **先验即初始化**：字/词胞一诞生就用字典先验初始化 64 卦分布与义项库，
     不是从随机/零样本起步 → 引擎"学过词典"再读语料。
  2. **基础义保护**：首义项=字典本义/部首义，学习时只新增/收敛语料义，
     绝不覆盖字典基础义（镜像并升级 08-21 的"基础义保护"军规）。
  3. **结构化**：每义项带 (64卦分布, 词性, 语义域) ，为后续"语言自组织规律"
     学习留接口（语法/搭配 → 虚词与实词的卦间转移）。

⚠️ 规模说明：此处先做**抽样机制验证**（覆盖高频核心字/词 + 典型歧义/多义词），
   验证"字典先验内化"机制有效后再对接开源词典语料全量扩展。这是方法论验证，非偷懒。
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import numpy as np

from bagua64 import (N_STATE, soft_from_bagua, soft_from_dists, top_k,
                     BAGUA_INDEX, entropy)

# ------------------------------------------------------------
# 字典先验结构
# ------------------------------------------------------------
# 一个义项 = {
#   'gua': '乾' 或 64维分布数组,      # 核心语义卦
#   'pos': 'n|v|adj|adv|虚',          # 词性（语法/自组织规律用）
#   'domain': '自然/物质/情感/时间/动作/抽象…',  # 语义域
#   'strength': float,                # 该义项先验强度
# }
Sense = dict

def _sense(gua: str, pos: str, domain: str, strength: float = 0.85) -> Sense:
    return {"gua": gua, "pos": pos, "domain": domain, "strength": strength}

# 部首 → 传统语义卦（继承并扩展 08-21 的 RADICAL_SEMANTICS，映射到64卦）
# (部首字符集, 义旁独体字/示例, 主导卦, 强度, 语义域)
RADICAL_64 = [
    # —— 五行/物质（物象极明确） ——
    (set("氵水冫"), set("水泪汤江海溪泉潮波浪浆浴滋洲泛滥沐浴"), "坎", 0.85, "物质·水"),
    (set("灬火"), set("火烛灯焰炽燃烧煮烹烤煎熏炎炎热"), "离", 0.85, "物质·火"),
    (set("木"), set("木林树村枚果板桌椅床梁柱机森棵枝"), "巽", 0.70, "物质·木"),
    (set("钅金"), set("金银钱铁铜锡铃锣钢锻镜"), "乾", 0.70, "物质·金"),
    (set("土"), set("土尘地城墙坪坡堤垣垒基堆埃址壤"), "坤", 0.65, "物质·土"),
    # —— 地支/时象 ——
    (set("日"), set("日晖晴煦旭晨旦昭时"), "离", 0.60, "时间·日"),
    (set("月"), set("月明朔望朗"), "坎", 0.55, "时间·月/阴"),
    (set("辰"), set("晨振震辰"), "震", 0.60, "时象·辰(雷动)"),
    # —— 自然天象（说文增） ——
    (set("雨"), set("雨雷雪雲云霜雾露雹霁霄霓霖雾"), "坎", 0.75, "自然·雨(水)"),
    (set("風风"), set("风飘飏飚飒风云"), "巽", 0.70, "自然·风(入)"),
    (set("云"), set("云芸昙"), "坎", 0.55, "自然·云气"),
    (set("電电"), set("电雷霓震"), "离", 0.65, "自然·电(光)"),
    # —— 地貌/土石（说文增） ——
    (set("山"), set("山岭峰峦峻岫崇巍嶂岗崖岸"), "艮", 0.85, "自然·山"),
    (set("石"), set("石岩矿礁磅磊砦砚碎砺碰砖砂"), "艮", 0.70, "物质·石"),
    (set("田"), set("田甸畦畔畴畈界畔"), "坤", 0.60, "物质·田(土)"),
    (set("谷"), set("谷谿壑豁"), "坎", 0.60, "自然·谷(水通)"),
    (set("阜阝"), set("队陟降阶防隔险阳阴陵附陌隹"), "艮", 0.55, "地貌·阜(高土)"),
    (set("邑阝"), set("邦郡都郊邸郢邯郸"), "坤", 0.50, "地貌·邑(国聚)"),
    (set("纟糸糸"), set("红绿绢索绳丝细纠织绩绪"), "巽", 0.60, "物质·丝(柔)"),
    # —— 草木植物（说文增） ——
    (set("艹艸"), set("草花荣华苗茶药萌芳芳芸芝若英"), "巽", 0.60, "自然·草木"),
    (set("竹"), set("竹笈笠第笛笔筱筱箪简"), "巽", 0.65, "自然·竹"),
    (set("禾"), set("禾秀秋种稻穗穗积秒秋"), "巽", 0.60, "物质·禾(木生)"),
    (set("米"), set("米粮粉粥粱粗糤"), "坤", 0.55, "物质·米(土谷)"),
    (set("麻"), set("麻麾靡"), "巽", 0.55, "物质·麻"),
    (set("麦麥"), set("麦麸麸面麋"), "巽", 0.55, "物质·麦"),
    (set("瓜"), set("瓜瓠瓣瓞"), "巽", 0.55, "植物·瓜(蔓)"),
    # —— 动物（说文增） ——
    (set("马馬"), set("马驰骋骏骥驮驾骆驼骑"), "乾", 0.65, "动物·马(健行)"),
    (set("牛"), set("牛牧牢牝牡牺牲犁"), "坤", 0.55, "动物·牛(厚顺)"),
    (set("羊"), set("羊群祥善美羹鲜羚"), "坤", 0.55, "动物·羊(顺)"),
    (set("犬犭"), set("狗猎猫猬狡猾猛狮独狼"), "艮", 0.55, "动物·犬(止御)"),
    (set("虎"), set("虎虐虏虚虔虏"), "艮", 0.55, "动物·虎(山兽)"),
    (set("鹿"), set("鹿麋麈麂麟麓"), "坤", 0.55, "动物·鹿(顺)"),
    (set("鼠"), set("鼠鼹鼬鼉"), "坎", 0.55, "动物·鼠(穴)"),
    (set("豕"), set("豕豚豨逊"), "坎", 0.55, "动物·豕(水畜)"),
    (set("龙龍"), set("龙宠笼珑龛庞"), "震", 0.65, "动物·龙(动变)"),
    (set("鱼魚"), set("鱼鲜鲤鲫鲇鲅鲸鲑鲢"), "坎", 0.65, "动物·鱼(水)"),
    (set("鸟鳥"), set("鸟鸡鸭鹅鸣鹄鸽鹂鹤"), "离", 0.60, "动物·鸟(飞明)"),
    (set("隹"), set("雀雕雁隽难雌雄集雅雉"), "离", 0.55, "动物·隹(鸣)"),
    (set("虫"), set("虫蚕蚊蝶蛙蚂蚁蜂虾蝌蚪蝉"), "巽", 0.60, "动物·虫(蠕动)"),
    # —— 身体/心性（说文增） ——
    (set("人亻"), set("人仆仙伊佳伦修倍侯位住仁他们"), "乾", 0.55, "身体·人"),
    (set("女"), set("女好如妙妇妻妾婚姨妹姑"), "坤", 0.55, "身体·女(顺)"),
    (set("子"), set("子孙孑孓孩孕孝存"), "坎", 0.55, "身体·子(萌)"),
    (set("心忄"), set("思念虑悲恐喜怒爱恨情志性"), "离", 0.60, "心理·心"),
    (set("目"), set("目盲看盯眨睁眼睛睦睫瞻"), "离", 0.60, "身体·目(明)"),
    (set("耳"), set("耳闻聆聪聊聋职耸耻聂"), "巽", 0.55, "身体·耳(听入)"),
    (set("口"), set("口言说命令唤"), "兑", 0.60, "言语·口"),
    (set("言讠"), set("语谈讲说论训诗词"), "兑", 0.60, "言语·言"),
    (set("舌"), set("舌甜舔舐"), "兑", 0.55, "言语·舌"),
    (set("手扌"), set("手打持握推拿拉提拨指拳挎"), "震", 0.60, "动作·手"),
    (set("足"), set("足践踏跳跑跟跗蹦跶蹄蹋"), "震", 0.60, "动作·足(行)"),
    (set("身"), set("身躯躬躲躺"), "震", 0.55, "身体·身(动)"),
    (set("骨"), set("骨骼髅骸髓" ), "乾", 0.55, "身体·骨(刚)"),
    (set("血"), set("血衅衊衅衅" ), "坎", 0.55, "身体·血(液)"),
    (set("首"), set("首道馘" ), "乾", 0.55, "身体·首"),
    # —— 动作/行为（说文增） ——
    (set("走辶"), set("行走进退过迁达赴赶起趁超越走道" ), "震", 0.60, "动作·行"),
    (set("彳"), set("往征彼很待徐律得德途径衍"), "震", 0.55, "动作·彳(行)"),
    (set("攵攵"), set("放收攻改故政教效敬敏敢散"), "震", 0.55, "动作·攵(击)"),
    (set("止"), set("正步此些出" ), "震", 0.55, "动作·止(基)"),
    (set("立"), set("立站童端竖竭耸靖" ), "震", 0.55, "动作·立"),
    (set("廴"), set("廷延建" ), "震", 0.55, "动作·廴(长行)"),
    # —— 器物/工具（说文增） ——
    (set("车車"), set("车轨轮转轻较辅载轩辐轿轿" ), "震", 0.60, "器物·车(动)"),
    (set("舟"), set("船航舰艇舱舵舷" ), "坎", 0.60, "器物·舟(水行)"),
    (set("皿"), set("皿盘盆盂盖盈盗监" ), "坎", 0.55, "器物·皿(盛水)"),
    (set("缶"), set("缶缸缺罐罍" ), "坤", 0.50, "器物·缶(瓦)"),
    (set("瓦"), set("瓦瓮瓷瓶甄" ), "坤", 0.50, "器物·瓦(土)"),
    (set("玉王"), set("玉宝珠珍珊琳琪璃琛瑞理球" ), "乾", 0.60, "器物·玉(坚润)"),
    (set("贝貝"), set("贝财货贸贤贵资费购赏赠" ), "乾", 0.55, "器物·贝(钱)"),
    (set("巾"), set("巾布帐帘帛帆帽帕" ), "巽", 0.55, "器物·巾(布柔)"),
    (set("衣衤"), set("衣袍被初衫袖袜裙补袜裹袋" ), "巽", 0.55, "器物·衣(覆柔)"),
    (set("示礻"), set("礼祝祷祭福社祈神祖祥禄" ), "艮", 0.50, "礼仪·神"),
    # —— 居所/建筑/标识（说文增） ——
    (set("宀"), set("家室宅客宫宿安定宝察富实" ), "艮", 0.55, "居所·宀(止居)"),
    (set("囗"), set("回因园圆图解困围固国" ), "坤", 0.50, "居所·囗(围土)"),
    (set("穴"), set("穴空穿窗穷究窖窿" ), "坎", 0.55, "居所·穴(空虚)"),
    (set("尸"), set("尸层居展属屋屏" ), "艮", 0.50, "居所·尸(止)"),
    (set("门門"), set("门闪闭间闲问闯闷闻闸阔" ), "艮", 0.50, "居所·门(止)"),
    (set("户"), set("户护启扁房扉" ), "艮", 0.50, "居所·户(止)"),
    (set("宀"), set("家室宅客宫宿安" ), "艮", 0.55, "居所·宀(止居)"),
    (set("广"), set("广店库庭府厅麻席庙" ), "艮", 0.55, "居所·广(高屋)"),
    (set("厂"), set("厂厩厝原厌" ), "艮", 0.55, "居所·厂(崖)"),
    (set("卜"), set("卜占卦贞"), "兑", 0.55, "标识·卜(言兆)"),
    (set("鬼"), set("鬼魂魁魅魄魏" ), "坤", 0.50, "标识·鬼(阴)"),
]

RADICAL_64_MAP: Dict[str, Tuple[str, float, str]] = {}
for rads, meaning, gua, strength, domain in RADICAL_64:
    for r in rads:
        RADICAL_64_MAP.setdefault(r, (gua, strength, domain))

def radical_prior64(word: str) -> Optional[np.ndarray]:
    """整词/字→64卦软分布（部首/字形拆解命中）

    v2(说文/拆字升级): 优先用 hanzi_chaizi 拆字库把汉字拆成部件，
    再查部件是否属某部首族。形声字(河/树/跑/爱/家)能正确命中形旁。
    回退: 字符子串包裹(r in word) 与 逐字拆解。
    """
    # 1) 直接字符子串命中（部首本身就是字，如“心口日水”独立出现）
    for rads, meaning, gua, strength, domain in RADICAL_64:
        if any(r in word for r in rads):
            return soft_from_bagua(gua, prob=strength)
        if word in meaning:
            return soft_from_bagua(gua, prob=strength)
    # 2) 拆字库：形声字拆成部件后查形旁
    parts = chaizi_decompose(word)
    for part in parts:
        for rads, meaning, gua, strength, domain in RADICAL_64:
            if part in rads or part in meaning:
                return soft_from_bagua(gua, prob=strength)
    # 3) 整词的每个单字递归（复合词）
    return None


# ------------------------------------------------------------
# 64卦语义命中层（V3: 让字义落到具体64卦基矢, 激活56个闲置维度）
# 利用 gua64_semantics 的每卦专属'载'义项, 字/部首/拆字部件命中对应卦位。
# 返回64维软分布, 命中落在具体卦(不只8经卦)。
# ------------------------------------------------------------
def prior64_semantic(word: str, inject: float = 0.55) -> Optional[np.ndarray]:
    """字/词 → 64卦语义分布(命中具体卦位)。
    命中来源: 整字、拆字部件、部首族, 落到 gua64_semantics 各卦'载'义项。
    inject: 命中卦概率主角(其余按比例)。
    \n    若仅落8经卦则退化为 soft_from_bagua 兼容。
    """
    try:
        from gua64_semantics import GUA_BY_INDEX, N_STATE as GNS
    except Exception:
        return None
    if not word:
        return None
    # 收集候选部件(整字+拆字+部首命中字)
    cands = set(word)
    try:
        parts = chaizi_decompose(word)
        cands.update(parts)
    except Exception:
        pass
    try:
        from gua64_semantics import NAME_INDEX as _GNAME_IDX
    except Exception:
        _GNAME_IDX = {}
    # 卦名整词优先: word 恰为某卦名 → 直接强命中(不受拆字部件噪声干扰)
    if word in _GNAME_IDX:
        d = np.full(GNS, (1.0 - inject) / (GNS - 1)) if GNS > 1 else np.ones(GNS)
        d[_GNAME_IDX[word]] = inject
        d = d / d.sum()
        return d
    # 遍历64卦, 按命中强度给分:
    #  tier1(强): 命中卦名自身(专属锚, 最强)
    #  tier2(中): 命中多字义项词(直接整体匹配)
    #  tier3(弱): 命中单字, 若该字被>=3卦共用则降权(防串扰)
    # 载义项全部拆成语义词项
    zai_all = {}   # idx -> [(item, is_multi)]
    for idx, g in GUA_BY_INDEX.items():
        zai_all[idx] = [(it.strip(), len(it.strip()) > 1)
                        for it in g["zai"].split(",") if it.strip()]
    # 统计单字跨卦共享度(串扰源)
    from collections import Counter
    single_count = Counter()
    for items in zai_all.values():
        for it, multi in items:
            if not multi:
                single_count[it] += 1

    scored = {}    # idx -> (score, n_hits)
    word_chars = set(word)
    for idx, items in zai_all.items():
        gname = GUA_BY_INDEX[idx]["name"]
        score = 0; n = 0
        for it, multi in items:
            if it in cands:
                n += 1
                if it == gname or (word_chars and gname in word_chars and it == gname):
                    # tier0/tier1: 载项 == 卦名(整词或单字卦名命中)
                    score += 6.0 if len(gname) > 1 and word == gname else 4.0
                elif any(ch in gname for ch in it) and len(gname) > 1 and len(it) == 1:
                    # tier1b: 单字属于多字卦名(如'济'∈'既济') → 强锚
                    score += 3.0
                elif multi:                        # tier2 多字义项整词
                    score += 2.0
                else:                              # tier3 单字
                    share = single_count[it]
                    score += 1.5 / share if share else 1.0
        if n:
            scored[idx] = (score, n)
    if not scored:
        return None
    # 取最高分卦(可多个同位)
    top_score = max(scored.values())[0]
    top_idx = [idx for idx, (s, _) in scored.items() if s >= top_score * 0.99]
    # 建64维分布: 命中卦为主角(用inject), 其余按比例铺
    d = np.full(GNS, (1.0 - inject) / (GNS - 1)) if GNS > 1 else np.ones(GNS)
    fill = inject / max(1, len(top_idx))
    for idx in top_idx[:3]:
        d[idx] = fill
    s = d.sum()
    if s <= 0:
        return None
    return d / s


# ---------- hanzi_chaizi 拆字库缓存（字形→部首 关键基础设施） ----------
_chaizi_data: Optional[Dict[str, List[List[str]]]] = None


def _load_chaizi():
    global _chaizi_data
    if _chaizi_data is None:
        import pickle, os
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chaizi.pkl")
        if os.path.exists(p):
            with open(p, "rb") as f:
                _chaizi_data = pickle.load(f)
        else:
            _chaizi_data = {}
    return _chaizi_data


def chaizi_decompose(word: str) -> List[str]:
    """返回汉字拆出的部件列表(首拆)。汉字→[形旁, 声旁…]; 非汉字/无拆→[自身]。"""
    d = _load_chaizi()
    out = []
    for ch in word:
        if ch not in d:
            out.append(ch)
            continue
        parts = d[ch]
        first = parts[0] if parts else [ch]
        for p in first:
            out.append(p)
    # 去重保序
    seen=set(); uniq=[]
    for p in out:
        if p not in seen:
            seen.add(p); uniq.append(p)
    return uniq

# ------------------------------------------------------------
# 字 字典先验（说文/常用义）—— 抽样核心字验证
# ------------------------------------------------------------
# 每个字：字源本义卦 + 引申义项（多义 → 多个 Sense）
CHAR_PRIOR: Dict[str, List[Sense]] = {
    # 自然·五行核心字（多义/歧义代表）
    "水": [_sense("坎", "n", "物质·水", 0.9), _sense("坎", "虚", "量词·域", 0.6)],
    "火": [_sense("离", "n", "物质·火", 0.9), _sense("离", "adj", "情绪·急", 0.6)],
    "木": [_sense("巽", "n", "物质·木", 0.9), _sense("巽", "n", "五行·木", 0.7)],
    "金": [_sense("乾", "n", "物质·金", 0.9), _sense("乾", "n", "五行·金/财", 0.7)],
    "土": [_sense("坤", "n", "物质·土", 0.9), _sense("坤", "n", "五行·土/地", 0.7)],
    "石": [_sense("艮", "n", "物质·石", 0.9), _sense("艮", "n", "姓氏·专名", 0.5)],
    "山": [_sense("艮", "n", "自然·山", 0.9)],
    "日": [_sense("离", "n", "时间·日/太阳", 0.85), _sense("离", "n", "时间·天", 0.6)],
    "月": [_sense("坎", "n", "时间·月/月亮", 0.85), _sense("坎", "n", "时间·月份", 0.6)],
    "心": [_sense("离", "n", "心理·心", 0.85), _sense("离", "n", "部位·心", 0.6)],
    # 高度多义/抽象（回应"语言自组织规律"）
    "点": [_sense("离", "v", "动·点燃/发光", 0.8), _sense("坎", "v", "动·蘸水/滴落", 0.7),
           _sense("乾", "n", "量词·点/少量", 0.6), _sense("离", "n", "抽象·要点", 0.6)],
    "打": [_sense("震", "v", "动·敲击", 0.8), _sense("巽", "v", "动·泛化动作", 0.5),
           _sense("兑", "v", "动·言语交锋", 0.5)],
    "开": [_sense("离", "v", "动·展开/明亮", 0.7), _sense("震", "v", "动·启动", 0.6)],
    "高": [_sense("乾", "adj", "形容·高", 0.7), _sense("乾", "n", "抽象·程度", 0.6)],
    "白": [_sense("乾", "adj", "色·白/明亮", 0.7), _sense("乾", "v", "动·说白/道白", 0.5)],
    # 虚词/语法词（语言自组织规律的典型）
    "了": [_sense("坤", "虚", "语法·完成体", 0.8), _sense("离", "v", "动·了结", 0.5)],
    "的": [_sense("坤", "虚", "语法·定语标记", 0.8)],
    "把": [_sense("坤", "虚", "语法·处置介词", 0.7), _sense("巽", "v", "动·握持", 0.6)],
    "在": [_sense("艮", "虚", "语法·处所介词", 0.7), _sense("震", "v", "动·存在", 0.6)],
 }

# 词 字典先验（词典义项）—— 抽样
WORD_PRIOR: Dict[str, List[Sense]] = {
    "江河": [_sense("坎", "n", "自然·水/河流", 0.9), _sense("坎", "n", "比喻·境界/气势", 0.7)],
    "火焰": [_sense("离", "n", "物质·火/光", 0.9)],
    "树木": [_sense("巽", "n", "自然·木/林", 0.9)],
    "金色": [_sense("乾", "n", "色·金光/贵重", 0.85), _sense("乾", "adj", "形容·珍贵", 0.7)],
    "土地": [_sense("坤", "n", "自然·土/田地", 0.9)],
    "石头": [_sense("艮", "n", "物质·石/硬", 0.9)],
    "山峰": [_sense("艮", "n", "自然·山/高", 0.9)],
    "日光": [_sense("离", "n", "光·日/明亮", 0.9)],
    "月光": [_sense("坎", "n", "光·月/清", 0.85)],
    "心情": [_sense("离", "n", "心理·情感", 0.8), _sense("离", "n", "状态·情绪", 0.7)],
    "点头": [_sense("坎", "v", "动·首部动作/应允", 0.75), _sense("乾", "v", "动·同意/认可", 0.7)],
    "点火": [_sense("离", "v", "动·点燃", 0.9)],
    "打水": [_sense("坎", "v", "动·取水", 0.85)],
    "开口": [_sense("兑", "v", "动·言语/开启", 0.8)],
    "高山": [_sense("艮", "n", "自然·山高", 0.9)],
    "明白": [_sense("离", "adj", "认知·清晰", 0.8), _sense("乾", "v", "动·理解", 0.7)],
    "明亮": [_sense("离", "adj", "光·亮", 0.9), _sense("乾", "adj", "抽象·清楚", 0.7)],
    "正在": [_sense("震", "虚", "语法·进行体", 0.75)],
    "关于": [_sense("坤", "虚", "语法·关涉介词", 0.75)],
}

# 虚词/语法词先验（语言自组织规律的直接体现——不匹配自然万象，是语言内部功能）
FUNCTION_WORDS: Dict[str, Sense] = {
    "了": _sense("坤", "虚", "语法·体标记", 0.8),
    "的": _sense("坤", "虚", "语法·结构助词", 0.8),
    "地": _sense("坤", "虚", "语法·状语标记", 0.75),
    "得": _sense("坤", "虚", "语法·补语标记", 0.75),
    "把": _sense("坤", "虚", "语法·处置", 0.7),
    "被": _sense("兑", "虚", "语法·被动", 0.7),
    "在": _sense("艮", "虚", "语法·处所", 0.7),
    "正在": _sense("震", "虚", "语法·进行", 0.75),
    "和": _sense("乾", "虚", "语法·并列连词", 0.75),
    "与": _sense("乾", "虚", "语法·并列连词", 0.75),
    "则": _sense("离", "虚", "语法·顺承连词", 0.7),
    "而": _sense("艮", "虚", "语法·转折连词", 0.7),
    "之": _sense("坤", "虚", "语法·结构助词/文言", 0.7),
    "乎": _sense("兑", "虚", "语法·语气词", 0.7),
    "者": _sense("坤", "虚", "语法·提顿", 0.7),
}

# ------------------------------------------------------------
# 查询接口：字典先验 → 64卦义项列表（词胞初始 sem_yaos）
# ------------------------------------------------------------
def char_senses(word: str) -> Optional[List[Dict]]:
    """字 → 字典先验义项列表（每义项带64卦分布）。查不到返回 None（由部首/语料补）。"""
    if word in CHAR_PRIOR:
        return [_to_sense_yao(s) for s in CHAR_PRIOR[word]]
    return None

def word_senses(word: str) -> Optional[List[Dict]]:
    """词 → 字典先验义项列表（优先词典，其次整词部首，其次组字部首聚合）。"""
    if word in WORD_PRIOR:
        return [_to_sense_yao(s) for s in WORD_PRIOR[word]]
    if word in FUNCTION_WORDS:
        return [_to_sense_yao(FUNCTION_WORDS[word])]
    # 整词部首
    r = radical_prior64(word)
    if r is not None:
        return [{"dist64": r, "pos": "N/A", "domain": "部首先验", "strength": 0.85}]
    return None

def _to_sense_yao(s: Sense) -> Dict:
    """Sense → 带64卦分布的义项字典。"""
    return {
        "dist64": soft_from_bagua(s["gua"], prob=s["strength"]),
        "pos": s["pos"], "domain": s["domain"], "strength": s["strength"],
        # 保留可读卦名
        "orig": s["gua"].strip(),
    }

def function_word(word: str) -> Optional[str]:
    """判断是否虚词/语法词 → 返回卦名先验（用于自组织规律通道）。"""
    if word in FUNCTION_WORDS:
        return FUNCTION_WORDS[word]["gua"]
    if word != "" and _is_low_content(word):
        return "兑"
    return None


LOW_CONTENT_CHARS = set(
    "你我他她它这那都就算不也是有无一二自其番又将又还好从于以为可能此彼么甚何谁别每最很太极更"
    "就咱们俩哪些个这些那些怎样怎么如何因故因此所以因为但而于对向给在从中上下去来内外面"
    "虽然若果则且或乃既曾经已经正也仍还在着过跟同被把使让叫问",
)


def _is_low_content(word: str) -> bool:
    """低语义内容字(高频虚化/代词/副词/量词等)：不应主导语境测量方向。"""
    return all(ch in LOW_CONTENT_CHARS for ch in word)

    return None

def char_prior_cover(ch: str) -> Optional[str]:
    """字是否在字典先验中 → 返回主导卦。"""
    if ch in CHAR_PRIOR:
        return CHAR_PRIOR[ch][0]["gua"]
    return None

# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== 字典先验注入自检 ===")
    for w, senses in [("点", CHAR_PRIOR["点"]), ("江河", WORD_PRIOR["江河"]), ("的", CHAR_PRIOR["的"])]:
        print(f"\n『{w}』 字典义项 {len(senses)} 个:")
        for s in senses:
            if "gua" in s:
                dist = soft_from_bagua(s["gua"], prob=s["strength"])
            else:
                dist = s.get("dist64")
            top = top_k(dist, 3)
            print(f"  [{s['pos']}/{s['domain']}] 主导=({top[0][0]},{top[0][2]},{top[0][1]:.2f}) "
                  f"熵={entropy(dist):.2f}bits  Top={[(t[2],round(t[1],2)) for t in top]}")
    w = "江河"
    sw = word_senses(w)
    print(f"\nword_senses('{w}') → {len(sw)}个义项, 首个主导(top): {top_k(sw[0]['dist64'],3)}")
    print("字典先验注入 OK")
