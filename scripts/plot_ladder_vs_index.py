#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt

# 中文字体（尽可能使用可用字体，避免中文乱码）
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from analyse_marketing.utils import get_pro, fetch_index_history
from src.limitup_ladder import build_ladder, load_ladder


def plot(index_code: str, days: int, metric: str, rebuild: bool, out_png: str):
	if rebuild:
		ladder = build_ladder(last_n_days=days)
	else:
		ladder = load_ladder()
	if ladder is None or ladder.empty:
		raise RuntimeError("连板梯队数据为空，请先使用 --rebuild 生成")
	ladder['date'] = pd.to_datetime(ladder['date'])
	ladder = ladder.set_index('date').sort_index()
	if days > 0:
		ladder = ladder.tail(days)
	if metric not in ladder.columns:
		raise ValueError(f"metric 必须为 {list(ladder.columns)} 之一")

	# 指数
	pro = get_pro()
	start_date = ladder.index.min().strftime('%Y%m%d')
	end_date = ladder.index.max().strftime('%Y%m%d')
	idx = fetch_index_history(pro, index_code=index_code, start_date=start_date, end_date=end_date)
	if idx is None or idx.empty:
		raise RuntimeError("指数数据为空")
	idx['trade_date'] = pd.to_datetime(idx['trade_date'])
	idx = idx.set_index('trade_date').sort_index()
	idx = idx.reindex(ladder.index.intersection(idx.index))
	if 'close' not in idx.columns:
		raise RuntimeError("指数数据缺少 close 列")
	idx_norm = idx['close'] / idx['close'].iloc[0]

	# 绘图
	plt.figure(figsize=(10, 6))
	gs = plt.GridSpec(2, 1, height_ratios=[2, 1], hspace=0.08)

	ax1 = plt.subplot(gs[0])
	x1 = idx_norm.index.to_numpy()
	y1 = idx_norm.to_numpy()
	ax1.plot(x1, y1, color='#1f77b4', label=f'{index_code} 归一')
	ax1.set_title(f'{index_code} 指数 vs 连板梯队（{metric}）')
	ax1.grid(True, alpha=0.3)
	ax1.legend(loc='upper left')

	ax2 = plt.subplot(gs[1], sharex=ax1)
	x2 = ladder.index.to_numpy()
	y2 = ladder[metric].to_numpy()
	ax2.plot(x2, y2, color='#d62728', label=f'连板: {metric}')
	ax2.grid(True, alpha=0.3)
	ax2.legend(loc='upper left')
	plt.setp(ax1.get_xticklabels(), visible=False)

	Path(os.path.dirname(out_png) or '.').mkdir(parents=True, exist_ok=True)
	plt.savefig(out_png, bbox_inches='tight', dpi=150)
	print(f'✅ 已保存: {out_png}')


def main():
	p = argparse.ArgumentParser(description='指数 vs 连板梯队 对比图')
	p.add_argument('--index', default='000001.SH', help='指数代码，如 000001.SH/399001.SZ/399006.SZ')
	p.add_argument('--days', type=int, default=120, help='最近N天')
	p.add_argument('--metric', default='high', help='绘制的连板指标: b1/b2/b3/b4p/high/total')
	p.add_argument('--rebuild', action='store_true', help='重算连板梯队缓存')
	p.add_argument('--out', default='data/plots/ladder_vs_index.png', help='输出图片路径')
	args = p.parse_args()
	plot(args.index, args.days, args.metric, args.rebuild, args.out)


if __name__ == '__main__':
	main()
