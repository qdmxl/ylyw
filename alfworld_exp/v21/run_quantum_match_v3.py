#!/usr/bin/env python3
"""
run_quantum_match_v3.py — 马老师方案v3

核心创新：六爻→指数衰减编码初态→酉演化→JS散度匹配64卦。
"""
from __future__ import annotations
import json, os, sys, time, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))

import numpy as np

# ===== 6量子位酉演化器 =====
I2 = np.eye(2, dtype=complex); Z = np.array([[1,0],[0,-1]], dtype=complex); X = np.array([[0,1],[1,0]], dtype=complex)
def pop(ops):
    r = ops[-1].copy()
    for o in reversed(ops[:-1]): r = np.kron(r, o)
    return r
def clip(x): return max(0.05, min(0.95, x))

# 乘承比应哈密顿量
def build_H():
    H = np.zeros((64,64), dtype=complex)
    h = np.array([0.3, 0.5, 0.7, 0.5, 0.8, 0.4])
    for i in range(6):
        H += h[i]*pop([Z if q==i else I2 for q in range(6)])
        H += 0.15*pop([X if q==i else I2 for q in range(6)])
    J = {(0,1):0.6,(1,2):0.6,(2,3):0.8,(3,4):0.6,(4,5):0.8,(1,0):0.4,(2,1):0.4,(3,2):0.6,(4,3):0.4,(5,4):0.6,(0,2):0.25,(1,3):0.25,(2,4):0.25,(3,5):0.25,(0,3):0.35,(1,4):0.35,(2,5):0.35}
    for (i,j), v in J.items():
        H += v*pop([Z if q in (i,j) else I2 for q in range(6)])
    for tri in [(0,1,2),(1,2,3),(2,3,4),(3,4,5)]:
        H += 0.08*pop([Z if q in tri else I2 for q in range(6)])
    evals, evecs = np.linalg.eigh(H)
    return evecs @ np.diag(np.exp(-1j*0.5*evals)) @ evecs.conj().T

U = build_H()

# 64个基态
BITS = np.array(list(itertools.product([0.05, 0.95], repeat=6)))

def encode_initial(yao_vec, beta=3.0):
    y = np.array([clip(v) for v in yao_vec])
    dists = np.sqrt(np.sum((BITS - y.reshape(1,6))**2, axis=1))
    amp = np.exp(-beta * dists).astype(complex)
    amp /= np.linalg.norm(amp)
    return amp

def js(p,q):
    pu = p+1e-12; pu/=pu.sum(); qu=q+1e-12; qu/=qu.sum(); m=0.5*(pu+qu)
    return 0.5*(np.sum(pu*np.log(pu/m))+np.sum(qu*np.log(qu/m)))

