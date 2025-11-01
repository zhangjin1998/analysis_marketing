import os
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np

from .patterns import list_cache_codes, _load_panel_from_cache

THEME_KEYWORDS = [
	("人工智能", ["AI","智","大模型","算力","数据要素","算法","语音","视觉","NLP","AIGC","Sora"]),
	("半导体/芯片", ["芯片","半导体","集成电路","晶圆","封测","EDA","光刻","算力芯片"]),
	("新能源/光伏", ["光伏","硅","逆变","N型","TOPCon","HJT","组件"]),
	("新能源/锂电", ["锂","电池","负极","正极","隔膜","电解液","储能"]),
	("有色金属", ["有色","铜","铝","稀土","锌","镍","钴","黄金"]),
	("煤炭/石油", ["煤","石油","油服","炼化","气" ]),
	("券商/金融", ["证券","券商","期货","保险","银行"]),
	("医药/医疗", ["医药","医疗","中药","创新药","器械","生物"]),
	("白酒/食品", ["白酒","食品","乳业","饮料","酿酒"]),
	("军工/航天", ["军工","航天","导弹","无人机","雷达"]),
	("软件/云", ["软件","云","SaaS","操作系统","数据库"]),
	("汽车/智能驾驶", ["汽车","整车","智能驾驶","激光雷达","车载"]),
	("机器人/制造", ["机器人","自动化","机床","制造","工控"]),
	("地产/建材", ["地产","物业","建材","水泥","玻璃"]),
]


def _to_dot(code: str) -> str:
	return code.replace('_', '.')


def _to_us(code: str) -> str:
	return code.replace('.', '_')


def get_stock_basic_cached(cache_csv: str = "data/meta/stock_basic.csv") -> pd.DataFrame:
	os.makedirs(os.path.dirname(cache_csv), exist_ok=True)
	if os.path.exists(cache_csv):
		try:
			return pd.read_csv(cache_csv)
		except Exception:
			pass
	# 拉取 TuShare 基础信息
	import tushare as ts
	token = os.environ.get('TUSHARE_TOKEN')
	if not token:
		raise RuntimeError("未设置 TUSHARE_TOKEN")
	pro = ts.pro_api(token)
	basics = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry,list_date')
	basics.to_csv(cache_csv, index=False, encoding='utf-8-sig')
	return basics


def _build_code_to_industry(basics: pd.DataFrame) -> Dict[str, str]:
	m: Dict[str, str] = {}
	for _, r in basics.iterrows():
		c = str(r['ts_code'])
		i = str(r.get('industry') if 'industry' in basics.columns else '')
		m[c] = i or ''
		m[_to_us(c)] = i or ''
		# 纯代码（不含后缀）也映射
		pure = c.split('.')[0]
		m[pure] = i or ''
	return m


def _recent_return(series: pd.Series, lookback: int) -> float:
	if series is None or len(series) < lookback + 1:
		return np.nan
	try:
		c0 = float(series.iloc[-lookback - 1])
		c1 = float(series.iloc[-1])
		if c0 <= 0:
			return np.nan
		return (c1 / c0) - 1.0
	except Exception:
		return np.nan


def compute_industry_performance(limit_codes: int = 0) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
	"""
	返回：
	- 行业表现 DataFrame: ['industry','ret5','ret20','count']
	- 每个行业的子面板（用于选龙头）
	"""
	basics = get_stock_basic_cached()
	code2ind = _build_code_to_industry(basics)

	codes = list_cache_codes(limit=limit_codes)
	panels = _load_panel_from_cache(codes)
	if not panels:
		return pd.DataFrame(), {}

	# 计算每只股票的近5/20日收益
	stock_rows = []
	for code, df in panels.items():
		if 'close' not in df.columns:
			continue
		ret5 = _recent_return(df['close'], 5)
		ret20 = _recent_return(df['close'], 20)
		ind = code2ind.get(code) or code2ind.get(_to_dot(code)) or code2ind.get(_to_us(code)) or ''
		stock_rows.append({
			'code': code,
			'industry': ind or '未分类',
			'ret5': ret5,
			'ret20': ret20,
		})
	stock_df = pd.DataFrame(stock_rows)
	if stock_df.empty:
		return pd.DataFrame(), {}

	# 行业聚合：用中位数更稳健
	agg = stock_df.groupby('industry').agg(
		ret5=('ret5', 'median'),
		ret20=('ret20', 'median'),
		count=('code', 'count')
	).reset_index().sort_values(['ret20','ret5'], ascending=False)

	# 行业->子表
	subpanels: Dict[str, pd.DataFrame] = {}
	for ind, sub in stock_df.groupby('industry'):
		subpanels[ind] = sub.sort_values(['ret20','ret5'], ascending=False)

	return agg, subpanels


