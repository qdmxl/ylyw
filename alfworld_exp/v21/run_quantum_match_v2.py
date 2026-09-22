#!/usr/bin/env python3
"""
run_quantum_match_v2.py — 马老师方案 v2

仅替换 get_best_hexagram（cosine 模板匹配 → 6量子位酉演化的概率分布匹配）
保持评分公式完全不变。

关键技术决策：
- 不是用全谱吉凶加权，而是用量子演化的概率分布与64个标准模板做JS散度匹配
- 最佳卦 = 酉演化输出概率分布与标准卦模板概率分布的最小JS散度
- 保持 ylyw_score = lin * favor * (0.75+0.25*cos) * (0.92+0.08*gua_aff) 不变
- cos 由量子匹配的JS散度转换得到
"""
from __future__ import annotations
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))

import numpy as np

# ===== 6量子位酉演化器 =====
I2 = np.eye(2, dtype=complex); Z = np.array([[1,0],[0,-1]], dtype=complex)
X = np.array([[0,1],[1,0]], dtype=complex)

def _pauli_op(ops):
    r = ops[-1].copy()
    for o in reversed(ops[:-1]): r = np.kron(r, o)
    return r

def _clip(x): return max(0.05, min(0.95, x))

def build_quantum_unitary(tau=0.5):
    """构建乘承比应哈密顿量的酉算子"""
    H = np.zeros((64,64), dtype=complex)
    h = np.array([0.3, 0.5, 0.7, 0.5, 0.8, 0.4])
    for i in range(6):
        ops = [Z if q==i else I2 for q in range(6)]
        H += h[i] * _pauli_op(ops)
        ops_x = [X if q==i else I2 for q in range(6)]
        H += 0.15 * _pauli_op(ops_x)
    J = {(0,1):0.6,(1,2):0.6,(2,3):0.8,(3,4):0.6,(4,5):0.8,
         (1,0):0.4,(2,1):0.4,(3,2):0.6,(4,3):0.4,(5,4):0.6,
         (0,2):0.25,(1,3):0.25,(2,4):0.25,(3,5):0.25,
         (0,3):0.35,(1,4):0.35,(2,5):0.35}
    for (i,j), v in J.items():
        ops = [Z if q in (i,j) else I2 for q in range(6)]
        H += v * _pauli_op(ops)
    for tri in [(0,1,2),(1,2,3),(2,3,4),(3,4,5)]:
        ops = [Z if q in tri else I2 for q in range(6)]
        H += 0.08 * _pauli_op(ops)
    evals, evecs = np.linalg.eigh(H)
    U_diag = np.diag(np.exp(-1j*tau*evals))
    U = evecs @ U_diag @ evecs.conj().T
    return U

def quantum_yao_to_probs(yao_vec, U):
    """六爻 → 6量子位酉演化 → 64维概率分布"""
    psi = np.ones(64, dtype=complex)/8.0
    for i in range(6):
        val = _clip(yao_vec[i])
        angle = np.pi*(1.0-val)
        Rz = np.array([[np.exp(-1j*angle/2),0],[0,np.exp(1j*angle/2)]], dtype=complex)
        ops = [Rz if q==i else I2 for q in range(6)]
        psi = _pauli_op(ops) @ psi
    psi = U @ psi
    probs = np.abs(psi)**2
    probs /= (probs.sum()+1e-12)
    return probs


