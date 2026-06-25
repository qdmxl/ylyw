#!/usr/bin/env python3
"""
ALFWorld + 即时翻译层 集成测试

测试完整流程：
1. 英文场景描述 → 中文 (Agent 看到的)
2. 中文命令 → 英文 → 发送到 ALFWorld 执行
3. 英文反馈 → 中文 (Agent 看到的)
"""

import sys
sys.path.insert(0, '/home/lijinhan/MXL/科研/ylyw/alfworld_translator')

from alfred_translator import ALFWorldTranslator, translate_command_to_zh
import os
import json
import argparse
import numpy as np
import yaml

# ALFWorld imports
os.environ['ALFWORLD_DATA'] = os.path.expanduser('~/.cache/alfworld')

from alfworld.agents.environment import get_environment


def load_config():
    config_path = '/home/lijinhan/alfworld_venv/lib/python3.14/site-packages/alfworld/agents/config/base_config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)
    config['env']['domain_randomization'] = False
    return config


def main():
    translator = ALFWorldTranslator(verbose=False)

    config = load_config()
    config['dataset']['data_path'] = os.path.join(
        os.environ['ALFWORLD_DATA'], 'json_2.1.1', 'train'
    )
    config['dataset']['num_train_games'] = 50  # 限制游戏数量

    env = get_environment('AlfredTWEnv')(config, train_eval='train')
    env = env.init_env(batch_size=1)

    print("=" * 70)
    print("  ALFWorld + YLYW 即时翻译层 集成测试")
    print("=" * 70)

    num_episodes = 3
    for ep in range(num_episodes):
        print(f"\n{'='*70}")
        print(f"  第 {ep+1} / {num_episodes} 个任务")
        print(f"{'='*70}")

        obs, info = env.reset()
        obs_text = obs[0]

        # 翻译 → 中文
        zh_obs = translator.observe(obs_text)

        # 翻译任务目标
        goal_match = None
        for line in obs_text.split('\n'):
            if 'Your task is' in line:
                goal_match = line.strip()
                break
        if goal_match:
            zh_goal = translator.translate_goal(goal_match)
            print(f"\n📋 任务: {zh_goal}")

        print(f"\n🌍 中文场景:")
        print(zh_obs)

        max_steps = 12
        for step in range(max_steps):
            admissible = info.get('admissible_commands', [[]])[0]
            zh_commands = translator.translate_commands(admissible)

            print(f"\n🎯 可选动作 (前8个):")
            for i, (en_cmd, zh_cmd) in enumerate(zip(admissible[:8], zh_commands[:8])):
                print(f"  [{i}] {zh_cmd:30s} ← {en_cmd}")

            # 随机选择
            random_idx = np.random.randint(len(admissible))
            chosen_en = admissible[random_idx]
            chosen_zh = zh_commands[random_idx]
            print(f"  → 执行: '{chosen_zh}' ({chosen_en})")

            obs, scores, dones, info = env.step([chosen_en])
            obs_text = obs[0]
            done = dones[0]

            zh_result = translator.observe(obs_text)
            print(f"📝 {zh_result}")

            if done:
                score = scores[0]
                emoji = '🎉' if score > 0 else '❌'
                print(f"\n{emoji} 任务{'成功' if score > 0 else '失败'} (score={score})")
                break

    print(f"\n{'='*70}")
    print("  ✅ 集成测试完成!")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
