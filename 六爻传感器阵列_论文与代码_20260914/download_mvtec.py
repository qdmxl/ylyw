#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 hf-mirror 下载 MVTec AD 指定类别的图片(经 Voxel51/mvtec-ad imagefolder)。
每个 filepath 是独立文件, 可逐个 resolve 下载。"""
import json, os, sys, time
import urllib.request

BASE = "https://hf-mirror.com/datasets/Voxel51/mvtec-ad/resolve/main/"
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/mvtec"
CATS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["bottle"]

os.makedirs(OUT, exist_ok=True)
samples = json.load(open("/tmp/samples.json"))["samples"]

def fetch(path, dest, retries=3):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    url = BASE + path
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                f.write(r.read())
            return True
        except Exception as e:
            if i == retries-1:
                print(f"  FAIL {path}: {e}")
                return False
            time.sleep(1)
    return False

total = ok = 0
meta = []
for s in samples:
    cat = s["category"]["label"]
    if cat not in CATS:
        continue
    total += 1
    defect = s["defect"]["label"]
    split = s["split"]
    fp = s["filepath"]
    dest = os.path.join(OUT, cat, split, defect, os.path.basename(fp))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = fetch(fp, dest)
    ok += r
    meta.append(dict(cat=cat, split=split, defect=defect, path=dest, src=fp))
    if total % 25 == 0:
        print(f"  {total} processed, {ok} ok ...", flush=True)

with open(os.path.join(OUT, "meta.json"), "w") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
print(f"完成: {ok}/{total} 张下载到 {OUT}")
