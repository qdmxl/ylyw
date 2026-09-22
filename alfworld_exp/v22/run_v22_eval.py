#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_v22_eval.py — V22 知几式可学习H Agent 评估入口

对比实验设计：
  静态H（V21, alpha=0） vs 知几式可学习H（V22, 跨局共享θ）

V22特有：
  - 一局结束后 commit_game(won) 校准θ（知几频率+灵敏度归因）
  - 若 --share 打开，用同一个agent跨局累积θ（知几跨局学习）
"""
from __future__ import annotations
import argparse, json, os, sys, time

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
    won = False; steps = 0; actions = []
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
    return {"game_idx": game_idx, "won": won, "steps": steps,
            "actions": actions, "task_desc": task_desc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="valid_seen")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=20)
    ap.add_argument("--games", default="")
    ap.add_argument("--output", default="v22/results.json")
    ap.add_argument("--alpha_q", type=float, default=0.08)
    ap.add_argument("--alpha_s", type=float, default=0.03)
    ap.add_argument("--share", action="store_true",  # 跨局共享θ（知几跨局学习）
                    help="share one agent across games (accumulate θ learn)")
    ap.add_argument("--exp_path", default="v22/exp_learnable_h.json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    from alfworld_official_wrapper import ALFWorldOfficial
    from v22.agent_v22 import AgentV22

    # 实验独立：清空经验文件，避免不同次运行的跨局积累污染
    if args.exp_path and os.path.exists(args.exp_path):
        os.remove(args.exp_path)

    env = ALFWorldOfficial(split=args.split)
    n = env.num_games
    end = min(args.end, n)
    if args.games.strip():
        game_range = [int(x) for x in args.games.split(",") if x.strip() != ""]
    else:
        game_range = list(range(args.start, end))

    # 跨局共享时用同一个agent；否则每局新建（对比V21行为）
    agent = None
    results = []
    theta_history = []
    t0 = time.time()
    for gi in game_range:
        if agent is None:
            agent = AgentV22(log_path=None, verbose=args.verbose,
                             ylyw_mode="full", alpha_q=args.alpha_q,
                             alpha_s=args.alpha_s, experience_path=args.exp_path)
        r = run_single(env, agent, gi)
        # 局末提交：commit_game 在 observe_transition 或 dump_logs 已触发。
        # 若该局被MAX_STEPS截断且未done（won_reported未置位），补一次 commit(won*)
        if not getattr(agent, '_won_reported', False):
            agent.scorer.commit_game(won=r["won"])
            agent._won_reported = True
        results.append(r)
        theta_history.append(dict(agent.scorer.theta_dict()) if hasattr(agent.scorer, 'theta_dict') else {})
        agent._won_reported = False  # 下一局重置
        if not args.share:
            agent = None  # 每局新建（不跨局学习）
        tag = "WON " if r["won"] else "lost"
        print(f"[{gi:3d}] {tag} steps={r['steps']:2d} θ={theta_history[-1]} :: {r['task_desc'][:45]}",
              flush=True)

    n_won = sum(1 for r in results if r["won"])
    n_tot = len(results)
    by_type = {}
    for r in results:
        t = "?"; by_type.setdefault(t, [0, 0]); by_type[t][1] += 1
        if r["won"]: by_type[t][0] += 1

    summary = {
        "split": args.split, "range": [args.start, end],
        "success_rate": n_won / n_tot if n_tot else 0.0,
        "n_won": n_won, "n_total": n_tot,
        "share": args.share, "alpha_q": args.alpha_q, "alpha_s": args.alpha_s,
        "theta_history": theta_history,
        "results": [{ "game_idx": r["game_idx"], "won": r["won"], "steps": r["steps"]}
                    for r in results],
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 60)
    print(f"V22 split={args.split} share={args.share} games[{args.start}:{end}] "
          f"SUCCESS {n_won}/{n_tot} = {summary['success_rate']*100:.1f}%")
    print(f"wall={time.time()-t0:.0f}s -> {args.output}")


if __name__ == "__main__":
    main()
