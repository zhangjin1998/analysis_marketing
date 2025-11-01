#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                            ║"
echo "║     🤖 A股短线交易系统 - LLM Agent 快速安装脚本                           ║"
echo "║                                                                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 检查 Python 版本
echo "📋 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ 当前 Python: $python_version"
echo ""

# 安装依赖
echo "📦 安装 LangChain + OpenAI 依赖..."
pip install langchain>=0.1.0 openai>=1.0.0 python-dotenv -i https://pypi.tuna.tsinghua.edu.cn/simple

if [ $? -ne 0 ]; then
    echo "❌ 安装失败！请检查网络连接"
    exit 1
fi

echo "✓ 依赖安装成功"
echo ""

# 创建 .env 文件
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
    echo "✓ .env 文件已创建"
    echo ""
    echo "⚠️  请编辑 .env 文件，填入你的 OpenAI API Key:"
    echo "   OPENAI_API_KEY=sk-xxx..."
else
    echo "✓ .env 文件已存在"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                          ✅ 安装完成！                                     ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 下一步："
echo "   1. 编辑 .env 文件，填入 OpenAI API Key"
echo "   2. 运行: python3 scripts/run_agent.py"
echo "   3. 输入 'help' 查看可用命令"
echo ""
echo "💡 获取 API Key:"
echo "   访问 https://platform.openai.com/api-keys 获取免费试用额度"
echo ""