# ===== 预计算64个标准卦的量子概率分布模板 =====
def build_standard_hex_templates(U):
    """64标准六爻 → 酉演化 → 64维概率分布模板"""
    # 通行本64卦的标准六爻模板（从HexagramRules._get_ideal_yao_template提取）
    templates = {}
    template_list = [
        ("QIAN",   [0.75,0.61,0.59,0.76,0.45,0.65]), ("KUN",    [0.39,0.61,0.30,0.28,0.35,0.59]),
        ("ZHUN",   [0.31,0.57,0.46,0.54,0.38,0.57]), ("MENG",   [0.21,0.59,0.45,0.71,0.44,0.63]),
        ("XU",     [0.21,0.59,0.41,0.71,0.48,0.73]), ("SONG",   [0.14,0.86,0.15,0.85,0.80,0.20]),
        ("SHI",    [0.19,0.14,0.21,0.15,0.16,0.84]), ("BI",     [0.27,0.59,0.32,0.33,0.34,0.49]),
        ("XIAOXU", [0.42,0.64,0.25,0.36,0.33,0.65]), ("LU",     [0.34,0.56,0.34,0.22,0.33,0.58]),
        ("TAI",    [0.76,0.58,0.60,0.74,0.45,0.66]), ("PI",     [0.09,0.10,0.11,0.88,0.88,0.89]),
        ("TONGREN", [0.29,0.52,0.32,0.23,0.34,0.61]),("DAYOU",  [0.75,0.55,0.23,0.19,0.31,0.47]),
        ("QIAN",   [0.51,0.63,0.29,0.21,0.38,0.61]), ("YU",     [0.25,0.62,0.41,0.70,0.49,0.71]),
        ("SUI",    [0.23,0.60,0.41,0.71,0.46,0.74]), ("GU",     [0.33,0.55,0.53,0.66,0.47,0.69]),
        ("LIN",    [0.46,0.63,0.23,0.39,0.35,0.64]), ("GUAN",   [0.53,0.56,0.28,0.21,0.32,0.60]),
        ("SHIHE",  [0.29,0.55,0.44,0.51,0.39,0.57]), ("BO",     [0.74,0.56,0.21,0.19,0.30,0.46]),
        ("FU",     [0.39,0.60,0.30,0.22,0.36,0.64]), ("WUWANG", [0.74,0.58,0.62,0.77,0.43,0.68]),
        ("DACHU",  [0.77,0.58,0.59,0.78,0.46,0.64]), ("YI",     [0.34,0.64,0.50,0.68,0.50,0.77]),
        ("DAGUO",  [0.55,0.59,0.57,0.71,0.43,0.61]), ("KAN",    [0.28,0.57,0.33,0.37,0.36,0.51]),
        ("LI",     [0.76,0.57,0.24,0.19,0.33,0.46]), ("XIAN",   [0.34,0.57,0.32,0.21,0.36,0.61]),
        ("HENG",   [0.36,0.62,0.49,0.65,0.47,0.79]), ("DUN",    [0.12,0.12,0.88,0.88,0.89,0.88]),
        ("DAZHUANG",[0.53,0.56,0.58,0.71,0.44,0.64]),("JIN",    [0.43,0.60,0.28,0.21,0.35,0.66]),
        ("MINGYI", [0.56,0.54,0.27,0.13,0.35,0.60]), ("JIAREN", [0.32,0.55,0.35,0.23,0.35,0.60]),
        ("KUI",    [0.34,0.52,0.59,0.68,0.44,0.59]), ("JIAN",   [0.34,0.52,0.57,0.69,0.44,0.58]),
        ("XIE",    [0.35,0.52,0.58,0.70,0.42,0.63]), ("SUN",    [0.51,0.60,0.28,0.23,0.35,0.61]),
        ("YI_GUA", [0.39,0.66,0.22,0.40,0.36,0.68]), ("GUAI",   [0.75,0.55,0.63,0.80,0.39,0.70]),
        ("GOU",    [0.22,0.59,0.48,0.74,0.45,0.61]), ("CUI",    [0.19,0.11,0.23,0.14,0.15,0.83]),
        ("SHENG",  [0.47,0.66,0.24,0.38,0.37,0.65]), ("KUN_GUA",[0.30,0.53,0.57,0.71,0.42,0.60]),
        ("JING",   [0.91,0.86,0.18,0.13,0.10,0.12]), ("GE",     [0.37,0.53,0.55,0.65,0.48,0.70]),
        ("DING",   [0.76,0.56,0.61,0.70,0.43,0.64]), ("ZHEN",   [0.25,0.59,0.43,0.71,0.50,0.74]),
        ("GEN",    [0.87,0.85,0.16,0.12,0.11,0.12]), ("JIAN_GUA",[0.47,0.59,0.24,0.18,0.32,0.66]),
        ("GUIMEI", [0.35,0.52,0.60,0.73,0.40,0.66]), ("FENG",   [0.54,0.58,0.58,0.74,0.47,0.64]),
        ("LU_GUA", [0.22,0.60,0.40,0.69,0.49,0.75]), ("XUN",    [0.33,0.53,0.57,0.71,0.42,0.63]),
        ("DUI",    [0.59,0.61,0.24,0.28,0.34,0.56]), ("HUAN",   [0.08,0.88,0.07,0.10,0.05,0.11]),
        ("JIE",    [0.49,0.60,0.29,0.21,0.32,0.64]), ("ZHONGFU",[0.33,0.57,0.34,0.19,0.33,0.59]),
        ("XIAOGUO",[0.42,0.49,0.33,0.60,0.42,0.62]), ("JIJI",   [0.92,0.10,0.89,0.10,0.93,0.10]),
        ("WEIJI",  [0.07,0.88,0.11,0.07,0.06,0.11]),
    ]
    # 去重（保留第一个）
    seen = set()
    for name, yao in template_list:
        if name not in seen:
            seen.add(name)
            probs = quantum_yao_to_probs(np.array(yao), U)
            templates[name] = probs
    return templates

def js_divergence(p, q):
    pu = p.flatten()+1e-12; pu /= pu.sum()
    qu = q.flatten()+1e-12; qu /= qu.sum()
    m = 0.5*(pu+qu)
    return 0.5*(np.sum(pu*np.log(pu/m))+np.sum(qu*np.log(qu/m)))

