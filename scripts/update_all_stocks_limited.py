#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整更新所有股票数据 - 带限速控制（修复 ts_code/日期索引）
遵守 Tushare API 限制: 每分钟最多 50 次调用
"""
import os
import sys
import time
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm

# 优先使用环境变量中的 Token；无则回退到默认值（用户提供）
if not os.environ.get('TUSHARE_TOKEN'):
	os.environ['TUSHARE_TOKEN'] = 'b09f3c651f9fa367d9861d845052e8b4bb461543980a2daad4fff9c7'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'analyse_marketing'))


def _to_ts_code(code: str) -> str:
	"""将 000001_SZ -> 000001.SZ；保持已是点号格式不变。"""
	if '_' in code and '.' not in code:
		return code.replace('_', '.')
	return code


def _last_trade_date_from_df(df: pd.DataFrame) -> str:
	"""从 DataFrame 解析最后一个交易日，返回 YYYYMMDD 字符串。"""
	# 优先 trade_date 列
	if 'trade_date' in df.columns:
		val = df['trade_date'].iloc[-1]
		try:
			d = pd.to_datetime(val)
			return d.strftime('%Y%m%d')
		except Exception:
			pass
	# 尝试索引为日期
	try:
		idx = df.index
		d = pd.to_datetime(idx[-1])
		return d.strftime('%Y%m%d')
	except Exception:
		return '19700101'


def _next_yyyymmdd(yyyymmdd: str) -> str:
	try:
		d = datetime.strptime(yyyymmdd, '%Y%m%d') + timedelta(days=1)
		return d.strftime('%Y%m%d')
	except Exception:
		return '20230101'


def get_pro_simple():
	"""获取 Tushare API"""
	import tushare as ts
	token = os.environ.get('TUSHARE_TOKEN')
	if not token:
		raise RuntimeError("❌ 未设置 TUSHARE_TOKEN")
	return ts.pro_api(token)


def fetch_all_stocks_latest(end_date: str = None):
	"""获取所有股票的最新数据，增量更新到 end_date（默认今日）。"""
	print("=" * 80)
	print("📊 完整更新所有股票数据（带限速）")
	print("=" * 80)
	print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
	print(f"🔑 限速: 每分钟最多 50 次 API 调用")
	print()
	
	pro = get_pro_simple()
	cache_dir = "analyse_marketing/cache"
	daily_dir = os.path.join(cache_dir, 'daily')
	os.makedirs(daily_dir, exist_ok=True)
	
	all_files = [f for f in os.listdir(daily_dir) if f.endswith('.parquet')]
	print(f"📁 找到 {len(all_files)} 只缓存股票")
	
	needs_update = []
	for file in all_files:
		code = file.replace('.parquet', '')
		cpath = os.path.join(daily_dir, file)
		try:
			df = pd.read_parquet(cpath)
			last_date = _last_trade_date_from_df(df)
		except Exception:
			last_date = '19700101'
		needs_update.append((code, last_date))
	
	print(f"🔄 需要检查更新: {len(needs_update)} 只股票\n")
	
	updated_count = 0
	failed_count = 0
	call_count = 0
	minute_start = time.time()
	
	if end_date is None:
		end_date = datetime.today().strftime('%Y%m%d')
	
	pbar = tqdm(total=len(needs_update), desc="进度")
	
	for code, last_date in needs_update:
		try:
			# 限速控制
			call_count += 1
			if call_count > 50:
				print(f"\n⏳ 达到分钟限制，等待中...")
				time.sleep(62)
				call_count = 0
				minute_start = time.time()
			else:
				elapsed = time.time() - minute_start
				expected_time = call_count * 1.2
				if expected_time > elapsed:
					time.sleep(expected_time - elapsed)
			
			cpath = os.path.join(daily_dir, f"{code}.parquet")
			start_date_str = _next_yyyymmdd(last_date)
			ts_code = _to_ts_code(code)
			
			# 拉取增量
			df_new = pro.daily(ts_code=ts_code, start_date=start_date_str, end_date=end_date,
							 fields='ts_code,trade_date,open,high,low,close,vol,amount')
			
			if df_new is not None and len(df_new) > 0:
				# 统一列
				df_new = df_new.copy()
				df_new['trade_date'] = pd.to_datetime(df_new['trade_date'])
				df_new = df_new.sort_values('trade_date')
				df_new = df_new.set_index('trade_date')
				# 兼容列名
				df_new = df_new.rename(columns={'vol': 'vol'})
				
				if os.path.exists(cpath):
					df_old = pd.read_parquet(cpath)
					# 若旧文件无日期索引，尝试从 trade_date 列恢复
					if 'trade_date' in df_old.columns:
						df_old = df_old.copy()
						df_old['trade_date'] = pd.to_datetime(df_old['trade_date'])
						df_old = df_old.set_index('trade_date')
					# 合并去重
					df_combined = pd.concat([df_old, df_new], axis=0)
					df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
					df_combined = df_combined.sort_index()
				else:
					df_combined = df_new
				
				# 保存（保持与系统读取兼容的列名：open/high/low/close/vol）
				df_save = df_combined[['open', 'high', 'low', 'close', 'vol', 'amount', 'ts_code']].copy()
				df_save.to_parquet(cpath)
				updated_count += 1
		
		except Exception:
			failed_count += 1
			# 忽略个别失败，继续
		
		pbar.update(1)
	
	pbar.close()
	
	print("\n" + "=" * 80)
	print(f"✅ 更新完成!")
	print(f"  成功更新: {updated_count} 只")
	print(f"  失败: {failed_count} 只")
	print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
	print("=" * 80)


if __name__ == "__main__":
	try:
		# 把数据补到 2025-10-31
		fetch_all_stocks_latest(end_date='20251031')
		
		# 更新完成后重新计算市场宽度（全量，后续可按需剔除ST）
		print("\n📈 现在重新计算市场宽度...")
		os.system("python3 scripts/update_breadth_today.py")
		# 如生成了 _new 文件，则自动替换
		new_fp = "data/market/breadth_am_integrated_new.parquet"
		old_fp = "data/market/breadth_am_integrated.parquet"
		if os.path.exists(new_fp):
			try:
				os.replace(new_fp, old_fp)
				print("✓ 已用最新宽度文件替换旧文件")
			except Exception:
				pass
		
	except Exception as e:
		print(f"❌ 错误: {e}")
		sys.exit(1)

