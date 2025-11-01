#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股短线交易系统 - 真实数据运行版本
支持从CSV加载真实行情数据（用户可从通达信、同花顺导出）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 70)
print("🎬 A股短线交易系统 - 真实数据版本")
print("=" * 70)

# ========== 检查真实数据文件 ==========
print("\n[检查] 寻找真实数据源...")

csv_files = [f for f in os.listdir("data") if f.endswith(".csv")] if os.path.exists("data") else []

if csv_files:
    print(f"  ✓ 找到 {len(csv_files)} 个CSV文件")
    print(f"    {', '.join(csv_files)}")
else:
    print("\n  ⚠️  未找到真实数据文件！")
    print("\n  💡 获取真实数据的方式：")
    print("     1️⃣  从同花顺/通达信/东方财富导出CSV")
    print("     2️⃣  手工放入 data/ 目录")
    print("     3️⃣  或者使用以下方法获取：")
    print()
    print("     方案A: 使用 tushare (需付费，推荐)")
    print("       pip install tushare")
    print("       # 然后修改脚本下载数据")
    print()
    print("     方案B: 使用 yfinance (免费，国际数据)")
    print("       pip install yfinance")
    print()
    print("     方案C: 手工下载后放入 data/ 目录")
    print("       格式: code,date,open,high,low,close,volume")
    print()
    
    # 创建示例CSV
    print("  🔧 创建示例真实数据结构...")
    
    sample_data = {
        "date": pd.date_range("2023-01-01", periods=30, freq="D"),
        "code": ["000001"] * 30,
        "open": 100 + np.random.randn(30).cumsum() * 0.5,
        "high": 102 + np.random.randn(30).cumsum() * 0.5,
        "low": 98 + np.random.randn(30).cumsum() * 0.5,
        "close": 100 + np.random.randn(30).cumsum() * 0.5,
        "volume": np.random.randint(10000000, 100000000, 30),
    }
    
    sample_df = pd.DataFrame(sample_data)
    os.makedirs("data", exist_ok=True)
    sample_df.to_csv("data/sample_000001.csv", index=False)
    print("  ✓ 已创建示例文件: data/sample_000001.csv")
    print("  ✓ 请参考此格式添加真实数据")
    sys.exit(1)

# ========== 加载真实数据 ==========
print("\n[第1步] 加载真实行情数据...")

all_data = []
for csv_file in csv_files:
    try:
        df = pd.read_csv(f"data/{csv_file}")
        all_data.append(df)
        print(f"  ✓ 已加载 {csv_file}: {len(df)} 行")
    except Exception as e:
        print(f"  ✗ 加载 {csv_file} 失败: {e}")

if not all_data:
    print("  ✗ 无法加载任何数据")
    sys.exit(1)

# 合并数据
data = pd.concat(all_data, ignore_index=True)
data["date"] = pd.to_datetime(data["date"])
data = data.sort_values(["code", "date"]).reset_index(drop=True)

print(f"\n  📊 数据概览:")
print(f"    - 股票数: {data['code'].nunique()}")
print(f"    - 交易日: {data['date'].min().date()} ~ {data['date'].max().date()}")
print(f"    - 总记录: {len(data)}")

# ========== 构建面板数据 ==========
print("\n[第2步] 构建面板数据...")

closes_list = []
volumes_list = []

for code in data["code"].unique():
    code_data = data[data["code"] == code].set_index("date")[["close", "volume"]]
    closes_list.append(code_data[["close"]].rename(columns={"close": code}))
    volumes_list.append(code_data[["volume"]].rename(columns={"volume": code}))

closes = pd.concat(closes_list, axis=1).dropna(how="all")
volumes = pd.concat(volumes_list, axis=1).dropna(how="all")

print(f"  ✓ 面板数据: {closes.shape[0]} 交易日 × {closes.shape[1]} 只股票")

# ========== 第3步：计算市场宽度 ==========
print("\n[第3步] 计算市场宽度与情绪...")

