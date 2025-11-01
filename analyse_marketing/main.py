import os, sys, argparse, yaml
import time
from pathlib import Path
from typing import Dict, List
import numpy as np
import pandas as pd
from tqdm import tqdm

from utils import get_pro, ensure_dir, cache_path, save_parquet, load_parquet, sleep_rate, \
                  get_universe_from_indices, fetch_daily_history, fetch_index_history, clean_stock_list, \
                  universe_from_daily_fallback, get_index_constituents_from_eastmoney, list_cached_ts_codes, \
                  apply_style_profile
from indicators import resample_weekly
from pipeline import compute_indicators_stock, last_row_ok, candidate_score, compute_weekly_gate, focus_template

def load_config(path: str) -> Dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_stock_basics(pro, retries: int = 3, wait_seconds: int = 65) -> pd.DataFrame:
    for attempt in range(retries + 1):
        try:
            basics = pro.stock_basic(exchange='', list_status='L',
                                     fields='ts_code,symbol,name,area,industry,market,list_date')
            return basics
        except Exception as e:
            msg = str(e)
            if ('每分钟最多访问该接口1次' in msg or 'exceeded' in msg.lower()) and attempt < retries:
                time.sleep(wait_seconds)
                continue
            raise

def build_universe(pro, cfg: Dict, offline: bool=False) -> pd.DataFrame:
    if offline:
        cached = list_cached_ts_codes(cfg.get('cache_dir', './cache'))
        basics = pd.DataFrame({'ts_code': cached})
        basics['name'] = basics['ts_code']
        basics['list_date'] = '20000101'
    else:
        try:
            basics = get_stock_basics(pro)
        except Exception as e:
            msg = str(e)
            print(f"[WARN] stock_basic 不可用：{msg}，切换到 daily 回退构造 Universe")
            basics = universe_from_daily_fallback(pro, cfg)
    basics = clean_stock_list(basics, cfg)
    idx_list = cfg.get('index_basket', [])
    if not offline and idx_list:
        uni_codes = get_universe_from_indices(pro, idx_list, cfg.get('sleep_per_call', 0.35))
        if len(uni_codes) == 0:
            # 回退到东财指数成分
            all_codes = set()
            for idx in idx_list:
                em_codes = get_index_constituents_from_eastmoney(idx)
                all_codes.update(em_codes)
            uni_codes = sorted(list(all_codes))
            if len(uni_codes) == 0:
                print("[WARN] 指数成分（TuShare/东财）均不可用，保留全市场基础清单")
        if len(uni_codes) > 0:
            basics = basics[basics['ts_code'].isin(uni_codes)]
    return basics

