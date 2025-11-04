import os
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from pathlib import Path

from analyse_marketing.utils import list_cached_ts_codes
from src.config import get_with_env

CACHE_ROOT_DIR = "analyse_marketing/cache"
OUT_DIR = "data/ladder"


def _read_daily_from_cache(ts_code: str) -> pd.DataFrame:
	path = os.path.join(CACHE_ROOT_DIR, 'daily', ts_code.replace('.', '_') + '.parquet')
	if not os.path.exists(path):
		return pd.DataFrame()
	df = pd.read_parquet(path)
	if df is None or df.empty:
		return pd.DataFrame()
	# 统一时间顺序
	if 'trade_date' in df.columns:
		df['trade_date'] = pd.to_datetime(df['trade_date'])
		df = df.sort_values('trade_date').reset_index(drop=True)
	else:
		# 兼容 index 为日期
		df = df.sort_index()
		if not isinstance(df.index, pd.DatetimeIndex):
			return pd.DataFrame()
		df = df.reset_index().rename(columns={'index': 'trade_date'})
	return df


def _is_20pct_board(ts_code: str) -> bool:
	# 创业板: 300*, 301*； 科创板: 688*
	code = ts_code.split('.')[0]
	return code.startswith('300') or code.startswith('301') or code.startswith('688')


def _is_limit_up(row: pd.Series, prev_close: float, is_20pct: bool) -> bool:
	if prev_close is None or prev_close <= 0:
		return False
	try:
		if 'pct_chg' in row and pd.notna(row['pct_chg']):
			pct = float(row['pct_chg']) / 100.0
		else:
			pct = float(row['close']) / float(prev_close) - 1.0
		th = 0.195 if is_20pct else 0.095
		# 放宽到 19.5% / 9.5% 以容错
		if pct < th:
			return False
		# 进一步用 high==close 近似确认封板（若列存在）
		if 'high' in row and 'close' in row and pd.notna(row['high']) and pd.notna(row['close']):
			if float(row['close']) + 1e-6 < float(row['high']):
				# 盘中未封死也可能，放宽：只要接近
				pass
		return True
	except Exception:
		return False


def compute_streak_series(df: pd.DataFrame, ts_code: str) -> pd.DataFrame:
	"""为单只股票计算每日连板高度（截至当日的连续涨停天数）。"""
	if df is None or df.empty:
		return pd.DataFrame()
	cols = set(df.columns)
	need = {'trade_date', 'close'}
	if not need.issubset(cols):
		return pd.DataFrame()
	is20 = _is_20pct_board(ts_code)
	streaks: List[int] = []
	prev_close = None
	prev_is = False
	for _, row in df.iterrows():
		cur_is = _is_limit_up(row, prev_close, is20)
		if cur_is:
			streaks.append((streaks[-1] + 1) if prev_is else 1)
		else:
			streaks.append(0)
		prev_is = cur_is
		prev_close = float(row['close']) if pd.notna(row['close']) else prev_close
	out = df[['trade_date']].copy()
	out['streak'] = streaks
	out['ts_code'] = ts_code
	return out


def build_ladder(last_n_days: int = 180, max_codes: int = 0) -> pd.DataFrame:
	"""聚合全市场最近 N 天连板梯队分布。
	返回列：date, b1, b2, b3, b4p, high(>=3), total
	"""
	codes = list_cached_ts_codes(CACHE_ROOT_DIR, kind='daily')
	if max_codes and max_codes > 0:
		codes = codes[:max_codes]
	rows: List[pd.DataFrame] = []
	for i, code in enumerate(codes):
		df = _read_daily_from_cache(code)
		if df.empty:
			continue
		if last_n_days and last_n_days > 0:
			df = df.tail(last_n_days)
		ser = compute_streak_series(df, code)
		if ser is not None and not ser.empty:
			rows.append(ser)
	if not rows:
		return pd.DataFrame()
	all_streaks = pd.concat(rows, ignore_index=True)
	all_streaks['date'] = pd.to_datetime(all_streaks['trade_date']).dt.normalize()
	grp = all_streaks.groupby('date')['streak']
	def _cnt(k):
		return (grp.apply(lambda s: np.sum(s == k))).astype(int)
	b1 = _cnt(1)
	b2 = _cnt(2)
	b3 = _cnt(3)
	b4p = grp.apply(lambda s: int(np.sum(s >= 4)))
	df_out = pd.DataFrame({
		'date': b1.index,
		'b1': b1.values,
		'b2': b2.values,
		'b3': b3.values,
		'b4p': b4p.values,
	})
	df_out['high'] = df_out['b3'] + df_out['b4p']
	df_out['total'] = df_out[['b1','b2','b3','b4p']].sum(axis=1)
	df_out = df_out.sort_values('date').reset_index(drop=True)
	# 缓存
	Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
	df_out.to_parquet(os.path.join(OUT_DIR, 'ladder.parquet'), index=False)
	return df_out


def load_ladder() -> pd.DataFrame:
	path = os.path.join(OUT_DIR, 'ladder.parquet')
	if os.path.exists(path):
		try:
			return pd.read_parquet(path)
		except Exception:
			pass
	return pd.DataFrame()


def build_ladder_distribution(last_n_days: int = 180, max_codes: int = 0, max_level: int = 8) -> pd.DataFrame:
	"""计算每天各连板层级的数量分布：L1..Lmax_level, L{max_level}p（>=max_level）以及 total、max_level_hit。
	缓存到 data/ladder/ladder_dist.parquet
	"""
	codes = list_cached_ts_codes(CACHE_ROOT_DIR, kind='daily')
	if max_codes and max_codes > 0:
		codes = codes[:max_codes]
	rows: List[pd.DataFrame] = []
	for code in codes:
		df = _read_daily_from_cache(code)
		if df.empty:
			continue
		if last_n_days and last_n_days > 0:
			df = df.tail(last_n_days)
		ser = compute_streak_series(df, code)
		if ser is not None and not ser.empty:
			rows.append(ser)
	if not rows:
		return pd.DataFrame()
	all_streaks = pd.concat(rows, ignore_index=True)
	all_streaks['date'] = pd.to_datetime(all_streaks['trade_date']).dt.normalize()
	# 按天统计各高度数量
	dates = sorted(all_streaks['date'].unique())
	cols = [f'L{i}' for i in range(1, max_level)] + [f'L{max_level}'] + [f'L{max_level}p']
	data = []
	for d in dates:
		s = all_streaks.loc[all_streaks['date'] == d, 'streak']
		counts = {c: 0 for c in cols}
		max_hit = 0
		for k, v in s.value_counts().items():
			if k <= 0:
				continue
			max_hit = max(max_hit, int(k))
			if k < max_level:
				counts[f'L{int(k)}'] += int(v)
			elif k == max_level:
				counts[f'L{max_level}'] += int(v)
			else:
				counts[f'L{max_level}p'] += int(v)
		total = sum(counts.values())
		row = {'date': d, **counts, 'total': total, 'max_level_hit': max_hit}
		data.append(row)
	df_out = pd.DataFrame(data).sort_values('date').reset_index(drop=True)
	Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
	df_out.to_parquet(os.path.join(OUT_DIR, 'ladder_dist.parquet'), index=False)
	return df_out


def load_ladder_distribution() -> pd.DataFrame:
	path = os.path.join(OUT_DIR, 'ladder_dist.parquet')
	if os.path.exists(path):
		try:
			return pd.read_parquet(path)
		except Exception:
			pass
	return pd.DataFrame()