# 64卦标准六爻
# 64卦标准六爻（通行本顺序，从api_docs/ylyw_core/hexagram_rules.py提取）
HX64 = np.array([
    [0.75,0.61,0.59,0.76,0.45,0.65],  # 0  乾
    [0.39,0.61,0.30,0.28,0.35,0.59],  # 1  坤
    [0.31,0.57,0.46,0.54,0.38,0.57],  # 2  屯
    [0.21,0.59,0.45,0.71,0.44,0.63],  # 3  蒙
    [0.21,0.59,0.41,0.71,0.48,0.73],  # 4  需
    [0.14,0.86,0.15,0.85,0.80,0.20],  # 5  讼
    [0.19,0.14,0.21,0.15,0.16,0.84],  # 6  师
    [0.27,0.59,0.32,0.33,0.34,0.49],  # 7  比
    [0.42,0.64,0.25,0.36,0.33,0.65],  # 8  小畜
    [0.34,0.56,0.34,0.22,0.33,0.58],  # 9  履
    [0.76,0.58,0.60,0.74,0.45,0.66],  # 10 泰
    [0.09,0.10,0.11,0.88,0.88,0.89],  # 11 否
    [0.29,0.52,0.32,0.23,0.34,0.61],  # 12 同人
    [0.75,0.55,0.23,0.19,0.31,0.47],  # 13 大有
    [0.51,0.63,0.29,0.21,0.38,0.61],  # 14 谦
    [0.25,0.62,0.41,0.70,0.49,0.71],  # 15 豫
    [0.23,0.60,0.41,0.71,0.46,0.74],  # 16 随
    [0.33,0.55,0.53,0.66,0.47,0.69],  # 17 蛊
    [0.46,0.63,0.23,0.39,0.35,0.64],  # 18 临
    [0.53,0.56,0.28,0.21,0.32,0.60],  # 19 观
    [0.29,0.55,0.44,0.51,0.39,0.57],  # 20 噬嗑
    [0.74,0.56,0.21,0.19,0.30,0.46],  # 21 贲
    [0.39,0.60,0.30,0.22,0.36,0.64],  # 22 剥
    [0.74,0.58,0.62,0.77,0.43,0.68],  # 23 复
    [0.77,0.58,0.59,0.78,0.46,0.64],  # 24 无妄
    [0.34,0.64,0.50,0.68,0.50,0.77],  # 25 大畜
    [0.55,0.59,0.57,0.71,0.43,0.61],  # 26 颐
    [0.28,0.57,0.33,0.37,0.36,0.51],  # 27 大过
    [0.76,0.57,0.24,0.19,0.33,0.46],  # 28 坎
    [0.34,0.57,0.32,0.21,0.36,0.61],  # 29 离
    [0.36,0.62,0.49,0.65,0.47,0.79],  # 30 咸
    [0.12,0.12,0.88,0.88,0.89,0.88],  # 31 恒
    [0.53,0.56,0.58,0.71,0.44,0.64],  # 32 遁
    [0.43,0.60,0.28,0.21,0.35,0.66],  # 33 大壮
    [0.56,0.54,0.27,0.13,0.35,0.60],  # 34 晋
    [0.32,0.55,0.35,0.23,0.35,0.60],  # 35 明夷
    [0.34,0.52,0.59,0.68,0.44,0.59],  # 36 家人
    [0.34,0.52,0.57,0.69,0.44,0.58],  # 37 睽
    [0.35,0.52,0.58,0.70,0.42,0.63],  # 38 蹇
    [0.51,0.60,0.28,0.23,0.35,0.61],  # 39 解
    [0.39,0.66,0.22,0.40,0.36,0.68],  # 40 损
    [0.75,0.55,0.63,0.80,0.39,0.70],  # 41 益
    [0.22,0.59,0.48,0.74,0.45,0.61],  # 42 夬
    [0.19,0.11,0.23,0.14,0.15,0.83],  # 43 姤
    [0.47,0.66,0.24,0.38,0.37,0.65],  # 44 萃
    [0.30,0.53,0.57,0.71,0.42,0.60],  # 45 升
    [0.91,0.86,0.18,0.13,0.10,0.12],  # 46 困
    [0.37,0.53,0.55,0.65,0.48,0.70],  # 47 井
    [0.76,0.56,0.61,0.70,0.43,0.64],  # 48 革
    [0.25,0.59,0.43,0.71,0.50,0.74],  # 49 鼎
    [0.87,0.85,0.16,0.12,0.11,0.12],  # 50 震
    [0.47,0.59,0.24,0.18,0.32,0.66],  # 51 艮
    [0.35,0.52,0.60,0.73,0.40,0.66],  # 52 渐
    [0.54,0.58,0.58,0.74,0.47,0.64],  # 53 归妹
    [0.22,0.60,0.40,0.69,0.49,0.75],  # 54 丰
    [0.33,0.53,0.57,0.71,0.42,0.63],  # 55 旅
    [0.59,0.61,0.24,0.28,0.34,0.56],  # 56 巽
    [0.08,0.88,0.07,0.10,0.05,0.11],  # 57 兑
    [0.49,0.60,0.29,0.21,0.32,0.64],  # 58 涣
    [0.33,0.57,0.34,0.19,0.33,0.59],  # 59 节
    [0.42,0.49,0.33,0.60,0.42,0.62],  # 60 中孚
    [0.92,0.10,0.89,0.10,0.93,0.10],  # 61 小过
    [0.07,0.88,0.11,0.07,0.06,0.11],  # 62 既济
    [0.31,0.57,0.46,0.54,0.38,0.57],  # 63 未济 (用屯模板占位，实际有64个但api_docs给了62个标准模板，差2个用已有替代)
], dtype=float)
# 修正说明：api_docs中只定义了62个标准模板（含8个重卦+上经下经共54个）
# 缺少2个用最接近的替代（Zhen(震k)和Gen(艮)已在50-51位置）
# 为保持64个完整，后几个用有定义的充填
print(f"HX64 shape: {HX64.shape}, rows={len(HX64)}")

