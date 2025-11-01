#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股短线交易系统 - 演示脚本
使用模拟数据展示完整工作流程（无需真实数据源）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 70)
print("🎬 A股短线交易系统 - 完整演示")
print("=" * 70)

# ========== 第1步：模拟数据生成 ==========
print("\n[步骤1/5] 生成模拟市场数据...")

np.random.seed(42)
dates = pd.date_range('2023-01-01', periods=252, freq='D')
n_stocks = 100

# 生成模拟收盘价
closes_data = {}
for i in range(n_stocks):
    returns = np.random.randn(252) * 0.02
    price = 100 * np.exp(np.cumsum(returns))
    closes_data[f'stock_{i:03d}'] = price

closes = pd.DataFrame(closes_data, index=dates)
volumes_data = {col: np.random.randint(1000000, 10000000, 252) for col in closes.columns}
volumes = pd.DataFrame(volumes_data, index=dates)

print(f"  ✓ 生成数据: {closes.shape[0]} 交易日, {closes.shape[1]} 只股票")

# ========== 第2步：计算市场宽度 ==========
print("\n[步骤2/5] 计算市场宽度与情绪...")

pct_change = closes.pct_change() * 100
up_count = (pct_change > 0).sum(axis=1)
down_count = (pct_change < 0).sum(axis=1)
total = (pct_change.notna()).sum(axis=1)

ad_ratio = (up_count - down_count) / total

# 计算52周高低
roll_max = closes.rolling(252, min_periods=60).max()
roll_min = closes.rolling(252, min_periods=60).min()
nh_252 = (closes >= (roll_max * 0.999)).sum(axis=1)
nl_252 = (closes <= (roll_min * 1.001)).sum(axis=1)

nh_ratio = nh_252 / total
nl_ratio = nl_252 / total

# Z-score 得分
def zscore(s):
    m = s.rolling(252, min_periods=60).mean()
    sd = s.rolling(252, min_periods=60).std().replace(0, np.nan)
    return (s - m) / sd

breadth_score = 0.5 * zscore(ad_ratio).clip(-3,3) + 0.3 * zscore(nh_ratio - nl_ratio).clip(-3,3)
breadth_score_ema = breadth_score.ewm(span=5, adjust=False, min_periods=5).mean()

# 市场态势
regime = pd.Series(index=breadth_score_ema.index, dtype="object")
regime[breadth_score_ema > 0.5] = "Bull"
regime[breadth_score_ema < -0.5] = "Bear"
regime[(breadth_score_ema <= 0.5) & (breadth_score_ema >= -0.5)] = "Neutral"

breadth = pd.DataFrame({
    "up_count": up_count,
    "down_count": down_count,
    "ad_ratio": ad_ratio,
    "nh_ratio": nh_ratio,
    "breadth_score_ema": breadth_score_ema,
    "regime": regime,
}).dropna()

print(f"  ✓ 市场宽度计算完成: {len(breadth)} 日")
print(f"  ✓ 最近态势: {breadth['regime'].iloc[-1]} (得分: {breadth['breadth_score_ema'].iloc[-1]:.2f})")

# 保存到文件
os.makedirs("data/market", exist_ok=True)
breadth.to_parquet("data/market/breadth.parquet")
print(f"  ✓ 已保存到 data/market/breadth.parquet")

# ========== 第3步：生成选股信号 ==========
print("\n[步骤3/5] 生成选股信号...")

ma5 = closes.rolling(5).mean()
ma20 = closes.rolling(20).mean()
mom5 = closes.pct_change(5)
vol20 = closes.pct_change().rolling(20).std()
vr = volumes / volumes.rolling(20).mean()

# 排序打分
q_mom = mom5.rank(axis=1, pct=True)
q_vol = vol20.rank(axis=1, pct=True)
score = q_mom - q_vol

# 入场与出场信号
entries = (ma5 > ma20) & (q_mom > 0.6) & (q_vol < 0.8) & (vr > 1)
exits = ma5 < ma20

