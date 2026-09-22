#!/usr/bin/env python3
"""
马老师方案：6量子位酉演化替代cosine模板匹配

保留经典YLYW的：
1. 汉字部首→八卦（HanziEngine）
2. 六爻构建规则（二进制状态驱动）

仅替换：
3. 六爻→卦象匹配（cosine模板匹配 → 6量子位酉演化）
4. 评分逻辑（单卦favorability → 全谱概率×吉凶加权）
"""
from __future__ import annotations
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))

import numpy as np

# ===== 6量子位酉演化器（乘承比应耦合） =====
I2 = np.eye(2, dtype=complex)
Z = np.array([[1,0],[0,-1]], dtype=complex)
X = np.array([[0,1],[1,0]], dtype=complex)

def _pauli_op(ops):
    r = ops[-1].copy()
    for o in reversed(ops[:-1]):
        r = np.kron(r, o)
    return r

def _clip(x):
    return max(0.05, min(0.95, x))

FAV64 = np.array([
    0.66,0.38,0.42,0.55,0.70,0.32,0.56,0.48,
    0.74,0.48,0.36,0.78,0.32,0.52,0.52,0.58,
    0.46,0.58,0.38,0.58,0.36,0.56,0.56,0.70,
    0.52,0.38,0.36,0.68,0.32,0.58,0.72,0.46,
    0.52,0.58,0.52,0.36,0.72,0.46,0.42,0.72,
    0.36,0.54,0.52,0.74,0.54,0.56,0.60,0.48,
    0.74,0.58,0.56,0.48,0.38,0.58,0.32,0.52,
    0.52,0.56,0.48,0.48,0.92,0.54,0.54,0.54,
])

HEX_NAMES = ['乾','坤','屯','蒙','需','讼','师','比','小畜','履','泰','否','同人','大有','谦','豫',
             '随','蛊','临','观','噬嗑','贲','剥','复','无妄','大畜','颐','大过','坎','离','咸','恒',
             '遁','大壮','晋','明夷','家人','睽','蹇','解','损','益','夬','姤','萃','升','困','井',
             '革','鼎','震','艮','渐','归妹','丰','旅','巽','兑','涣','节','中孚','小过','既济','未济']


def build_H(tau=0.5):
    """构建乘承比应哈密顿量，返回酉矩阵U和FAV64"""
    H = np.zeros((64,64), dtype=complex)
    
    # 单爻能级（基于爻位意义）
    h = np.array([0.3, 0.5, 0.7, 0.5, 0.8, 0.4])
    for i in range(6):
        ops = [Z if q==i else I2 for q in range(6)]
        H += h[i] * _pauli_op(ops)
        ops_x = [X if q==i else I2 for q in range(6)]
        H += 0.15 * _pauli_op(ops_x)
    
    # 乘承比应耦合
    J = {
        (0,1):0.6, (1,2):0.6, (2,3):0.8, (3,4):0.6, (4,5):0.8,  # 乘（下对上）
        (1,0):0.4, (2,1):0.4, (3,2):0.6, (4,3):0.4, (5,4):0.6,  # 承（上对下）
        (0,2):0.25, (1,3):0.25, (2,4):0.25, (3,5):0.25,          # 比（隔位）
        (0,3):0.35, (1,4):0.35, (2,5):0.35,                       # 应（初四/二五/三六）
    }
    for (i,j), v in J.items():
        ops = [Z if q in (i,j) else I2 for q in range(6)]
        H += v * _pauli_op(ops)
    
    # 三体纠缠（"三生万物"）
    for tri in [(0,1,2), (1,2,3), (2,3,4), (3,4,5)]:
        ops = [Z if q in tri else I2 for q in range(6)]
        H += 0.08 * _pauli_op(ops)
    
    # 酉化
    evals, evecs = np.linalg.eigh(H)
    U_diag = np.diag(np.exp(-1j * tau * evals))
    U = evecs @ U_diag @ evecs.conj().T
    return U


def quantum_match(yao_vec, U):
    """六爻 → 6量子位酉演化 → 64维概率分布"""
    # 六爻编码为初态（Z旋转）
    psi = np.ones(64, dtype=complex) / 8.0
    for i in range(6):
        val = _clip(yao_vec[i])
        angle = np.pi * (1.0 - val)
        Rz = np.array([[np.exp(-1j*angle/2),0],[0,np.exp(1j*angle/2)]], dtype=complex)
        ops = [Rz if q==i else I2 for q in range(6)]
        psi = _pauli_op(ops) @ psi
    
    # 酉演化
    psi = U @ psi
    probs = np.abs(psi)**2
    probs /= (probs.sum() + 1e-12)
    return probs


def quantize(yao_vec, U):
    """六爻→量子评分（全谱概率×吉凶加权）"""
    probs = quantum_match(yao_vec, U)
    q_score = float(np.sum(probs * FAV64))
    dom_idx = int(np.argmax(probs))
    dom_prob = float(probs[dom_idx])
    return q_score, dom_idx, dom_prob, probs


