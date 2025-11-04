import os
import time
import json
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
import tushare as ts
import requests
from glob import glob
from src.config import get_with_env  # 新增


def get_pro():
    token = get_with_env('tushare.token', 'TUSHARE_TOKEN')
    if not token:
        raise RuntimeError("请先在 config.json(tushare.token) 或环境变量 TUSHARE_TOKEN 中配置 TuShare Token")
    return ts.pro_api(token)

def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)

def cache_path(cache_dir: str, kind: str, key: str) -> str:
    safe_key = key.replace('.', '_').replace('/', '_')
    return os.path.join(cache_dir, kind, f"{safe_key}.parquet")

def save_parquet(df: pd.DataFrame, path: str):
    ensure_dir(os.path.dirname(path))
    df.to_parquet(path, index=False)

def load_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)

def sleep_rate(s: float):
    if s and s > 0:
        time.sleep(s)

def latest_index_weight(pro, index_code: str) -> pd.DataFrame:
    # TuShare index_weight 按月发布，取最近一月
    w = pro.index_weight(index_code=index_code)
    # 若多期合并，取最近 trade_date
    w['trade_date'] = pd.to_datetime(w['trade_date'])
    latest = w['trade_date'].max()
    return w[w['trade_date'] == latest].copy()

def get_universe_from_indices(pro, index_list: List[str], sleep: float=0.35) -> List[str]:
    codes = set()
    for idx in index_list:
        w = latest_index_weight(pro, idx)
        codes.update(w['con_code'].tolist())  # 股票 ts_code
        sleep_rate(sleep)
    return sorted(list(codes))

def clean_stock_list(df: pd.DataFrame, cfg: Dict) -> pd.DataFrame:
    # 基础排除：ST、上市天数、价格下限、板块选择
    if cfg.get('exclude_st', True):
        df = df[~df['name'].str.contains('ST')]
    # 板块
    if not cfg.get('include_kcb', False):
        df = df[~df['ts_code'].str.startswith('688')]
    if not cfg.get('include_bj', False):
        df = df[~df['ts_code'].str.endswith('.BJ')]
    # 上市天数
    df['list_date'] = pd.to_datetime(df['list_date'])
    df = df[df['list_date'] <= pd.Timestamp.today() - pd.Timedelta(days=cfg.get('min_days_listed', 60))]
    return df

def fetch_daily_history(pro, ts_code: str, start_date: str, end_date: str=None, sleep: float=0.35) -> pd.DataFrame:
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    sleep_rate(sleep)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['amount_rmb'] = df['amount'] * 1000.0
    return df

def fetch_index_history(pro, index_code: str, start_date: str, end_date: str=None, sleep: float=0.35) -> pd.DataFrame:
    try:
        df = pro.index_daily(ts_code=index_code, start_date=start_date, end_date=end_date)
    except Exception:
        df = pd.DataFrame()
    sleep_rate(sleep)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['amount_rmb'] = df['amount'] * 1000.0 if 'amount' in df.columns else 0.0
    return df

# ===== 以下为回退与风格配置等辅助函数（供 main.py 引用） =====

def find_recent_trade_date_via_daily(pro, max_back_days: int = 7) -> str:
    today = pd.Timestamp.today().normalize()
    for i in range(max_back_days):
        d = today - pd.Timedelta(days=i)
        ds = d.strftime('%Y%m%d')
        try:
            df = pro.daily(trade_date=ds)
            if df is not None and not df.empty:
                return ds
        except Exception:
            continue
    return ''

def universe_from_daily_fallback(pro, cfg: Dict) -> pd.DataFrame:
    # 用最近交易日全市场日线构造股票列表（降级用）
    td = find_recent_trade_date_via_daily(pro, 10)
    if not td:
        return pd.DataFrame()
    try:
        df = pro.daily(trade_date=td)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    basics = df[['ts_code']].drop_duplicates().copy()
    basics['name'] = basics['ts_code']
    basics['list_date'] = '20000101'
    # 板块过滤
    if not cfg.get('include_kcb', False):
        basics = basics[~basics['ts_code'].str.startswith('688')]
    if not cfg.get('include_bj', False):
        basics = basics[~basics['ts_code'].str.endswith('.BJ')]
    return basics.reset_index(drop=True)

def list_cached_ts_codes(cache_dir: str, kind: str = 'daily') -> List[str]:
    dirp = os.path.join(cache_dir, kind)
    if not os.path.isdir(dirp):
        return []
    codes: List[str] = []
    for p in glob(os.path.join(dirp, '*.parquet')):
        fn = os.path.basename(p)
        if fn.lower().endswith('.parquet'):
            base = fn[:-8]
            ts_code = base.replace('_', '.')
            codes.append(ts_code)
    return sorted(list(set(codes)))

def _map_index_code_to_em(index_code: str) -> str:
    if index_code.endswith('.CSI'):
        return index_code.replace('.CSI', '.SH')
    return index_code

def get_index_constituents_from_eastmoney(index_code: str, timeout: int = 15) -> List[str]:
    code_em = _map_index_code_to_em(index_code)
    url = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
    params = {
        'reportName': 'RPTA_WEB_INDEX_COMPONENT',
        'columns': 'SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_MARKET_CODE,INDEX_CODE',
        'filter': f'(INDEX_CODE="{code_em}")',
        'pageNumber': 1,
        'pageSize': 5000
    }
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        items = (j.get('data') or {}).get('items') or []
        codes = []
        for it in items:
            code = it.get('SECURITY_CODE') or ''
            if not code:
                secucode = it.get('SECUCODE') or ''
                if secucode:
                    codes.append(secucode)
                continue
            if code.startswith('6'):
                ts_code = f"{code}.SH"
            else:
                ts_code = f"{code}.SZ"
            codes.append(ts_code)
        return sorted(list(set(codes)))
    except Exception:
        return []

def apply_style_profile(cfg: Dict) -> Dict:
    profile = (cfg.get('style_profile') or '').lower()
    if not profile or profile == 'balanced':
        return cfg
    new_cfg = dict(cfg)
    if profile == 'theme':
        new_cfg['style'] = 'theme-momentum'
        new_cfg['liquidity_rmb_min'] = 3e7
        new_cfg['atrp_min'] = max(0.04, float(cfg.get('atrp_min', 0.03)))
        new_cfg['atrp_max'] = 0.20
        new_cfg['weights'] = {'rs60':0.5,'near_high':0.35,'liquidity':0.1,'atrp':0.05}
    elif profile == 'whitehorse':
        new_cfg['style'] = 'whitehorse-exec'
        new_cfg['liquidity_rmb_min'] = 1e8
        new_cfg['atrp_min'] = 0.02
        new_cfg['atrp_max'] = 0.12
        new_cfg['weights'] = {'rs60':0.3,'near_high':0.25,'liquidity':0.35,'atrp':0.1}
    return new_cfg

