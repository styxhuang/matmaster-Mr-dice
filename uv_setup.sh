#!/bin/bash
# UV 项目初始化脚本

set -e

echo "🚀 初始化 Mr-Dice 项目..."

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ 未找到 uv，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "✅ UV 已安装"

# 同步依赖（包括开发依赖）
echo "📦 同步项目依赖..."
uv sync --group dev

# 检查是否需要安装内部依赖
if python -c "import dp.agent" 2>/dev/null; then
    echo "✅ dp.agent 已安装"
else
    echo "⚠️  警告: dp.agent 未找到"
    echo "   如果这是内部包，请手动安装:"
    echo "   pip install bohr-agent-sdk"
    echo "   或使用其他方式安装 dp.agent"
fi

echo ""
echo "✅ 项目初始化完成！"
echo ""
echo "运行项目:"
echo "  uv run python -m mrdice_server.server"
echo ""
echo "运行调试服务器:"
echo "  uv run uvicorn mrdice_server.debug_server:app --reload --host 0.0.0.0 --port 50001"
echo ""

