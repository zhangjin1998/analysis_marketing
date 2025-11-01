#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测分析脚本：历史数据参数优化与绩效评估
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.dataio import get_universe, load_parquet
from src.signals import make_signals
from src.risk import apply_regime_filter, position_scale
from src.backtest import simple_backtest


def run_backtest_period(start_date: str, end_date: str, top_n: int = 100,
                       mom_thresh: float = 0.6, vol_thresh: float = 0.8):
    """
    运行指定时期的回测
    
    :param start_date: 开始日期 YYYYMMDD
    :param end_date: 结束日期 YYYYMMDD
    :param top_n: 宇宙规模
    :param mom_thresh: 动量阈值
    :param vol_thresh: 波动阈值
    :return: dict 回测结果
    """
    print(f"\n执行回测: {start_date} ~ {end_date}")
    print(f"  参数: top_n={top_n}, mom_thresh={mom_thresh}, vol_thresh={vol_thresh}")
    
    try:
        # 获取宇宙（预期需要更新，这里使用缓存）
        uni = get_universe(top_n=top_n)
        codes = uni["代码"].tolist()
        
        # 生成信号（需要更长的历史用于计算指标）
        lookback = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=365)).strftime("%Y%m%d")
        closes, entries, exits, score = make_signals(codes, lookback, end_date)
        
        # 裁切到目标时期
        mask = (closes.index >= pd.to_datetime(start_date)) & (closes.index <= pd.to_datetime(end_date))
        closes_period = closes[mask]
        entries_period = entries[mask]
        exits_period = exits[mask]
        
        if len(closes_period) == 0:
            print("  ✗ 无效时期数据")
            return None
        
        # 应用Top-K筛选
        mask_top = score.loc[entries_period.index].apply(lambda s: s.rank(ascending=False) <= 20, axis=1)
        entries_top = entries_period & mask_top
        
        # 回测
        result = simple_backtest(closes_period, entries_top, exits_period, 
                               init_cash=100_000, fees=0.0003)
        
        if len(result) == 0:
            print("  ✗ 回测失败")
            return None
        
        # 计算关键指标
        total_ret = result['cumret'].iloc[-1]
        annualized_ret = (1 + total_ret) ** (252 / len(result)) - 1
        sharpe = result['return'].mean() / result['return'].std() * np.sqrt(252) if result['return'].std() > 0 else 0
        max_dd = ((result['value'].cummax() - result['value']) / result['value'].cummax()).max()
        
        print(f"  ✓ 年化: {annualized_ret:.2%}, 夏普: {sharpe:.2f}, 最大回撤: {max_dd:.2%}")
        
        return {
            'period': f"{start_date}-{end_date}",
            'total_return': total_ret,
            'annualized_return': annualized_ret,
            'sharpe': sharpe,
            'max_drawdown': max_dd,
            'trades': entries_top.sum().sum(),
            'days': len(result),
        }
    
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return None


def parameter_sweep(param_grid: dict) -> pd.DataFrame:
    """
    参数网格搜索
    
    :param param_grid: dict 参数范围
    :return: DataFrame 结果矩阵
    """
    print("\n=" * 70)
    print("开始参数扫描...")
    print("=" * 70)
    
    results = []
    
    # 简单的2024年回测（最近1年）
    end = datetime.today().strftime("%Y%m%d")
    start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")
    
    for top_n in param_grid.get('top_n', [100]):
        for mom in param_grid.get('momentum', [0.6]):
            for vol in param_grid.get('volatility', [0.8]):
                result = run_backtest_period(start, end, top_n=top_n, 
                                            mom_thresh=mom, vol_thresh=vol)
                if result:
                    results.append(result)
    
    df = pd.DataFrame(results)
    return df


if __name__ == "__main__":
    print("=" * 70)
    print("A股短线策略 - 回测分析工具")
    print("=" * 70)
    
    try:
        # 快速参数扫描示例
        param_grid = {
            'top_n': [80, 100, 120],
            'momentum': [0.5, 0.6, 0.7],
            'volatility': [0.7, 0.8, 0.9],
        }
        
        # 注意：实际调用需要修改 make_signals 以支持动态阈值
        # 这里演示框架，实际使用时需要调整
        
        print("\n提示: 参数扫描需要较长时间。可以：")
        print("1. 减少 param_grid 的参数范围")
        print("2. 减少 top_n 加快数据获取")
        print("3. 使用更短的时期测试")
        
        # 演示：单次回测
        end = datetime.today().strftime("%Y%m%d")
        start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")
        
        result = run_backtest_period(start, end, top_n=80)
        
        if result:
            print("\n" + "=" * 70)
            print("回测结果摘要")
            print("=" * 70)
            print(f"时期: {result['period']}")
            print(f"年化收益: {result['annualized_return']:.2%}")
            print(f"夏普比率: {result['sharpe']:.2f}")
            print(f"最大回撤: {result['max_drawdown']:.2%}")
            print(f"信号数: {result['trades']:.0f}")
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
