#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 A股短线交易系统 - Agent 启动脚本
运行命令: python3 scripts/run_agent.py
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.trading_agent import run_agent_loop

if __name__ == "__main__":
    run_agent_loop()