def history_with_cache(pro, ts_code: str, start_date: str, cache_dir: str, sleep: float, offline: bool=False) -> pd.DataFrame:
    cpath = cache_path(cache_dir, 'daily', ts_code)
    if offline:
        if os.path.exists(cpath):
            return load_parquet(cpath)
        return pd.DataFrame()
    if os.path.exists(cpath):
        df = load_parquet(cpath)
        last_date = df['trade_date'].max()
        # 若已有，增量拉取新数据
        df_new = fetch_daily_history(pro, ts_code, start_date=str(int(last_date)+1), sleep=sleep)
        if not df_new.empty:
            df = pd.concat([df, df_new], ignore_index=True).drop_duplicates(subset=['trade_date'])
            save_parquet(df, cpath)
        return df
    else:
        df = fetch_daily_history(pro, ts_code, start_date=start_date, sleep=sleep)
        if not df.empty:
            save_parquet(df, cpath)
        return df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--start', required=True, help='历史开始日，形如 20230101')
    parser.add_argument('--export', default='./out')
    parser.add_argument('--offline', action='store_true', help='仅用本地缓存计算（不请求网络）')
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg = apply_style_profile(cfg)
    ensure_dir(args.export)
    ensure_dir(cfg.get('cache_dir', './cache'))

    pro = None if args.offline else get_pro()

    # 1) 环境闸门（指数篮子）
    index_hist = {}
    if not args.offline:
        for idx in cfg.get('index_basket', []):
            df_idx = fetch_index_history(pro, idx, start_date='20180101', sleep=cfg.get('sleep_per_call',0.35))
            if not df_idx.empty:
                index_hist[idx] = df_idx
    if index_hist:
        env_label, env_table = compute_weekly_gate(index_hist)
        env_table.to_csv(os.path.join(args.export, 'env_gate_indices.csv'), index=False)
    else:
        env_label = "离线/权限不足，已跳过闸门"
        pd.DataFrame([], columns=['index','pass']).to_csv(os.path.join(args.export, 'env_gate_indices.csv'), index=False)
    print(f"[ENV] 周线闸门：{env_label}；情绪阶段（手工/占位）：{cfg.get('sentiment_stage','N/A')}")

    # 2) 构建股票池 Universe（指数成分 ∩ 基础排除）
    universe = build_universe(pro, cfg, offline=args.offline)
    print(f"[INFO] Universe size: {len(universe)}")

    # 3) 逐只取数/缓存/计算指标/硬过滤
    rows = []
    sleep = cfg.get('sleep_per_call', 0.35)
    for _, row in tqdm(universe.iterrows(), total=len(universe), desc="Fetching & computing"):
        code = row['ts_code']
        hist = history_with_cache(pro, code, args.start, cfg.get('cache_dir','./cache'), sleep, offline=args.offline)
        if hist is None or hist.empty or len(hist) < 220:
            continue
        hist = compute_indicators_stock(hist, cfg)
        last = hist.iloc[-1].copy()
        last['ts_code'] = code
        last['name'] = row['name']
        # 筛选阶段剔除 ST
        try:
            if isinstance(last.get('name'), str) and ('ST' in last['name']):
                continue
        except Exception:
            pass
        if np.isnan(last['ma200']):
            continue
        if last_row_ok(last, cfg):
            rows.append(last)

    if not rows:
        print("[WARN] 硬过滤后为空，建议放宽 near_high 或提高 liquidity 下限准确性")
        sys.exit(0)

    base = pd.DataFrame(rows)
    # 4) 基础池规模控制
    base = base.sort_values('amount_ma20', ascending=False).head(cfg.get('base_pool_max', 300)).copy()
    base_out_cols = ['ts_code','name','close','ma10','ma21','ma50','ma200','atr14','atrp','rsi14',
                     'hhvN','near_high','amount_ma20','ret20','ret60']
    base[base_out_cols].to_csv(os.path.join(args.export, 'base_pool.csv'), index=False)

    # 5) 打分（标准化→线性加权）
    # 近高位度: 1 - near_high；流动性：amount_ma20；ATR%：atrp；RS60 用 ret60 代替或接入基准收益差
    cand = base.copy()
    cand['NearHigh'] = 1 - cand['near_high']
    # 分位（0-1）
    def quantile_col(s): 
        return s.rank(pct=True)
    cand['RS60_q'] = quantile_col(cand['ret60'].fillna(0))
    cand['NearHigh_q'] = quantile_col(cand['NearHigh'].fillna(0))
    cand['Liquidity_q'] = quantile_col(cand['amount_ma20'].fillna(0))
    cand['ATRP_q'] = quantile_col((1 - (cand['atrp'] - cand['atrp'].median()).abs()).fillna(0))  # 中性靠近中位的得分更高
    cand['RS20'] = cand['ret20']
    cand['RS60'] = cand['ret60']
    cand['Score'] = cand.apply(lambda r: candidate_score(r, cfg), axis=1)

    cand = cand.sort_values('Score', ascending=False).head(cfg.get('daily_candidates_max',100)).copy()
    cand_out_cols = base_out_cols + ['RS20','RS60','amount_ma20','Score']
    cand[cand_out_cols].to_csv(os.path.join(args.export, 'daily_candidates.csv'), index=False)

    # 6) 盘前 Focus 模板（20–30只，附枢轴草案与当日量能阈值）
    focus = focus_template(cand, cfg.get('focus_max', 30))
    focus.to_csv(os.path.join(args.export, 'focus_template.csv'), index=False)

    print(f"[DONE] 输出已生成于 {args.export}")
    print("  - base_pool.csv（基础池，周更）")
    print("  - daily_candidates.csv（每日候选池，已打分）")
    print("  - focus_template.csv（盘前Focus模板，需人工确认形态/VWAP）")
    print(f"[HINT] 当日量能阈值 = 1.8 × 20日均额；枢轴草案 = 近{cfg.get('near_high_lookback',60)}日高；14:00后做三确认。")

if __name__ == "__main__":
    main()

