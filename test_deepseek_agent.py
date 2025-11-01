#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 DeepSeek Agent - 验证集成是否正确
"""

import os
import sys

# 设置环境变量
os.environ['DEEPSEEK_API_KEY'] = 'sk-0252c421598b44a9be3cbe68425dfa0d'
os.environ['TRADING_MODEL'] = 'deepseek'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("🤖 DeepSeek Agent 测试")
print("=" * 80)
print()

# 测试 1: 检查模型配置
print("【测试 1】检查模型配置状态")
print("-" * 80)
from agents.model_config import get_default_model, check_models, list_models

model_name = get_default_model()
print(f"✅ 默认模型: {model_name}")
print(f"✅ 环境变量 DEEPSEEK_API_KEY 已配置")
print()

# 测试 2: 列出所有模型
print("【测试 2】可用模型列表")
print("-" * 80)
print(list_models())
print()

# 测试 3: 获取 LLM 实例
print("【测试 3】初始化 DeepSeek LLM")
print("-" * 80)
try:
    from agents.model_config import get_llm
    llm = get_llm('deepseek')
    print(f"✅ DeepSeek LLM 初始化成功!")
    print(f"   模型类型: {type(llm).__name__}")
    print(f"   基础 URL: https://api.deepseek.com/v1")
    print(f"   模型名称: deepseek-chat")
except Exception as e:
    print(f"❌ 错误: {e}")
print()

# 测试 4: 简单测试 LLM
print("【测试 4】测试 LLM 能力 (简单提示)")
print("-" * 80)
try:
    response = llm("用一句话解释什么是 A 股短线交易")
    print(f"✅ LLM 响应成功!")
    print(f"回复内容: {response}")
except Exception as e:
    print(f"❌ 错误: {e}")
    print(f"   可能原因: API Key 无效、网络问题、API 配额不足")
print()

# 测试 5: 显示系统信息
print("【测试 5】系统配置信息")
print("-" * 80)
print(f"✅ 项目路径: {os.getcwd()}")
print(f"✅ Python 版本: {sys.version.split()[0]}")
print(f"✅ DeepSeek API Key: {os.environ.get('DEEPSEEK_API_KEY')[:20]}...")
print(f"✅ 交易模型: {os.environ.get('TRADING_MODEL')}")
print()

print("=" * 80)
print("✅ DeepSeek Agent 配置测试完成！")
print("=" * 80)
print()
print("📝 接下来可以运行:")
print("   python3 scripts/run_agent.py")
print()
