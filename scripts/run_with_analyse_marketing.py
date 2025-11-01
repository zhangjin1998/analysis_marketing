#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股短线交易系统 - 与analyse_marketing集成版本
融合analyse_marketing的真实数据、候选池与短线交易策略
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.dataio import load_from_analyse_marketing, load_daily_candidates, convert_tushare_format
from src.breadth import compute_breadth
from src.signals import make_signals
from src.risk import apply_regime_filter, position_scale
from src.orders import export_orders_today
from src.backtest import simple_backtest

print("=" * 80)
print("🎬 A股短线交易系统 - analyse_marketing集成版本")
print("=" * 80)

# ========== 第1步：加载analyse_marketing数据 ==========
print("\n[步骤1/6] 加载analyse_marketing真实数据...")

# 自动定位analyse_marketing目录
am_base = os.path.join(os.path.dirname(__file__), "..", "analyse_marketing")
am_cache = os.path.join(am_base, "cache", "daily")
am_out = os.path.join(am_base, "out")

print(f"  - 数据缓存目录: {am_cache}")
print(f"  - 输出目录: {am_out}")

# 加载面板数据
panels = load_from_analyse_marketing(cache_dir=am_cache, min_records=60)

if not panels:
    print("\n✗ 无法加载面板数据，请先运行 analyse_marketing/main.py 生成缓存")
    print("  提示：python3 ../analyse_marketing/main.py --start 20230101 --export ./out")
    sys.exit(1)

print(f"  ✓ 成功加载 {len(panels)} 只股票的面板数据")

# 合并收盘价与成交量
closes = pd.concat({k: v["close"] for k, v in panels.items()}, axis=1).dropna(how="all")
volumes = pd.concat({k: v["volume"] for k, v in panels.items()}, axis=1).reindex_like(closes)

print(f"  ✓ 面板形状: {closes.shape[0]} 交易日 × {closes.shape[1]} 只股票")

# ========== 第2步：加载analyse_marketing候选池 ==========
print("\n[步骤2/6] 加载analyse_marketing候选池...")

candidates = load_daily_candidates(output_dir=am_out)

if candidates:
    # 过滤到候选池中的股票
    valid_codes = [c for c in closes.columns if c in candidates]
    if valid_codes:
        closes = closes[valid_codes]
        volumes = volumes[valid_codes]
        print(f"  ✓ 过滤到候选池: {len(valid_codes)} 个标的")
    else:
        print(f"  ⚠️  候选池中的代码与面板数据不匹配，使用全部面板")
else:
    print(f"  ⚠️  未找到候选池，使用所有面板数据")

# ========== 第3步：计算市场宽度 ==========
print("\n[步骤3/6] 计算市场宽度与情绪...")

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
})  # 移除 .dropna() 以保留所有日期

print(f"  ✓ 宽度计算完成: {len(breadth)} 日")
if len(breadth) > 0:
    print(f"  ✓ 最近态势: {breadth['regime'].iloc[-1]} (得分: {breadth['breadth_score_ema'].iloc[-1]:.2f})")

os.makedirs("data/market", exist_ok=True)
breadth.to_parquet("data/market/breadth_am_integrated.parquet")

# ========== 第4步：生成选股信号 ==========
print("\n[步骤4/6] 生成选股信号...")

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
print("\n[步骤5/6] 应用风控过滤...")

reg = breadth["regime"].reindex(entries.index).ffill()

# 修复：使用正确的向量化方式进行行级别的过滤
# 创建一个 boolean 数组，每行都是 (reg != "Bear") 的值
not_bear_mask = (reg != "Bear").values.reshape(-1, 1)  # 转换为列向量以便广播
entries_filtered = entries & not_bear_mask

mask_top = score.apply(lambda s: s.rank(ascending=False) <= 20, axis=1)
entries_top = entries_filtered & mask_top

print(f"  ✓ 过滤后入场信号: {entries_top.sum().sum():.0f} 个")

# 仓位缩放
sig = 1 / (1 + np.exp(-breadth["breadth_score_ema"]))
position_scale_factor = (0.2 + sig).clip(0, 1)

print(f"  ✓ 仓位缩放范围: {position_scale_factor.min():.2%} ~ {position_scale_factor.max():.2%}")

# ========== 第6步：导出订单 ==========
print("\n[步骤6/6] 生成并导出订单...")

today = entries_top.index[-1]
picks_mask = entries_top.loc[today].fillna(False)

# 处理NaN值（可能所有值都是NaN）
if picks_mask.isna().all():
    picks_mask = pd.Series(False, index=picks_mask.index)
else:
    picks_mask = picks_mask.fillna(False)

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
    
    orders_df.to_csv("data/orders_am_integrated.csv", index=False, encoding="utf-8-sig")
    
    print(f"  ✓ 已导出 {n_picks} 个信号到 data/orders_am_integrated.csv")
    print(f"  ✓ 每个标的权重: {alloc:.2%}")
    print(f"\n  📋 订单预览 (前10个):")
    print(orders_df.head(10).to_string(index=False))

# ========== 生成报告 ==========
print("\n" + "=" * 80)
print("📊 analyse_marketing集成 - 运行完成")
print("=" * 80)

print(f"\n📈 市场状态:")
if len(breadth) > 0:
    print(f"  - 交易日: {today.strftime('%Y-%m-%d')}")
    print(f"  - 市场态势: {breadth['regime'].iloc[-1]}")
    print(f"  - 宽度得分: {breadth['breadth_score_ema'].iloc[-1]:.2f}")
    print(f"  - 上涨: {int(breadth['up_count'].iloc[-1])}, 下跌: {int(breadth['down_count'].iloc[-1])}")

print(f"\n💰 仓位管理:")
if len(position_scale_factor) > 0:
    print(f"  - 今日缩放: {position_scale_factor.iloc[-1]:.2%}")

print(f"\n📂 输出文件:")
print(f"  - 市场指标: data/market/breadth_am_integrated.parquet")
print(f"  - 订单文件: data/orders_am_integrated.csv")
print(f"  - 候选池: {am_out}/daily_candidates.csv")

print("\n✅ 集成完成！")
print("=" * 80)

print("\n💡 后续步骤:")
print("  1. 查看 data/orders_am_integrated.csv 获取今日交易订单")
print("  2. 定期运行 analyse_marketing/main.py 更新数据缓存")
print("  3. 调整参数后重新运行本脚本")

print("\n✨ 祝交易顺利! 📈\n")
