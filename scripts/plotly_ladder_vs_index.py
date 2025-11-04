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
from src.limitup_ladder import build_ladder, load_ladder, build_ladder_distribution, load_ladder_distribution

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _ensure_dist(days: int, rebuild: bool, max_level: int):
	df = build_ladder_distribution(last_n_days=days, max_level=max_level) if rebuild else load_ladder_distribution()
	if df is None or df.empty:
		raise RuntimeError("连板梯队分布数据为空，请使用 --rebuild 先生成")
	df['date'] = pd.to_datetime(df['date'])
	df = df.set_index('date').sort_index()
	if days > 0:
		df = df.tail(days)
	return df


def _load_index_df(index_code: str, x_index):
	pro = get_pro()
	start_date = pd.to_datetime(pd.Series(x_index).min()).strftime('%Y%m%d')
	end_date = pd.to_datetime(pd.Series(x_index).max()).strftime('%Y%m%d')
	idx = fetch_index_history(pro, index_code=index_code, start_date=start_date, end_date=end_date)
	if idx is None or idx.empty:
		return pd.DataFrame()
	idx['trade_date'] = pd.to_datetime(idx['trade_date'])
	idx = idx.set_index('trade_date').sort_index()
	idx = idx.reindex(pd.DatetimeIndex(x_index).intersection(idx.index))
	return idx


def _index_norm_series(index_code: str, x_index):
	idx = _load_index_df(index_code, x_index)
	if idx is None or idx.empty or 'close' not in idx.columns:
		return pd.Series(index=pd.DatetimeIndex(x_index), dtype=float)
	ser = idx['close'] / idx['close'].iloc[0]
	return ser


def build_figure_index(index_code: str, days: int, metric: str, rebuild: bool, index_style: str):
	ladder = build_ladder(last_n_days=days) if rebuild else load_ladder()
	if ladder is None or ladder.empty:
		raise RuntimeError("连板梯队数据为空，请先使用 --rebuild 生成")
	ladder['date'] = pd.to_datetime(ladder['date'])
	ladder = ladder.set_index('date').sort_index()
	if days > 0:
		ladder = ladder.tail(days)
	if metric not in ladder.columns:
		raise ValueError(f"metric 必须为 {list(ladder.columns)} 之一")

	# 指数
	if index_style == 'candle':
		idx = _load_index_df(index_code, ladder.index)
	else:
		idx = None
		ser = _index_norm_series(index_code, ladder.index)

	title_top = f"{index_code}{'（K线）' if index_style=='candle' else '（归一化）'}"
	fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
				subplot_titles=(title_top, f"连板梯队：{metric}"))
	if index_style == 'candle' and idx is not None and not idx.empty:
		fig.add_trace(
			go.Candlestick(
				x=idx.index,
				open=idx['open'], high=idx['high'], low=idx['low'], close=idx['close'], name=f'{index_code}',
				increasing_line_color='red', increasing_fillcolor='red',
				decreasing_line_color='green', decreasing_fillcolor='green'
			),
			row=1, col=1
		)
	else:
		fig.add_trace(
			go.Scatter(x=ser.index, y=ser.values, mode='lines', name=f'{index_code}', line=dict(color='#1f77b4')),
			row=1, col=1
		)

	fig.add_trace(
		go.Bar(x=ladder.index, y=ladder[metric].values, name=f'{metric}', marker_color='#d62728', opacity=0.8),
		row=2, col=1
	)
	fig.update_layout(height=700, title=f"指数 vs 连板梯队（{index_code}, 最近{days}日, {metric}）",
		legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), margin=dict(l=40, r=20, t=60, b=40))
	fig.update_yaxes(title_text='指数' if index_style=='candle' else '指数(归一)', row=1, col=1)
	fig.update_yaxes(title_text=f'{metric}', row=2, col=1)
	return fig


def build_figure_heatmap(days: int, rebuild: bool, max_level: int, share: bool, with_index: bool, index_code: str, index_style: str):
	df = _ensure_dist(days, rebuild, max_level)
	level_cols = [f'L{i}' for i in range(1, max_level)] + [f'L{max_level}', f'L{max_level}p']
	if share:
		den = df['total'].replace(0, 1)
		zdf = df[level_cols].div(den, axis=0)
		title_suffix = '（占比）'
	else:
		zdf = df[level_cols]
		title_suffix = '（数量）'
	# y轴从高到低
	y_labels = [f'{max_level}+' , f'{max_level}'] + [str(i) for i in range(max_level-1, 0, -1)]
	reorder = [f'L{max_level}p', f'L{max_level}'] + [f'L{i}' for i in range(max_level-1, 0, -1)]
	z = zdf[reorder].T.values
	x = df.index
	if with_index:
		title_top = f"{index_code}{'（K线）' if index_style=='candle' else '（归一化）'}"
		fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
					subplot_titles=(title_top, f"连板梯队热力图{title_suffix}"))
		if index_style == 'candle':
			idx = _load_index_df(index_code, x)
			fig.add_trace(
				go.Candlestick(
					x=idx.index, open=idx['open'], high=idx['high'], low=idx['low'], close=idx['close'], name=f'{index_code}',
					increasing_line_color='red', increasing_fillcolor='red',
					decreasing_line_color='green', decreasing_fillcolor='green'
				),
				row=1, col=1
			)
		else:
			ser = _index_norm_series(index_code, x)
			fig.add_trace(go.Scatter(x=ser.index, y=ser.values, mode='lines', name=f'{index_code}', line=dict(color='#1f77b4')), row=1, col=1)
		fig.add_trace(go.Heatmap(z=z, x=x, y=y_labels, colorscale='YlOrRd', colorbar=dict(title='强度')), row=2, col=1)
		fig.update_yaxes(title_text=('指数' if index_style=='candle' else '指数(归一)'), row=1, col=1)
		fig.update_layout(height=720)
	else:
		fig = go.Figure(data=go.Heatmap(z=z, x=x, y=y_labels, colorscale='YlOrRd', colorbar=dict(title='强度')))
		fig.update_layout(height=520)
	fig.update_layout(title=f"连板梯队热力图{title_suffix}（最近{days}日）", margin=dict(l=40, r=20, t=60, b=40))
	return fig