def quantum_get_best_hexagram(yao_vec, U, templates):
    """量子版get_best_hexagram：酉演化→64维概率分布→与各卦模板的JS散度比较"""
    probs = quantum_yao_to_probs(yao_vec, U)
    best_name = None
    best_js = 999.0
    for name, tpl in templates.items():
        js = js_divergence(probs, tpl)
        if js < best_js:
            best_js = js
            best_name = name
    # JS → cosine-like (JS=0→完全匹配→cos=1)
    sim = max(0.0, 1.0 - best_js * 3.0)
    return best_name, sim


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
    
    print("构建6量子位酉演化器 + 64卦概率模板...")
    U = build_quantum_unitary(args.tau)
    templates = build_standard_hex_templates(U)
    print(f"酉矩阵: {U.shape[0]}×{U.shape[1]}, 模板数: {len(templates)}")
    
    # 验证：对一个随机六爻，量子匹配是否与经典一致
    print("\n验证量子匹配 vs 经典匹配:")
    from v18.ylyw_scorer import YLYWScorer, Hexagram
    classic_hr = YLYWScorer().hr
    test_yao = np.array([0.3, 0.6, 0.5, 0.4, 0.5, 0.7])
    cl_hx, cl_cos = classic_hr.get_best_hexagram(test_yao)
    q_name, q_sim = quantum_get_best_hexagram(test_yao, U, templates)
    print(f"  经典: {cl_hx.name} (cos={cl_cos:.4f})")
    print(f"  量子: {q_name} (sim={q_sim:.4f})")
    
    # 名字映射（经典枚举名 → 模板名）
    name_map_inv = {hx.name: hx for hx in Hexagram}
    template_names = set(templates.keys())
    
    env = ALFWorldOfficial(split=args.split)
    results = []
    t0 = time.time()
    
    for gi in range(args.start, args.start + args.games):
        obs, info = env.reset(game_idx=gi)
        task_desc = info.get("task_desc","")
        adm = info.get("admissible_commands",["look"])
        agent = AgentV21(verbose=False)
        agent.reset(task_desc, obs, adm, game_id=gi)
        
        won = False
        for step in range(50):
            phase = agent._phase()
            candidates = []
            for cmd in adm:
                parsed = agent.scorer._parse_action(cmd)
                yao = agent.scorer.build_yao(parsed, agent.world, agent.goal, phase)
                vec = np.array(yao, dtype=float)
                
                # 量子匹配
                q_name, q_sim = quantum_get_best_hexagram(vec, U, templates)
                
                # 使用经典评分公式但替换cos为q_sim
                if q_name in name_map_inv:
                    hx = name_map_inv[q_name]
                else:
                    # fallback: 找最接近
                    hx, _ = classic_hr.get_best_hexagram(vec)
                
                favor = float(YLYWScorer()._fav[hx.value])
                lin = float(np.dot(vec, np.array([0.18,0.25,0.20,0.15,0.12,0.10])))
                
                # Action gua affinity
                prim = {"go":"go","take":"take","put":"put","open":"open","clean":"clean",
                        "heat":"heat","cool":"cool","use":"use","look":"look","help":"look","inventory":"look"}.get(parsed["verb"],"look")
                agua_str = {"go":"111111","take":"001100","put":"110011","open":"101010",
                            "clean":"010101","heat":"111000","cool":"000111","use":"100100","look":"000000"}
                agua = agua_str.get(prim,"000000")
                sig = "".join("1" if v>0.5 else "0" for v in yao)
                gua_aff = sum(1 for a,b in zip(agua,sig) if a==b)/6.0
                
                final = lin * favor * (0.75 + 0.25*q_sim) * (0.92 + 0.08*gua_aff)
                candidates.append((cmd, final, q_name, q_sim, yao))
            
            candidates.sort(key=lambda x: x[1], reverse=True)
            action = candidates[0][0]
            
            obs, info = env.step(action)
            won = bool(info.get("won",False))
            adm = info.get("admissible_commands",["look"])
            agent.observe_transition(action, obs, adm, won=won)
            if won or info.get("done",False): break
        
        elapsed = int(time.time()-t0)
        tag = "W" if won else "L"
        print(f"[{gi:3d}] {tag} s={step+1:2d} t={elapsed:4d}s hx={candidates[0][2]} | {task_desc[:60]}")
        sys.stdout.flush()
        results.append({"gi":gi,"won":won,"steps":step+1,"task":task_desc})
    
    n_won = sum(1 for r in results if r['won'])
    total = len(results)
    print(f"\n【量子匹配v2（JS散度+cosine公式不变）】{total}局: {n_won}/{total}={n_won/max(total,1)*100:.1f}%")
    
    if args.output:
        with open(args.output,"w") as f:
            json.dump({"mode":"quantum_match_v2","tau":args.tau,"results":results}, f, indent=2)

if __name__ == "__main__":
    main()