HXN = ['乾','坤','屯','蒙','需','讼','师','比','小畜','履','泰','否','同人','大有','谦','豫',
       '随','蛊','临','观','噬嗑','贲','剥','复','无妄','大畜','颐','大过','坎','离','咸','恒',
       '遁','大壮','晋','明夷','家人','睽','蹇','解','损','益','夬','姤','萃','升','困','井',
       '革','鼎','震','艮','渐','归妹','丰','旅','巽','兑','涣','节','中孚','小过','既济','未济']

FAV = np.array([0.66,0.38,0.42,0.55,0.70,0.32,0.56,0.48,0.74,0.48,0.36,0.78,0.32,0.52,0.52,0.58,
    0.46,0.58,0.38,0.58,0.36,0.56,0.56,0.70,0.52,0.38,0.36,0.68,0.32,0.58,0.72,0.46,
    0.52,0.58,0.52,0.36,0.72,0.46,0.42,0.72,0.36,0.54,0.52,0.74,0.54,0.56,0.60,0.48,
    0.74,0.58,0.56,0.48,0.38,0.58,0.32,0.52,0.52,0.56,0.48,0.48,0.92,0.54,0.54,0.54])

# 预计算标准卦的量子演化分布
BETA = 3.0
STD_PROBS = np.zeros((64,64))
for idx in range(64):
    p = np.abs(U @ encode_initial(HX64[idx], BETA))**2; p /= p.sum()
    STD_PROBS[idx] = p

def quantum_get_best(yao_vec):
    p = np.abs(U @ encode_initial(yao_vec, BETA))**2; p /= p.sum()
    best = 0; best_js = 999.0
    for idx in range(64):
        d = js(p, STD_PROBS[idx])
        if d < best_js: best_js = d; best = idx
    sim = max(0.0, 1.0 - best_js * 2.0)
    return best, best_js, sim

# ===== 评估 =====
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--split", default="valid_seen")
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    
    from alfworld_official_wrapper import ALFWorldOfficial
    from v21.agent_v21 import AgentV21
    import train_priors as _tp; print(f"[priors] {_tp._PATH}")
    
    env = ALFWorldOfficial(split=args.split)
    results = []; t0 = time.time()
    
    for gi in range(args.start, args.start + args.games):
        obs, info = env.reset(game_idx=gi)
        task = info.get("task_desc","")
        adm = info.get("admissible_commands",["look"])
        agent = AgentV21(verbose=False)
        agent.reset(task, obs, adm, game_id=gi)
        
        won = False
        for step in range(50):
            phase = agent._phase()
            cands = []
            for cmd in adm:
                parsed = agent.scorer._parse_action(cmd)
                yao = agent.scorer.build_yao(parsed, agent.world, agent.goal, phase)
                vec = np.array(yao, dtype=float)
                bi, bj, sim = quantum_get_best(vec)
                lin = float(np.dot(vec, np.array([0.18,0.25,0.20,0.15,0.12,0.10])))
                favor = float(FAV[bi])
                prim = {"go":"go","take":"take","put":"put","open":"open","clean":"clean",
                        "heat":"heat","cool":"cool","use":"use","look":"look","help":"look","inventory":"look"}.get(parsed["verb"],"look")
                agua_s = {"go":"111111","take":"001100","put":"110011","open":"101010",
                          "clean":"010101","heat":"111000","cool":"000111","use":"100100","look":"000000"}.get(prim,"000000")
                sig = "".join("1" if v>0.5 else "0" for v in yao)
                ga = sum(1 for a,b in zip(agua_s,sig) if a==b)/6.0
                final = lin * favor * (0.75+0.25*sim) * (0.92+0.08*ga)
                cands.append((cmd, final, HXN[bi], sim))
            cands.sort(key=lambda x: x[1], reverse=True)
            obs, info = env.step(cands[0][0])
            won = bool(info.get("won",False))
            adm = info.get("admissible_commands",["look"])
            agent.observe_transition(cands[0][0], obs, adm, won=won)
            if won or info.get("done",False): break
        
        e = int(time.time()-t0)
        print(f"[{gi:3d}] {'W' if won else 'L'} s={step+1:2d} t={e:4d}s hx={cands[0][2]} | {task[:60]}")
        sys.stdout.flush()
        results.append({"gi":gi,"won":won,"steps":step+1,"task":task})
    
    nw = sum(1 for r in results if r['won'])
    print(f"\n【量子匹配v3：指数编码+酉演化】{len(results)}局: {nw}/{len(results)}={nw/max(len(results),1)*100:.1f}%")
    
    if args.output:
        with open(args.output,"w") as f:
            json.dump({"mode":"quantum_match_v3","beta":BETA,"results":results}, f, indent=2)

if __name__ == "__main__":
    main()
