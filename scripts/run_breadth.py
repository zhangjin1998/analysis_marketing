#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
市场宽度与情绪周期构建脚本
运行时机：每个交易日收盘后 15:10
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.breadth import build_breadth
from datetime import datetime


if __name__ == "__main__":
    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始构建市场宽度数据")
    print("=" * 60)
    
    try:
        # 构建宽度数据（取流动性最好的前100个，回溯2年）
        df = build_breadth(top_n=100, lookback_days=365 * 2)
        
        print("\n" + "=" * 60)
        print("最近3个交易日的市场状态摘要：")
        print("=" * 60)
        summary = df[["up_count", "down_count", "ad_ratio", "breadth_score_ema", "regime"]].tail(3)
        print(summary.to_string())
        
        print("\n" + "=" * 60)
        print("✓ 宽度数据已成功保存到 data/market/breadth.parquet")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
