#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发下载 MVTec AD 指定类别 (hf-mirror)。"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

BASE = "https://hf-mirror.com/datasets/Voxel51/mvtec-ad/resolve/main/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/mvtec")
CATS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["bottle"]
os.makedirs(OUT, exist_ok=True)
samples = json.load(open("/tmp/samples.json"))["samples"]

jobs = []
for s in samples:
    cat = s["category"]["label"]
    if cat not in CATS: continue
    defect = s["defect"]["label"]; split = s["split"]; fp = s["filepath"]
    dest = os.path.join(OUT, cat, split, defect, os.path.basename(fp))
    jobs.append((fp, dest, dict(cat=cat, split=split, defect=defect, path=dest, src=fp)))

def fetch(job):
    fp, dest, meta = job
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return True, meta
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for i in range(3):
        try:
            req = urllib.request.Request(BASE + fp, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as f:
                f.write(r.read())
            return True, meta
        except Exception as e:
            if i == 2: return False, meta
            time.sleep(1)
    return False, meta

print(f"待下载 {len(jobs)} 张 -> {OUT}", flush=True)
ok = 0; done = 0; metas = []
t0 = time.time()
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(fetch, j) for j in jobs]
    for fu in as_completed(futs):
        r, meta = fu.result(); done += 1; ok += r; metas.append(meta)
        if done % 50 == 0 or done == len(jobs):
            el = time.time()-t0
            print(f"  {done}/{len(jobs)} ok={ok}  {el:.0f}s  ({done/el:.1f}/s)", flush=True)

with open(os.path.join(OUT, "meta.json"), "w") as f:
    json.dump(metas, f, ensure_ascii=False, indent=1)
print(f"完成 {ok}/{len(jobs)}", flush=True)
