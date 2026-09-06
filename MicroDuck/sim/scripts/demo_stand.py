#!/usr/bin/env python3
"""MicroDuck 站立保持演示 + 回归测试(ylyw 基座验证)。

用法:
    python scripts/demo_stand.py            # 跑 4s 保持,打印稳定性报告
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.microduck_env import StandingEnv, ensure_control_model


def main():
    xml = ensure_control_model()
    print(f"控制友好模型: {xml}")
    env = StandingEnv(xml_path=xml, control_dt=0.02)
    print(f"机器人: nu={env.model.nu} 关节={env.action_size} 关键帧数={env.model.nkey}")
    # 展示关节/执行器映射
    print("伺服映射 servo->actuator:", env._servo_act_idx)
    rep = env.run_hold(seconds=4.0)
    print("\n=== 站立保持报告(4 秒) ===")
    for k, v in rep.items():
        print(f"  {k:16s}: {v}")
    ok = rep["stable"]
    print("\n结果:", "PASS —— 机器人能稳定站立,基座可用" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
