#!/usr/bin/env python3
"""
run_v20_eval.py — V20 汉字YLYW Agent 评估入口

与 run_v18_eval.py 相同接口，但使用 CnWorldModel（汉字+YLYW卦象）。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))

MAX_STEPS = 50
AGENT_INFO_WHITELIST = ("task_desc", "admissible_commands")


def agent_view(info: dict) -> dict:
    return {k: info.get(k) for k in AGENT_INFO_WHITELIST}


def run_single(env, agent, game_idx: int) -> dict:
    obs, info = env.reset(game_idx=game_idx)
    view = agent_view(info)
    task_desc = view.get("task_desc") or ""
    admissible = view.get("admissible_commands") or ["look"]

    agent.reset(task_desc, obs, admissible, game_id=game_idx)

    won = False
    steps = 0
    actions = []
    for _ in range(MAX_STEPS):
        action = agent.act(obs, admissible)
        actions.append(action)
        obs, info = env.step(action)
        steps += 1
        won = bool(info.get("won", False))
        admissible = (agent_view(info).get("admissible_commands")) or ["look"]
        agent.observe_transition(action, obs, admissible, won=won)
        if won or info.get("done", False):
            break

    infl = agent.influence_stats()
    return {
        "game_idx": game_idx,
        "won": won,
        "steps": steps,
        "actions": actions,
        "task_type_real": info.get("task_type", ""),
        "task_desc": task_desc,
        "parsed_goal": agent.goal.as_dict() if agent.goal else {},
        "influence": infl,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="valid_seen")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=10)
    ap.add_argument("--games", default="")
    ap.add_argument("--priors", default="")
    ap.add_argument("--output", default="v20/results.json")
    ap.add_argument("--logjsonl", default="")
    ap.add_argument("--ablation", default="full")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.priors:
        os.environ["YLYW_PRIORS_PATH"] = os.path.abspath(args.priors)
    
    from alfworld_official_wrapper import ALFWorldOfficial
    from v20.agent_v20 import AgentV20
    import train_priors as _tp
    print(f"[priors] loaded from: {_tp._PATH}")

    env = ALFWorldOfficial(split=args.split)
    n = env.num_games
    end = min(args.end, n)

    if args.games.strip():
        game_range = [int(x) for x in args.games.split(",") if x.strip() != ""]
    else:
        game_range = list(range(args.start, end))

    logpath = args.logjsonl or None
    if logpath and os.path.exists(logpath):
        os.remove(logpath)

    results = []
    t0 = time.time()
    for gi in game_range:
        agent = AgentV20(log_path=logpath, verbose=args.verbose,
                         ylyw_mode=args.ablation)
        try:
            r = run_single(env, agent, gi)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = {"game_idx": gi, "won": False, "steps": MAX_STEPS,
                 "error": str(e), "actions": []}
        if logpath:
            agent.dump_logs(extra={"won": r["won"]})
        results.append(r)
        tag = "WON " if r["won"] else "lost"
        print(f"[{gi:3d}] {tag} steps={r['steps']:2d} "
              f"type={r.get('task_type_real', ''):32s} :: {r.get('task_desc', '')[:50]}")
        
        # 每10局中间保存一次
        if len(results) % 10 == 0:
            try:
                from v20.gua_knowledge_base import save_knowledge
                save_knowledge()
            except Exception:
                pass

    n_won = sum(1 for r in results if r["won"])
    n_tot = len(results)
    by_type = {}
    for r in results:
        t = r.get("task_type_real", "?")
        by_type.setdefault(t, [0, 0])
        by_type[t][1] += 1
        if r["won"]:
            by_type[t][0] += 1

    summary = {
        "split": args.split,
        "range": [args.start, end],
        "success_rate": n_won / n_tot if n_tot else 0.0,
        "n_won": n_won,
        "n_total": n_tot,
        "by_type": {k: {"won": v[0], "total": v[1],
                        "rate": v[0] / v[1] if v[1] else 0.0}
                    for k, v in by_type.items()},
        "ablation": args.ablation,
        "wall_time_s": round(time.time() - t0, 1),
        "results": results,
        "note": "V20: CnWorldModel (汉字+YLYW卦象) replaces V18 WorldModel (正则英文)",
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    # 最终保存知识库
    try:
        from v20.gua_knowledge_base import save_knowledge
        save_knowledge()
    except Exception:
        pass
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # 打印知识库统计
    try:
        from v20.gua_knowledge_base import get_knowledge
        kbs = get_knowledge().stats()
        print(f"知识库统计: {kbs['handcrafted']}条先验 + {kbs['learned']}条学习")
    except Exception:
        pass
    
    print("\n" + "=" * 60)
    print(f"V20 SPLIT={args.split}  games[{args.start}:{end}]  "
          f"SUCCESS {n_won}/{n_tot} = {summary['success_rate']*100:.1f}%")
    for k, v in summary["by_type"].items():
        print(f"   {k:34s} {v['won']}/{v['total']} = {v['rate']*100:.0f}%")
    print(f"wall={summary['wall_time_s']}s  -> {args.output}")


if __name__ == "__main__":
    main()
