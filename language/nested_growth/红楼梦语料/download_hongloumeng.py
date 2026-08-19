#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载《红楼梦》全文（120回）并清洗为纯文本。
来源: github.com/hunterhug/china-literary/红楼梦/原文版红楼梦
每回一个 html, 提取 <p> 正文, 过滤导航, 合并为单一 txt。
"""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = HERE
TXT = os.path.join(OUTDIR, "红楼梦_全文.txt")
API = "https://api.github.com/repos/hunterhug/china-literary/contents/%E7%BA%A2%E6%A5%BC%E6%A2%A6/%E5%8E%9F%E6%96%87%E7%89%88%E7%BA%A2%E6%A5%BC%E6%A2%A6"
UA = {"User-Agent": "Mozilla/5.0"}

def get(url, raw_bytes=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if raw_bytes else data.decode("utf-8", errors="ignore")

def fetch_content(name):
    """按文件名(含中文空格)做 URL-encode 后从 raw 下载 html 并提取正文"""
    base = "https://raw.githubusercontent.com/hunterhug/china-literary/master/"
    enc = base + urllib.parse.quote("红楼梦/原文版红楼梦/" + name)
    html = get(enc, raw_bytes=True).decode("utf-8", errors="ignore")
    # 提取 <p> 段落
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S)
    out = []
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p)
        t = t.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        t = t.strip()
        if not t:
            continue
        # 跳过导航/首页/copyright 行
        if t in ("首页", "← 阿星星的首页") or t.startswith("下一节") or t.startswith("上一篇") \
           or "copyright" in t or t.startswith("红楼梦-原文版红楼梦：目录") or "阿星星" in t:
            continue
        out.append(t)
    return out

def main():
    d = json.loads(get(API))
    files = [x for x in d if isinstance(x, dict) and x.get("name", "").endswith(".html")]
    # 按回目排序（中文数字转序）
    cn2num = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,
              "十一":11,"十二":12,"十三":13,"十四":14,"十五":15,"十六":16,"十七":17,"十八":18,"十九":19,
              "二十":20,"二十一":21,"二十二":22,"二十三":23,"二十四":24,"二十五":25,"二十六":26,
              "二十七":27,"二十八":28,"二十九":29,"三十":30}
    def zhnum(n):
        return cn2num.get(str(n)) or 100
    def keyf(f):
        m = re.search(r'第(.+?)回', f["name"])
        return zhnum(m.group(1)) if m else 999
    files.sort(key=keyf)
    print(f"共 {len(files)} 回")

    total_chars = 0
    all_texts = []
    for i, f in enumerate(files):
        name = f["name"]
        try:
            paras = fetch_content(name)
        except Exception as e:
            print(f"  [{i+1}/{len(files)}] ✗ {name}: {e}")
            continue
        # 仅保留正文段（跳过开头的导航直到出现"此开卷..."，简化为跳过首2段导航）
        body_paras = paras
        chapter_header = name.replace("-原文.html", "").replace(".html", "")
        all_texts.append(f"\n\n【{chapter_header}】\n")
        for p in body_paras:
            all_texts.append(p)
        n = sum(len(p) for p in body_paras)
        total_chars += n
        if (i+1) % 20 == 0:
            print(f"  已下载 {i+1}/{len(files)} 回")
        time.sleep(0.3)

    text = "\n".join(all_texts)
    with open(TXT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"✅ 完成: {len(files)} 回, 总字数 ≈ {total_chars}")
    print(f"  保存: {TXT}")

if __name__ == "__main__":
    main()
