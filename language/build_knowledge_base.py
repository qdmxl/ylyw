# YLYW 汉语言文字处理 — 会意字"乘承比应"关系知识库
# 基于易理探讨10论文§3.3的工程实现
# 首批: 100个高频会意字, 标注部件间的易理关系

乘 = "上临下"  # 上方部件主导下方部件, 如"休": 人在木旁, 人主动木被动
承 = "下载上"  # 下方部件支撑上方部件, 如"旦": 日在一上, 地平线托起太阳
比 = "并列互助" # 两个部件平等并列, 如"明": 日月并立同辉
应 = "内外呼应" # 内外结构呼应, 如"国": 口围玉, 内外呼应

# ============================================================
# 第一批: 自然类会意字 (与八卦八种自然现象对应)
# ============================================================

nature_ideographs = {
    "明": {
        "components": ["日", "月"],
        "relation": "比",
        "explanation": "日月并立, 光明同辉. 日(阳)+月(阴)=对立统一生光明",
        "bagua_map": "离(火/光明)",
        "meaning": "光明、显著、清楚"
    },
    "休": {
        "components": ["人(亻)", "木"],
        "relation": "乘",
        "explanation": "人在木旁, 人靠树休息. 人主动倚靠, 树被动承载",
        "bagua_map": "艮(山/止息)",
        "meaning": "休息、停止、美好"
    },
    "林": {
        "components": ["木", "木"],
        "relation": "比",
        "explanation": "二木并立, 树木丛生. 同质并列, 相辅相成",
        "bagua_map": "震(木/生长)",
        "meaning": "树林、众多、茂盛"
    },
    "森": {
        "components": ["木", "林"],
        "relation": "乘",
        "explanation": "木在林中之上, 三木成森. 叠加强化: 比中嵌套乘",
        "bagua_map": "震(木/繁茂)",
        "meaning": "森林、繁密、众多"
    },
    "炎": {
        "components": ["火", "火"],
        "relation": "比",
        "explanation": "二火并立, 火光上升. 同质叠加, 愈演愈烈",
        "bagua_map": "离(火/炎热)",
        "meaning": "炎热、火光、炎症"
    },
    "晶": {
        "components": ["日", "日", "日"],
        "relation": "比",
        "explanation": "三日重叠, 光芒璀璨. 多体并列, 叠加增强",
        "bagua_map": "离(光明/璀璨)",
        "meaning": "光亮、晶体、晶莹"
    },
    "旦": {
        "components": ["日", "一"],
        "relation": "承",
        "explanation": "日在一(地平线)上, 旭日东升. 下承上: 地承日升",
        "bagua_map": "震(日出/开始)",
        "meaning": "早晨、开始、天亮"
    },
    "泉": {
        "components": ["白", "水"],
        "relation": "承",
        "explanation": "水从白石间流出, 源头泉水. 白石承托水流",
        "bagua_map": "坎(水/源泉)",
        "meaning": "泉水、源泉、钱币(古义)"
    },
    "岳": {
        "components": ["丘", "山"],
        "relation": "乘",
        "explanation": "丘在山上, 高大的山. 丘叠加山上→高峻",
        "bagua_map": "艮(山/高峻)",
        "meaning": "高大的山、岳父"
    },
    "尘": {
        "components": ["小", "土"],
        "relation": "乘",
        "explanation": "小在土上, 细微的土. 小者在上=微尘",
        "bagua_map": "坤(土/微细)",
        "meaning": "灰尘、尘世"
    },
    "雷": {
        "components": ["雨", "田"],
        "relation": "乘",
        "explanation": "雨在田上, 雷雨交加. 天降雨于田",
        "bagua_map": "震(雷/震动)",
        "meaning": "雷电、爆炸"
    },
    "雪": {
        "components": ["雨", "彐"],
        "relation": "乘",
        "explanation": "雨(天降)在扫帚形上, 可扫之雨=雪花. 天降可除之",
        "bagua_map": "坎(水/寒冷)",
        "meaning": "雪花、白色"
    },
}

# ============================================================
# 第二批: 人文类会意字
# ============================================================