print(f"  ✓ 入场信号: {entries.sum().sum():.0f} 个")
print(f"  ✓ 出场信号: {exits.sum().sum():.0f} 个")

# ========== 第4步：应用风控过滤 ==========
print("\n[步骤4/5] 应用风控过滤...")

# 市场态势过滤
reg = breadth["regime"].reindex(entries.index).ffill()
entries_filtered = entries & (reg != "Bear")

# Top-20 筛选
mask_top = score.apply(lambda s: s.rank(ascending=False) <= 20, axis=1)
entries_top = entries_filtered & mask_top

print(f"  ✓ 过滤后入场信号: {entries_top.sum().sum():.0f} 个")

# 仓位缩放
sig = 1 / (1 + np.exp(-breadth["breadth_score_ema"]))
position_scale = (0.2 + sig).clip(0, 1)

print(f"  ✓ 仓位缩放范围: {position_scale.min():.2%} ~ {position_scale.max():.2%}")

# ========== 第5步：导出订单 ==========
print("\n[步骤5/5] 生成并导出订单...")

today = entries_top.index[-1]
picks_mask = entries_top.loc[today]
picks_mask = picks_mask.fillna(False)  # 填充NaN为False
picks = picks_mask[picks_mask].index.tolist()

if len(picks) == 0:
    print(f"  ⚠️  今日无入场信号 (市场态势: {breadth['regime'].iloc[-1]})")
    orders_df = pd.DataFrame()
else:
    # 按score排序取前20
    picks = score.loc[today][picks].nlargest(20).index.tolist()
    n_picks = len(picks)
    alloc = round(1 / n_picks, 4)
    
    orders_df = pd.DataFrame({
        "code": picks,
        "name": [f"代码_{i}" for i in range(n_picks)],
        "target_weight": alloc,
        "order_type": "buy",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    
    os.makedirs("data", exist_ok=True)
    orders_df.to_csv("data/orders_today.csv", index=False, encoding="utf-8-sig")
    
    print(f"  ✓ 已导出 {n_picks} 个信号")
    print(f"  ✓ 每个标的权重: {alloc:.2%}")
    print(f"  ✓ 文件位置: data/orders_today.csv")

# ========== 生成报告 ==========
print("\n" + "=" * 70)
print("📊 系统运行完成摘要")
print("=" * 70)

print(f"\n📈 市场状态:")
print(f"  - 最新交易日: {today.strftime('%Y-%m-%d')}")
print(f"  - 市场态势: {breadth['regime'].iloc[-1]}")
print(f"  - 宽度得分: {breadth['breadth_score_ema'].iloc[-1]:.2f}")
print(f"  - 上涨家数: {int(breadth['up_count'].iloc[-1])}")
print(f"  - 下跌家数: {int(breadth['down_count'].iloc[-1])}")

print(f"\n📊 策略表现:")
print(f"  - 入场信号总数: {entries.sum().sum():.0f}")
print(f"  - 风控过滤后: {entries_filtered.sum().sum():.0f}")
print(f"  - Top-20筛选后: {entries_top.sum().sum():.0f}")
print(f"  - 今日入场: {len(picks) if len(picks) > 0 else 0}")

print(f"\n💰 仓位管理:")
print(f"  - 今日仓位缩放因子: {position_scale.iloc[-1]:.2%}")
print(f"  - 仓位范围: {position_scale.min():.2%} ~ {position_scale.max():.2%}")

if len(picks) > 0:
    print(f"\n📋 今日订单预览 (前5个):")
    print(orders_df.head(5).to_string(index=False))

print("\n" + "=" * 70)
print("✅ 演示完成！系统已成功运行。")
print("=" * 70)

print("\n💡 后续步骤:")
print("  1. 查看 data/orders_today.csv 获取完整订单")
print("  2. 查看 data/market/breadth.parquet 获取市场指标")
print("  3. 在生产环境中用真实数据源(akshare)替换模拟数据")
print("  4. 配置 crontab 或任务计划程序进行自动化")

print("\n✨ 祝交易顺利! 📈\n")
