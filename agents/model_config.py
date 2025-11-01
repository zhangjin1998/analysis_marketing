#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 多模型配置管理模块
支持切换不同的大模型 (DeepSeek, OpenAI, Claude, Qwen 等)
"""

import os
from typing import Optional, Dict, Any


# ========== 模型配置 ==========

MODEL_CONFIGS = {
    # 🇨🇳 DeepSeek (国内，最便宜，质量接近 GPT-4)
    "deepseek": {
        "provider": "openai",  # OpenAI 兼容 API
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2000,
        "cost": "$0 (¥500免费)",
        "speed": "快",
        "quality": "⭐⭐⭐⭐⭐",
        "notes": "推荐首选，国内服务器，中文优化",
    },
    
    # 🌍 OpenAI (国际标准，质量最好)
    "openai": {
        "provider": "openai",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "temperature": 0.3,
        "max_tokens": 2000,
        "cost": "$5-20/月",
        "speed": "中",
        "quality": "⭐⭐⭐⭐⭐",
        "notes": "国际标准，性能稳定",
    },
    
    # 🇨🇳 阿里通义千问 (免费额度，快速)
    "qwen": {
        "provider": "openai",
        "api_key": os.getenv("QWEN_API_KEY"),
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "model": "qwen-plus",
        "temperature": 0.3,
        "max_tokens": 2000,
        "cost": "$0 (免费额度)",
        "speed": "很快",
        "quality": "⭐⭐⭐⭐",
        "notes": "国内免费，很快，中文优化",
    },
    
    # 🇨🇳 讯飞星火 (成本低，支持长文本)
    "spark": {
        "provider": "openai",
        "api_key": os.getenv("SPARK_API_KEY"),
        "base_url": "https://spark-api.xf-yun.com/v1",
        "model": "4.0Ultra",
        "temperature": 0.3,
        "max_tokens": 2000,
        "cost": "$$ 低",
        "speed": "快",
        "quality": "⭐⭐⭐⭐",
        "notes": "成本低，支持超长文本",
    },
    
    # 🇨🇳 百度文心一言 (功能完整)
    "baidu": {
        "provider": "baidu",
        "api_key": os.getenv("BAIDU_API_KEY"),
        "base_url": "https://aip.baidubce.com/rpc/2.0",
        "model": "ernie-bot-4",
        "temperature": 0.3,
        "max_tokens": 2000,
        "cost": "$ 低",
        "speed": "快",
        "quality": "⭐⭐⭐⭐",
        "notes": "功能完整，生态好",
    },
    
    # 🇨🇳 Claude (Anthropic，推理能力最强)
    "claude": {
        "provider": "anthropic",
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.3,
        "max_tokens": 2000,
        "cost": "$$$ 中",
        "speed": "中",
        "quality": "⭐⭐⭐⭐⭐",
        "notes": "推理能力最强，思考深入",
    },
}


# ========== 模型工厂函数 ==========

def get_llm(model_name: str = "deepseek"):
    """
    根据模型名称获取 LLM 实例
    
    Args:
        model_name: 模型名称 (deepseek/openai/qwen/spark/baidu/claude)
    
    Returns:
        LLM 实例
    
    Raises:
        ValueError: 模型名称不存在
    """
    from langchain.llms import OpenAI, Anthropic
    
    if model_name not in MODEL_CONFIGS:
        raise ValueError(
            f"❌ 未知模型: {model_name}\n"
            f"可用模型: {', '.join(MODEL_CONFIGS.keys())}"
        )
    
    config = MODEL_CONFIGS[model_name]
    
    # 检查 API Key
    if not config["api_key"]:
        raise ValueError(
            f"❌ 缺少 API Key: {model_name}\n"
            f"请在 .env 中设置: {config['provider'].upper()}_API_KEY"
        )
    
    # 根据提供商创建 LLM 实例
    if config["provider"] == "anthropic":
        return Anthropic(
            api_key=config["api_key"],
            model=config["model"],
        )
    
    elif config["provider"] == "baidu":
        # 百度需要特殊处理
        # 这里简化处理，实际使用需要百度官方 SDK
        from langchain.llms import OpenAI
        # 注: 百度不完全兼容 OpenAI API，建议使用百度官方 SDK
        pass
    
    else:  # OpenAI 兼容的 API
        return OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model=config["model"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )


def list_models():
    """列出所有可用模型"""
    from tabulate import tabulate
    
    headers = ["模型", "提供商", "成本", "速度", "质量", "备注"]
    rows = []
    
    for name, cfg in MODEL_CONFIGS.items():
        rows.append([
            name,
            cfg["provider"],
            cfg["cost"],
            cfg["speed"],
            cfg["quality"],
            cfg["notes"][:30] + "..." if len(cfg["notes"]) > 30 else cfg["notes"]
        ])
    
    return tabulate(rows, headers=headers, tablefmt="grid")


def check_models():
    """检查所有模型的 API Key 配置状态"""
    print("\n📋 模型 API Key 配置状态检查")
    print("=" * 70)
    
    for name, cfg in MODEL_CONFIGS.items():
        has_key = "✅" if cfg["api_key"] else "❌"
        
        # 获取正确的环境变量名
        if name == "deepseek":
            env_var = "DEEPSEEK_API_KEY"
        elif name == "openai":
            env_var = "OPENAI_API_KEY"
        elif name == "qwen":
            env_var = "QWEN_API_KEY"
        elif name == "spark":
            env_var = "SPARK_API_KEY"
        elif name == "baidu":
            env_var = "BAIDU_API_KEY"
        elif name == "claude":
            env_var = "ANTHROPIC_API_KEY"
        else:
            env_var = f"{cfg['provider'].upper()}_API_KEY"
        
        print(f"{has_key} {name:15} ({cfg['provider']:10}) -> {env_var}")
    
    print("=" * 70)


def get_default_model():
    """获取默认模型"""
    model_name = os.getenv("TRADING_MODEL", "deepseek")
    return model_name


# ========== 主函数示例 ==========

if __name__ == "__main__":
    import sys
    
    # 列出所有模型
    print("\n" + "=" * 70)
    print("🤖 可用的 AI 模型")
    print("=" * 70 + "\n")
    print(list_models())
    
    # 检查配置
    print("\n")
    check_models()
    
    # 测试模型
    print("\n📊 默认模型: ", get_default_model())