def top_themes_with_leaders(top_k: int = 5, per_theme: int = 2, limit_codes: int = 0) -> str:
	# 优先用行业聚合；失败时回退到候选池关键词聚类
	try:
		agg, sub = compute_industry_performance(limit_codes=limit_codes)
		if agg is not None and not agg.empty:
			out = [f"🔥 题材/行业强度榜（按近20日中位收益）- Top{top_k}"]
			for _, row in agg.head(top_k).iterrows():
				ind = row['industry']
				ret20 = row['ret20']
				ret5 = row['ret5']
				cnt = int(row['count'])
				out.append(f"- {ind} | 近20日: {ret20:+.2%} | 近5日: {ret5:+.2%} | 覆盖: {cnt} 只")
				leaders = sub.get(ind, pd.DataFrame()).head(per_theme)
				for i, r in leaders.iterrows():
					out.append(f"   · 龙头候选: {r['code']} | 20日:{r['ret20']:+.2%} 5日:{r['ret5']:+.2%}")
			return "\n".join(out)
	except Exception:
		pass
	# 回退：基于候选池名称关键词
	cand_csv = "analyse_marketing/out/daily_candidates.csv"
	if not os.path.exists(cand_csv):
		return "未能计算题材（缺少候选池/基础信息权限受限）"
	df = pd.read_csv(cand_csv)
	if df is None or df.empty:
		return "候选池为空，无法计算题材"
	# 统一列
	name_col = 'name' if 'name' in df.columns else None
	ret20_col = 'ret20' if 'ret20' in df.columns else None
	ret5_col = 'ret5' if 'ret5' in df.columns else None
	if name_col is None:
		return "候选池缺少名称列"
	# 计算主题打分（用ret20优先，其次RS60/RS20/Score）
	score = None
	if ret20_col and ret20_col in df.columns:
		score = df[ret20_col]
	elif 'RS60' in df.columns:
		score = df['RS60']
	elif 'Score' in df.columns:
		score = df['Score']
	else:
		score = pd.Series(np.zeros(len(df)))
	
	theme_rows = []
	for theme, keys in THEME_KEYWORDS:
		mask = pd.Series(False, index=df.index)
		for k in keys:
			mask = mask | df[name_col].astype(str).str.contains(k, case=False, na=False)
		if mask.any():
			df_sub = df[mask].copy()
			median_score = score[mask].median()
			# 简单“龙头”：取子集中得分Top
			lead_cols = ['ts_code'] if 'ts_code' in df_sub.columns else (['code'] if 'code' in df_sub.columns else [])
			leaders = []
			if lead_cols:
				col = lead_cols[0]
				df_sub = df_sub.assign(_score=score[mask]).sort_values('_score', ascending=False)
				for _, r in df_sub.head(3).iterrows():
					leaders.append(str(r[col]))
			theme_rows.append({
				'theme': theme,
				'score': median_score,
				'leaders': leaders[:per_theme]
			})
	if not theme_rows:
		return "候选池未识别出明显题材"
	out_df = pd.DataFrame(theme_rows).sort_values('score', ascending=False)
	lines = [f"🔥 题材热点（候选池回退，按近20日/RS/Score）- Top{top_k}"]
	for _, r in out_df.head(top_k).iterrows():
		leaders_txt = ', '.join(r['leaders']) if isinstance(r['leaders'], list) else '-'
		lines.append(f"- {r['theme']} | 得分:{r['score']:.3f} | 龙头候选: {leaders_txt}")
	return "\n".join(lines)
