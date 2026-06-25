#!/bin/bash
# YLYW书法论文编译脚本
# 需要: xelatex + Noto CJK字体
# 安装: sudo apt install texlive-xetex texlive-latex-extra fonts-noto-cjk

PAPER_DIR="/home/lijinhan/MXL/科研/ylyw/calligraphy"
cd "$PAPER_DIR"

echo "=== YLYW 书法学习论文编译 ==="
echo ""

# 检查依赖
if ! command -v xelatex &> /dev/null; then
    echo "❌ xelatex 未安装"
    echo "   安装: sudo apt install texlive-xetex texlive-latex-extra fonts-noto-cjk"
    exit 1
fi

# 编译
echo "📝 编译 paper_complete.tex ..."
xelatex -interaction=nonstopmode paper_complete.tex
xelatex -interaction=nonstopmode paper_complete.tex  # 两次以解决交叉引用

# 检查结果
if [ -f "paper_complete.pdf" ]; then
    echo "✅ 论文PDF已生成: $PAPER_DIR/paper_complete.pdf"
    ls -lh paper_complete.pdf
else
    echo "❌ 编译失败，查看 paper_complete.log"
    tail -30 paper_complete.log
fi