# ===== 主评估 =====
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--split", default="valid_seen")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    
    from alfworld_official_wrapper import ALFWorldOfficial
    from v21.agent_v21 import AgentV21
    import train_priors as _tp
    print(f"[priors] {_tp._PATH}")
    
    print("构建6量子位哈密顿量...")
    U = build_H(args.tau)
    print(f"酉矩阵: {U.shape[0]}×{U.shape[1]}, tau={args.tau}")
    
    env = ALFWorldOfficial(split=args.split)
    results = []
    t0 = time.time()
    
    for gi in range(args.start, args.start + args.games):
        obs, info = env.reset(game_idx=gi)
        task_desc = info.get("task_desc", "")
        adm = info.get("admissible_commands", ["look"])
        
        agent = AgentV21(verbose=False)
        agent.reset(task_desc, obs, adm, game_id=gi)
        # 强制用原始v18的build_yao（通过QYUFScorer的委托）
        
        won = False
        for step in range(50):
            phase = agent._phase()
            candidates = []
            
            for cmd in adm:
                parsed = agent.scorer._parse_action(cmd)
                yao = agent.scorer.build_yao(parsed, agent.world, agent.goal, phase)
                vec = np.array(yao, dtype=float)
                
                q_score, dom_idx, dom_prob, probs = quantize(vec, U)
                
                # 量子评分 = 全谱吉凶 × 线性基线 × 主导概率调整
                lin = float(np.dot(vec, np.array([0.18,0.25,0.20,0.15,0.12,0.10])))
                final = q_score * (0.3 + 0.7 * lin) * (0.4 + 0.6 * dom_prob)
                candidates.append((cmd, final, q_score, dom_idx, yao))
            
            candidates.sort(key=lambda x: x[1], reverse=True)
            action = candidates[0][0]
            
            obs, info = env.step(action)
            won = bool(info.get("won", False))
            adm = info.get("admissible_commands", ["look"])
            agent.observe_transition(action, obs, adm, won=won)
            if won or info.get("done", False):
                break
        
        elapsed = int(time.time() - t0)
        tag = "W" if won else "L"
        dom_hex = HEX_NAMES[candidates[0][3]]
        print(f"[{gi:3d}] {tag} s={step+1:2d} t={elapsed:4d}s hx={dom_hex} | {task_desc[:60]}")
        sys.stdout.flush()
        results.append({"gi": gi, "won": won, "steps": step+1, "task": task_desc})
    
    n_won = sum(1 for r in results if r["won"])
    total = len(results)
    print(f"\n【量子匹配版：6位酉演化替cosine模板匹配】{total}局: {n_won}/{total}={n_won/max(total,1)*100:.1f}%")
    
    # 经典版对比
    print("--- 经典版对比 ---")
    from v18.ylyw_scorer import YLYWScorer
    original = YLYWScorer()
    results_c = []
    for gi in range(args.start, args.start + args.games):
        obs, info = env.reset(game_idx=gi)
        task_desc = info.get("task_desc", "")
        adm = info.get("admissible_commands", ["look"])
        agent = AgentV21(verbose=False)
        agent.reset(task_desc, obs, adm, game_id=gi)
        won = False
        for step in range(50):
            phase = agent._phase()
            candidates = []
            for cmd in adm:
                cand = original.score_candidate(cmd, agent.world, agent.goal, phase)
                candidates.append((cmd, cand.ylyw_score, cand.hexagram, cand.yao))
            candidates.sort(key=lambda x: x[1], reverse=True)
            action = candidates[0][0]
            obs, info = env.step(action)
            won = bool(info.get("won", False))
            adm = info.get("admissible_commands", ["look"])
            agent.observe_transition(action, obs, adm, won=won)
            if won or info.get("done", False): break
        tag = "W" if won else "L"
        print(f"[C{gi:3d}] {tag} s={step+1:2d} | {task_desc[:60]}")
        results_c.append({"gi": gi, "won": won})
    
    nw_c = sum(1 for r in results_c if r["won"])
    print(f"\n经典版: {nw_c}/{total}={nw_c/max(total,1)*100:.1f}%")
    agree = sum(1 for r1,r2 in zip(results, results_c) if r1['won']==r2['won'])
    print(f"一致率: {agree}/{total}={agree/max(total,1)*100:.1f}%")
    print(f"量子胜经典败: {[r1['gi'] for r1,r2 in zip(results,results_c) if r1['won'] and not r2['won']]}")
    print(f"经典胜量子败: {[r1['gi'] for r1,r2 in zip(results,results_c) if not r1['won'] and r2['won']]}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump({"mode":"quantum_match","tau":args.tau,
                       "quantum":results,"classic":results_c}, f, indent=2)
        print(f"已保存到 {args.output}")

if __name__ == "__main__":
    main()
