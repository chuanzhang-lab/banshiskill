#!/bin/bash
# Context-Compressor 一键启动脚本
# 用法：bash setup.sh
# 自动切到脚本所在目录，避免路径问题

set -e  # 出错就退出

# 自动 cd 到脚本所在目录（解决"在 ~ 下执行"问题）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> 当前目录: $SCRIPT_DIR"
echo ""

echo "==> 1. 安装依赖"
python3 -m pip install -r requirements.txt
echo ""

echo "==> 2. 生成工件"
python3 parse_skill.py
python3 skill_compressor.py
python3 compress.py --skill-md SKILL.md
echo ""

echo "==> 3. 运行测试"
python3 -m pytest test_compress.py -v
echo ""

echo "==> 4. 代码质量"
python3 -m ruff check .
python3 -m ruff format --check .
echo ""

echo "✅ 全部完成"
