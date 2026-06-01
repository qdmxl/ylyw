#!/bin/bash
# YLYW 仿真调试脚本 - 捕获错误信息
cd /home/lijinhan/MXL/科研/ylyw

echo "====== YLYW 仿真调试 $(date) ======" | tee /tmp/ylyw_debug.log
echo "DISPLAY=$DISPLAY" | tee -a /tmp/ylyw_debug.log
echo "XAUTHORITY=$XAUTHORITY" | tee -a /tmp/ylyw_debug.log
echo "PYTHON=$(which python3)" | tee -a /tmp/ylyw_debug.log
echo "---" | tee -a /tmp/ylyw_debug.log

python3 scripts/demo_feature_extraction.py 2>&1 | tee -a /tmp/ylyw_debug.log
EXIT_CODE=$?

echo "---" | tee -a /tmp/ylyw_debug.log
echo "退出码: $EXIT_CODE" | tee -a /tmp/ylyw_debug.log

if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ 脚本异常退出！请查看 /tmp/ylyw_debug.log" | tee -a /tmp/ylyw_debug.log
fi
