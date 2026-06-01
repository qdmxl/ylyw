#!/usr/bin/env bash
# YLYW 版本管理快捷脚本
# 用法: bash scripts/version_save.sh <类型> <版本号> "<描述>"
#
# 示例:
#   bash scripts/version_save.sh exp centroid-opt "爻模板质心优化完成，300物体91.7%"
#   bash scripts/version_save.sh paper v0.5 "新增物理约束层章节"
#   bash scripts/version_save.sh release v3.0 "阶段二完成：物理约束层 + 推物实验"

set -e

TYPE=${1:?请指定类型: exp/paper/release}
VERSION=${2:?请指定版本号}
DESC=${3:?请指定描述}

TAG="${TYPE}/${VERSION}"
DATE=$(date '+%Y-%m-%d %H:%M')
ROOT=$(cd "$(dirname "$0")/.." && pwd)

export GIT_DIR="$ROOT/.git"
export GIT_WORK_TREE="$ROOT"

echo "════════════════════════════════════"
echo "  YLYW 版本保存"
echo "════════════════════════════════════"
echo "  类型: $TYPE"
echo "  版本: $VERSION"
echo "  标签: $TAG"
echo "  日期: $DATE"
echo "  描述: $DESC"
echo "════════════════════════════════════"

# 显示变更
echo ""
echo "▎变更文件:"
git status --short

# 确认
read -p "确认提交并打标签 $TAG? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "已取消"
    exit 0
fi

# 提交
git add -A
git commit -m "$TAG: $DESC" || echo "(无新变更，仅打标签)"

# 打标签
git tag -f "$TAG"

# 自动追加到 VERSIONS.md
echo "" >> "$ROOT/VERSIONS.md"
echo "### $TAG — $DESC" >> "$ROOT/VERSIONS.md"
echo "- **日期**: $DATE" >> "$ROOT/VERSIONS.md"
echo "- **Tag**: \`$TAG\`" >> "$ROOT/VERSIONS.md"
git add "$ROOT/VERSIONS.md"
git commit -m "docs: 更新VERSIONS.md ($TAG)" || true

echo ""
echo "✅ 版本已保存: $TAG"
echo ""
echo "▎所有版本:"
git tag -l