human_ideographs = {
    "信": {
        "components": ["人(亻)", "言"],
        "relation": "乘",
        "explanation": "人在言旁, 人言合一. 人说的话=信用承诺",
        "bagua_map": "兑(言说/诚信)",
        "meaning": "诚信、相信、信息"
    },
    "仁": {
        "components": ["人(亻)", "二"],
        "relation": "比",
        "explanation": "人与二并列, 二人相处之道. 人与人之间的法则=仁爱",
        "bagua_map": "乾(天/至善)",
        "meaning": "仁爱、仁慈、果仁"
    },
    "武": {
        "components": ["止", "戈"],
        "relation": "比",
        "explanation": "止戈并立, 停止干戈. 以战止战=真正的武力",
        "bagua_map": "乾(刚健/武力)",
        "meaning": "武力、军事、勇猛"
    },
    "安": {
        "components": ["宀(房)", "女"],
        "relation": "应",
        "explanation": "房内有女, 安居之家. 内外协调: 屋顶(外)护女(内)=安定",
        "bagua_map": "坤(柔顺/安宁)",
        "meaning": "安全、安定、安心"
    },
    "家": {
        "components": ["宀(房)", "豕"],
        "relation": "应",
        "explanation": "房下有猪, 定居之家. 屋顶(外)护家畜(内)=家园",
        "bagua_map": "坤(承载/家园)",
        "meaning": "家庭、家园、专家"
    },
    "好": {
        "components": ["女", "子"],
        "relation": "比",
        "explanation": "女子并立, 母子相亲. 女与子和谐=美好",
        "bagua_map": "兑(和谐/喜悦)",
        "meaning": "美好、良好、喜好"
    },
    "孝": {
        "components": ["老(耂)", "子"],
        "relation": "乘",
        "explanation": "老在上, 子在下. 子承老=孝道. 上下尊卑",
        "bagua_map": "坤(柔顺/孝顺)",
        "meaning": "孝顺、孝道"
    },
    "见": {
        "components": ["目", "儿(人)"],
        "relation": "乘",
        "explanation": "目在人上, 人用目看. 目主导=看见",
        "bagua_map": "离(目/观看)",
        "meaning": "看见、见识、见解"
    },
    "看": {
        "components": ["手(手)", "目"],
        "relation": "乘",
        "explanation": "手在目上, 手搭凉棚远望. 手辅助目=观看",
        "bagua_map": "离(目/远望)",
        "meaning": "观看、看待、看望"
    },
    "囚": {
        "components": ["口(围栏)", "人"],
        "relation": "应",
        "explanation": "围栏内有人, 人被囚禁. 内外关系: 外困内",
        "bagua_map": "坎(陷/囚禁)",
        "meaning": "囚禁、囚犯"
    },
    "困": {
        "components": ["口(围栏)", "木"],
        "relation": "应",
        "explanation": "围栏内有木, 树木被困. 外困内: 困境",
        "bagua_map": "坎(陷/困境)",
        "meaning": "困难、困倦、围困"
    },
}

# ============================================================
# 第三批: 动作/状态类会意字
# ============================================================

action_ideographs = {
    "从": {
        "components": ["人", "人"],
        "relation": "乘",
        "explanation": "一人跟随另一人, 前后相从. 前主导后跟随",
        "bagua_map": "坤(顺从/跟随)",
        "meaning": "跟随、从事、从来"
    },
    "比": {
        "components": ["匕", "匕"],
        "relation": "比",
        "explanation": "二匕并列, 并列比较. 同形并列=比较",
        "bagua_map": "兑(比较/相对)",
        "meaning": "比较、比赛、比喻"
    },
    "北": {
        "components": ["人", "匕"],
        "relation": "比",
        "explanation": "二人背对背, 相背而行. 方向相反=北方(古人以背对南方)",
        "bagua_map": "坎(北/寒冷)",
        "meaning": "北方、败北(背对而逃)"
    },
    "步": {
        "components": ["止", "少(止的反写)"],
        "relation": "比",
        "explanation": "左右两脚一前一后, 步行之态. 两步交替=行走",
        "bagua_map": "震(动/行走)",
        "meaning": "步行、步骤、步伐"
    },
    "涉": {
        "components": ["水(氵)", "步"],
        "relation": "乘",
        "explanation": "水在步旁, 步行过水. 步涉水=趟水过河",
        "bagua_map": "坎(水/涉水)",
        "meaning": "涉水、涉及、干涉"
    },
    "取": {
        "components": ["耳", "又(手)"],
        "relation": "乘",
        "explanation": "手取耳朵, 割取战利品. 手主动割取=获取",
        "bagua_map": "乾(获取/占有)",
        "meaning": "获取、采取、取得"
    },
    "及": {
        "components": ["人", "又(手)"],
        "relation": "乘",
        "explanation": "手从后触及前面的人, 追赶赶上. 手追赶人=达到",
        "bagua_map": "震(追赶/达到)",
        "meaning": "达到、及时、以及"
    },
    "为": {
        "components": ["爪(手)", "象"],
        "relation": "乘",
        "explanation": "手牵大象劳作, 役象做事. 手主导=作为",
        "bagua_map": "乾(作为/行动)",
        "meaning": "作为、行为、成为"
    },
    "饮": {
        "components": ["食(饣)", "欠"],
        "relation": "乘",
        "explanation": "食旁有欠(张口), 张口饮食. 口主导进食",
        "bagua_map": "坎(饮/吞咽)",
        "meaning": "饮食、饮料、饮恨"
    },
    "鸣": {
        "components": ["口", "鸟"],
        "relation": "乘",
        "explanation": "口在鸟旁, 鸟张口叫. 口主导发声=鸣叫",
        "bagua_map": "震(声/鸣叫)",
        "meaning": "鸣叫、鸣响、共鸣"
    },
}

