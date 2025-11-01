#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速更新今日市场宽度数据
基于 analyse_marketing 的最新缓存 + 实时 API 调用
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.risk import position_scale
from src.patterns import load_st_code_set

def load_latest_candidate_data(exclude_st: bool = True):
	"""加载 analyse_marketing 的最新候选股票数据"""
	cache_dir = "analyse_marketing/cache/daily"
	
	if not os.path.exists(cache_dir):
		print("❌ analyse_marketing 缓存目录不存在")
		return None
	
	# 获取所有 parquet 文件
	files = [f for f in os.listdir(cache_dir) if f.endswith('.parquet')]
	if not files:
		print("❌ 缓存中没有数据文件")
		return None
	
	print(f"📊 找到 {len(files)} 个股票缓存")
	
	# 加载所有股票数据
	closes_dict = {}
	volumes_dict = {}
	
	for i, file in enumerate(files):  # 使用全部 4666 只股票
		if i % 20 == 0:
			print(f"  加载进度: {i+1}/{len(files)}")
		
		try:
			df = pd.read_parquet(os.path.join(cache_dir, file))
			code = file.replace('.parquet', '')
			# 列名兼容：close/vol
			if 'close' in df.columns:
				closes_dict[code] = df['close']
			if 'vol' in df.columns:
				volumes_dict[code] = df['vol']
		except Exception as e:
			continue
	
	if not closes_dict:
		print("❌ 无法加载有效数据")
		return None
	
	# 转换为 DataFrame（列为 000001_SZ 等缓存名，索引沿用原索引）
	closes = pd.concat(closes_dict, axis=1)
	volumes = pd.concat(volumes_dict, axis=1) if volumes_dict else closes * 0 + 1
	
	# 剔除ST（根据 ts_code 变体集合进行匹配）
	if exclude_st:
		st_set = load_st_code_set()
		if st_set:
			cols_keep = []
			for c in closes.columns:
				# c 是缓存名（000001_SZ 或 000001.SZ），st_set 含两种变体
				if c in st_set:
					continue
				# 某些缓存列可能仅为代码不含后缀，尝试补齐匹配
				c_dot = c.replace('_', '.')
				c_us = c.replace('.', '_')
				if c_dot in st_set or c_us in st_set:
					continue
				cols_keep.append(c)
			if cols_keep:
				closes = closes[cols_keep]
				volumes = volumes[cols_keep]
				print(f"✓ 已剔除ST，剩余 {closes.shape[1]} 只")
	
	print(f"✅ 成功加载: {closes.shape[0]} 交易日, {closes.shape[1]} 只股票")
	print(f"📅 数据范围: {closes.index[0]} 到 {closes.index[-1]}")
	
	return closes, volumes


def compute_breadth_today(closes, volumes):
	"""计算最新的市场宽度"""
	print("\n📈 计算市场宽度指标...")
	
	pct_change = closes.pct_change() * 100
	up_count = (pct_change > 0).sum(axis=1)
	down_count = (pct_change < 0).sum(axis=1)
	total = (pct_change.notna()).sum(axis=1)
	
	ad_ratio = (up_count - down_count) / total
	
	# 计算 52 周高低
	roll_max = closes.rolling(252, min_periods=60).max()
	roll_min = closes.rolling(252, min_periods=60).min()
	nh_252 = (closes >= (roll_max * 0.999)).sum(axis=1)
	nl_252 = (closes <= (roll_min * 1.001)).sum(axis=1)
	
	nh_ratio = nh_252 / total
	nl_ratio = nl_252 / total
	
	# 涨停比例（简化版）
	zt_ratio = (pct_change >= 9.8).sum(axis=1) / total
	
	# Z-score 得分
	def zscore(s):
		m = s.rolling(252, min_periods=60).mean()
		sd = s.rolling(252, min_periods=60).std().replace(0, np.nan)
		return (s - m) / sd
	
	score = 0.5*zscore(ad_ratio).clip(-3,3) + 0.3*zscore(nh_ratio - nl_ratio).clip(-3,3) + 0.2*zscore(zt_ratio).clip(-3,3)
	score_ema = score.ewm(span=5, adjust=False, min_periods=5).mean()
	
	# 市场态势
	regime = pd.Series(index=score_ema.index, dtype="object")
	regime[score_ema > 0.5] = "Bull"
	regime[score_ema < -0.5] = "Bear"
	regime[(score_ema <= 0.5) & (score_ema >= -0.5)] = "Neutral"
	
	breadth = pd.DataFrame({
		"up_count": up_count,
		"down_count": down_count,
		"total": total,
		"ad_ratio": ad_ratio,
		"nh_ratio": nh_ratio,
		"nl_ratio": nl_ratio,
		"zt_ratio": zt_ratio,
		"breadth_score": score,
		"breadth_score_ema": score_ema,
		"regime": regime,
	}).dropna()
	
	return breadth


if __name__ == "__main__":
	print("=" * 70)
	print(f"🔄 市场宽度快速更新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
	print("=" * 70)
	
	# 加载数据（剔除ST）
	result = load_latest_candidate_data(exclude_st=True)
	if result is None:
		sys.exit(1)
	
	closes, volumes = result
	
	# 计算市场宽度
	breadth = compute_breadth_today(closes, volumes)
	
	# 保存
	os.makedirs("data/market", exist_ok=True)
	breadth.to_parquet("data/market/breadth_am_integrated_new.parquet")
	print(f"\n✅ 新数据已保存到 breadth_am_integrated_new.parquet")
	
	# 显示最新数据
	latest = breadth.iloc[-1]
	print(f"\n📊 最新市场数据 (截止 {breadth.index[-1]}):")
	print(f"  ├─ 上涨家数: {int(latest['up_count'])} 家")
	print(f"  ├─ 下跌家数: {int(latest['down_count'])} 家")
	print(f"  ├─ 市场态势: {latest['regime']}")
	print(f"  ├─ 宽度得分: {latest['breadth_score_ema']:.3f}")
	print(f"  └─ 推荐仓位: {position_scale(breadth).iloc[-1]:.2%}")
	
	print("\n💡 使用新数据替换旧数据:")
	print("  mv data/market/breadth_am_integrated_new.parquet data/market/breadth_am_integrated.parquet")
    