pct_change = closes.pct_change() * 100
up_count = (pct_change > 0).sum(axis=1)
down_count = (pct_change < 0).sum(axis=1)
total = (pct_change.notna()).sum(axis=1)

ad_ratio = (up_count - down_count) / total

# 52周高低
roll_max = closes.rolling(252, min_periods=20).max()
roll_min = closes.rolling(252, min_periods=20).min()
nh_252 = (closes >= (roll_max * 0.999)).sum(axis=1)
nl_252 = (closes <= (roll_min * 1.001)).sum(axis=1)

nh_ratio = nh_252 / total.clip(lower=1)
nl_ratio = nl_252 / total.clip(lower=1)

# Z-score 得分
def zscore(s):
    m = s.rolling(min(252, len(s)//2), min_periods=5).mean()
    sd = s.rolling(min(252, len(s)//2), min_periods=5).std().replace(0, np.nan)
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

print(f"  ✓ 宽度计算完成: {len(breadth)} 日")
print(f"  ✓ 最近态势: {breadth['regime'].iloc[-1]} (得分: {breadth['breadth_score_ema'].iloc[-1]:.2f})")

os.makedirs("data/market", exist_ok=True)
breadth.to_parquet("data/market/breadth_real.parquet")
print(f"  ✓ 已保存到 data/market/breadth_real.parquet")

# ========== 第4步：生成选股信号 ==========
print("\n[第4步] 生成选股信号...")

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

# ========== 第5步：风控过滤 ==========
print("\n[第5步] 应用风控过滤...")

reg = breadth["regime"].reindex(entries.index).ffill()
entries_filtered = entries & (reg != "Bear")

mask_top = score.apply(lambda s: s.rank(ascending=False) <= 20, axis=1)
entries_top = entries_filtered & mask_top

print(f"  ✓ 过滤后入场信号: {entries_top.sum().sum():.0f} 个")

# 仓位缩放
sig = 1 / (1 + np.exp(-breadth["breadth_score_ema"]))
position_scale = (0.2 + sig).clip(0, 1)

print(f"  ✓ 仓位缩放范围: {position_scale.min():.2%} ~ {position_scale.max():.2%}")

# ========== 第6步：导出订单 ==========
print("\n[第6步] 生成并导出订单...")

today = entries_top.index[-1]
picks_mask = entries_top.loc[today].fillna(False)
picks = picks_mask[picks_mask].index.tolist()

if len(picks) == 0:
    print(f"  ⚠️  今日无入场信号 (市场态势: {breadth['regime'].iloc[-1]})")
else:
    picks = score.loc[today][picks].nlargest(20).index.tolist()
    n_picks = len(picks)
    alloc = round(1 / n_picks, 4)
    
    orders_df = pd.DataFrame({
        "code": picks,
        "target_weight": alloc,
        "order_type": "buy",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    
    orders_df.to_csv("data/orders_real.csv", index=False, encoding="utf-8-sig")
    
    print(f"  ✓ 已导出 {n_picks} 个信号到 data/orders_real.csv")
    print(f"  ✓ 每个标的权重: {alloc:.2%}")
    print(f"\n  📋 订单预览 (前5个):")
    print(orders_df.head(5).to_string(index=False))

# ========== 生成报告 ==========
print("\n" + "=" * 70)
print("📊 真实数据运行完成")
print("=" * 70)

print(f"\n📈 市场状态:")
print(f"  - 交易日: {today.strftime('%Y-%m-%d')}")
print(f"  - 市场态势: {breadth['regime'].iloc[-1]}")
print(f"  - 宽度得分: {breadth['breadth_score_ema'].iloc[-1]:.2f}")
print(f"  - 上涨: {int(breadth['up_count'].iloc[-1])}, 下跌: {int(breadth['down_count'].iloc[-1])}")

print(f"\n💰 仓位管理:")
print(f"  - 今日缩放: {position_scale.iloc[-1]:.2%}")

print("\n✅ 真实数据处理完成！")
print("=" * 70)