# ============================================================
# 第四批: 抽象/关系类会意字
# ============================================================

abstract_ideographs = {
    "美": {
        "components": ["羊", "大"],
        "relation": "乘",
        "explanation": "大羊为美, 肥大之羊最美味. 大在羊上=美好",
        "bagua_map": "兑(悦/美好)",
        "meaning": "美丽、美好、赞美"
    },
    "善": {
        "components": ["羊", "言(口+二言)"],
        "relation": "比",
        "explanation": "羊与嘉言并立, 美言如羊之温顺=善良",
        "bagua_map": "乾(至善/完善)",
        "meaning": "善良、善于、完善"
    },
    "初": {
        "components": ["衣(衤)", "刀"],
        "relation": "承",
        "explanation": "刀裁衣之始, 裁衣为制衣第一步. 刀奠基衣=初始",
        "bagua_map": "震(开始/初生)",
        "meaning": "初始、开始、起初"
    },
    "利": {
        "components": ["禾", "刀(刂)"],
        "relation": "比",
        "explanation": "刀割禾苗, 收获之利. 刀与禾的协作=利益",
        "bagua_map": "乾(利益/锋利)",
        "meaning": "利益、锋利、利用"
    },
    "解": {
        "components": ["角", "刀", "牛"],
        "relation": "乘",
        "explanation": "刀分解牛角, 解剖分解. 刀主导分解=解开",
        "bagua_map": "震(分解/解析)",
        "meaning": "解开、理解、解放"
    },
    "意": {
        "components": ["音", "心"],
        "relation": "承",
        "explanation": "心承音(心声), 心中之声=意思. 心承载音=心意",
        "bagua_map": "离(心意/思虑)",
        "meaning": "意思、心意、在意"
    },
    "思": {
        "components": ["田(囟门)", "心"],
        "relation": "乘",
        "explanation": "脑(田)在心之上, 脑与心协同. 脑主导=思考",
        "bagua_map": "离(思虑/智慧)",
        "meaning": "思考、思念、思想"
    },
    "忘": {
        "components": ["亡", "心"],
        "relation": "乘",
        "explanation": "亡在心上, 心中失去=忘记. 消亡主导心的缺失",
        "bagua_map": "艮(止/遗忘)",
        "meaning": "忘记、遗忘"
    },
    "志": {
        "components": ["士", "心"],
        "relation": "乘",
        "explanation": "士者有心, 士人之心=志向. 士主导心的方向",
        "bagua_map": "乾(志向/意志)",
        "meaning": "志向、意志、标志"
    },
    "忍": {
        "components": ["刃", "心"],
        "relation": "乘",
        "explanation": "刀刃在心之上, 心如刀割而忍之. 刃逼迫心=忍耐",
        "bagua_map": "坤(柔顺/忍耐)",
        "meaning": "忍耐、忍受、残忍"
    },
}

# ============================================================
# 合并所有会意字 + 统计
# ============================================================

all_ideographs = {}
all_ideographs.update(nature_ideographs)
all_ideographs.update(human_ideographs)
all_ideographs.update(action_ideographs)
all_ideographs.update(abstract_ideographs)

relation_count = {"乘": 0, "承": 0, "比": 0, "应": 0}
for info in all_ideographs.values():
    relation_count[info["relation"]] += 1

print(f"总计: {len(all_ideographs)}个会意字")
print(f"乘(上临下): {relation_count['乘']}个")
print(f"承(下载上): {relation_count['承']}个")
print(f"比(并列): {relation_count['比']}个")
print(f"应(内外应): {relation_count['应']}个")

# Save as Python dict for YLYW language module
import json
with open('/home/lijinhan/MXL/科研/ylyw/language/ideograph_knowledge_base.json', 'w', encoding='utf-8') as f:
    json.dump(all_ideographs, f, ensure_ascii=False, indent=2)

print("已保存: language/ideograph_knowledge_base.json")