def build_figure_stacked(days: int, rebuild: bool, max_level: int, share: bool, with_max_line: bool, with_index: bool, index_code: str, index_style: str):
	df = _ensure_dist(days, rebuild, max_level)
	level_cols = [f'L{i}' for i in range(1, max_level)] + [f'L{max_level}', f'L{max_level}p']
	if share:
		den = df['total'].replace(0, 1)
		plot_df = df[level_cols].div(den, axis=0)
		title_suffix = '（占比）'
		y_title = '份额占比'
	else:
		plot_df = df[level_cols]
		title_suffix = '（数量）'
		y_title = '数量'
	if with_index:
		title_top = f"{index_code}{'（K线）' if index_style=='candle' else '（归一化）'}"
		fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
					subplot_titles=(title_top, f"连板梯队按层级堆叠柱{title_suffix}"),
					specs=[[{}],[{"secondary_y": True}]])
		if index_style == 'candle':
			idx = _load_index_df(index_code, df.index)
			fig.add_trace(
				go.Candlestick(
					x=idx.index, open=idx['open'], high=idx['high'], low=idx['low'], close=idx['close'], name=f'{index_code}',
					increasing_line_color='red', increasing_fillcolor='red',
					decreasing_line_color='green', decreasing_fillcolor='green'
				),
				row=1, col=1
			)
		else:
			ser = _index_norm_series(index_code, df.index)
			fig.add_trace(go.Scatter(x=ser.index, y=ser.values, mode='lines', name=f'{index_code}', line=dict(color='#1f77b4')), row=1, col=1)
		row2 = (2, 1)
	else:
		fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])
		row2 = (1, 1)
	# 从低到高堆叠
	stack_order = [f'L{i}' for i in range(1, max_level)] + [f'L{max_level}', f'L{max_level}p']
	name_map = {f'L{i}': f'{i}板' for i in range(1, max_level)}
	name_map.update({f'L{max_level}': f'{max_level}板', f'L{max_level}p': f'{max_level}+'})
	for col in stack_order:
		trace = go.Bar(x=df.index, y=plot_df[col].values, name=name_map[col])
		fig.add_trace(trace, row=row2[0], col=row2[1], secondary_y=False)
	if with_max_line:
		line = go.Scatter(
			x=df.index, y=df['max_level_hit'].values, name='当日最高板', mode='lines+markers',
			line=dict(color='#111111', width=3), marker=dict(size=7)
		)
		fig.add_trace(line, row=row2[0], col=row2[1], secondary_y=True)
	# 坐标轴与布局
	fig.update_layout(barmode='stack', title=f"连板梯队按层级堆叠柱{title_suffix}（最近{days}日）",
		legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), margin=dict(l=40, r=20, t=60, b=40))
	if with_index:
		fig.update_layout(height=720)
		fig.update_yaxes(title_text=('指数' if index_style=='candle' else '指数(归一)'), row=1, col=1)
		fig.update_yaxes(title_text=y_title, row=2, col=1, secondary_y=False)
		fig.update_yaxes(title_text='最高板(级)', row=2, col=1, secondary_y=True, range=[0, max_level])
	else:
		fig.update_layout(height=560)
		fig.update_yaxes(title_text=y_title, row=1, col=1, secondary_y=False)
		fig.update_yaxes(title_text='最高板(级)', row=1, col=1, secondary_y=True, range=[0, max_level])
	return fig


def main():
	p = argparse.ArgumentParser(description='Plotly: 指数/热力图/堆叠柱 展示连板梯队')
	p.add_argument('--mode', choices=['index', 'heatmap', 'stacked'], default='index', help='展示模式')
	p.add_argument('--index', default='000001.SH', help='指数代码（index模式或 with-index 时用）')
	p.add_argument('--index-style', choices=['line', 'candle'], default='candle', help='指数展示样式')
	p.add_argument('--days', type=int, default=120, help='最近N天')
	p.add_argument('--metric', default='high', help='index模式下的指标: b1/b2/b3/b4p/high/total')
	p.add_argument('--rebuild', action='store_true', help='重算缓存')
	p.add_argument('--out', default='data/plots/ladder_plotly.html', help='输出HTML路径')
	p.add_argument('--max-level', type=int, default=8, help='分层最大板数，额外一层为 max-level+ 汇总')
	p.add_argument('--share', action='store_true', help='热力图/堆叠柱使用占比而非数量')
	p.add_argument('--with-max-line', action='store_true', help='堆叠柱叠加当日最高板折线')
	p.add_argument('--with-index', action='store_true', help='在热力图/堆叠柱上方加入指数对比')
	args = p.parse_args()

	if args.mode == 'index':
		fig = build_figure_index(args.index, args.days, args.metric, args.rebuild, args.index_style)
	elif args.mode == 'heatmap':
		fig = build_figure_heatmap(args.days, args.rebuild, args.max_level, args.share, args.with_index, args.index, args.index_style)
	else:
		fig = build_figure_stacked(args.days, args.rebuild, args.max_level, args.share, args.with_max_line, args.with_index, args.index, args.index_style)

	out = Path(args.out)
	out.parent.mkdir(parents=True, exist_ok=True)
	fig.write_html(str(out), include_plotlyjs='cdn', full_html=True)
	print(f'✅ 已生成: {out}')


if __name__ == '__main__':
	main()
