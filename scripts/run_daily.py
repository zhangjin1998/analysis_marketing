#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日度选股、择时、风控与订单生成脚本
运行时机：每个交易日收盘后 15:20（或次日开盘前）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pandas as pd

from src.dataio import get_universe, load_parquet
from src.signals import make_signals
from src.risk import apply_regime_filter, position_scale
from src.orders import export_orders_today
from src.backtest import simple_backtest


if __name__ == "__main__":
    print("=" * 70)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始日度选股、风控与订单生成")
    print("=" * 70)
    
    try:
        # ========== 第1步：数据准备 ==========
        print("\n[步骤1/6] 准备宇宙与日期范围...")
        uni = get_universe(top_n=100)
        codes = uni["代码"].tolist()
        
        end = datetime.today().strftime("%Y%m%d")
        start = (datetime.today() - timedelta(days=365 * 3)).strftime("%Y%m%d")
        
        print(f"  - 宇宙规模: {len(codes)} 只")
        print(f"  - 日期范围: {start} ~ {end}")
        
        # ========== 第2步：生成策略信号 ==========
        print("\n[步骤2/6] 生成选股信号...")
        closes, entries, exits, score = make_signals(codes, start, end)
        print(f"  - 面板形状: {closes.shape}")
        print(f"  - 入场信号 True 数: {entries.sum().sum():.0f}")
        
        # ========== 第3步：加载市场宽度数据 ==========
        print("\n[步骤3/6] 加载市场宽度与情绪...")
        try:
            breadth = load_parquet("market/breadth.parquet")
        except FileNotFoundError:
            print("  ✗ 警告: 未找到 breadth.parquet，请先运行 python scripts/run_breadth.py")
            breadth = None
        
        if breadth is not None:
            breadth = breadth.reindex(closes.index).ffill().dropna(how="all")
            print(f"  - 宽度数据形状: {breadth.shape}")
        
        # ========== 第4步：情绪过滤与Top-K筛选 ==========
        print("\n[步骤4/6] 应用情绪过滤与Top-K筛选...")
        
        if breadth is not None:
            entries_ok = apply_regime_filter(entries, breadth)
        else:
            entries_ok = entries
        
        # Top-20 打分筛选
        mask_top = score.apply(lambda s: s.rank(ascending=False) <= 20, axis=1)
        entries_top = entries_ok & mask_top
        
        print(f"  - 过滤后入场信号 True 数: {entries_top.sum().sum():.0f}")
        
        # ========== 第5步：回测（可选） ==========
        print("\n[步骤5/6] 执行简化回测...")
        try:
            backtest_result = simple_backtest(closes, entries_top, exits, 
                                             init_cash=100_000, fees=0.0003)
            print(f"  ✓ 回测完成")
        except Exception as e:
            print(f"  ✗ 回测失败: {e}")
            backtest_result = None
        
        # ========== 第6步：仓位缩放与订单导出 ==========
        print("\n[步骤6/6] 计算仓位缩放与导出订单...")
        
        if breadth is not None:
            scale = position_scale(breadth).iloc[-1]
            print(f"  - 今日仓位缩放因子: {scale:.2%}")
        else:
            scale = 1.0
            print(f"  - 无宽度数据，使用默认仓位: {scale:.2%}")
        
        path = export_orders_today(entries_top, score=score, top_n=20, 
                                  out_path="data/orders_today.csv")
        
        # ========== 输出摘要 ==========
        print("\n" + "=" * 70)
        print("运行完成摘要")
        print("=" * 70)
        
        if path:
            print(f"✓ 订单已导出: {path}")
        else:
            print("✓ 无新订单（今日无入场信号）")
        
        print(f"✓ 市场状态: {breadth['regime'].iloc[-1] if breadth is not None else '未知'}")
        print(f"✓ 仓位建议: {scale:.2%}")
        
        if backtest_result is not None:
            print(f"✓ 回测年化: {(backtest_result['cumret'].iloc[-1] + 1) ** (252/len(backtest_result)) - 1:.2%}")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
