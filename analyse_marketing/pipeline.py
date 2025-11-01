from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from indicators import sma, ema, atr, rsi_wilder, high_n, resample_weekly, pct_change

def compute_indicators_stock(df: pd.DataFrame, cfg: Dict) -> pd.DataFrame:
    # 需要列：open, high, low, close, amount_rmb, trade_date
    for n in [10,21,50,200]:
        df[f'ma{n}'] = df['close'].rolling(n, min_periods=n).mean()
    df['ema10'] = df['close'].ewm(span=10, adjust=False, min_periods=10).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False, min_periods=21).mean()
    df['atr14'] = atr(df, 14)
    df['atrp'] = df['atr14'] / df['close']
    df['rsi14'] = rsi_wilder(df['close'], 14)
    n = cfg.get('near_high_lookback', 60)
    df['hhvN'] = high_n(df['high'], n)
    df['near_high'] = (df['hhvN'] - df['close']) / df['hhvN']
    df['amount_ma20'] = df['amount_rmb'].rolling(20, min_periods=20).mean()
    # 近60日与20日相对强度（可选：相对指数；此处先用自身动量替代）
    df['ret20'] = df['close'].pct_change(20)
    df['ret60'] = df['close'].pct_change(60)
    return df

def last_row_ok(row: pd.Series, cfg: Dict) -> bool:
    checks = [
        row['close'] > row['ma50'],
        row['ma50'] > row['ma200'],
        row['near_high'] <= cfg.get('near_high_max', 0.05),
        row['amount_ma20'] >= cfg.get('liquidity_rmb_min', 5e7),
        (row['rsi14'] > cfg.get('rsi14_min', 50)) if cfg.get('rsi14_min', None) is not None else True,
        (row['atrp'] >= cfg.get('atrp_min', 0.0)) and (row['atrp'] <= cfg.get('atrp_max', 1.0)),
        row['close'] >= cfg.get('min_price', 5.0)
    ]
    return all(checks)

def candidate_score(row: pd.Series, cfg: Dict) -> float:
    # 分位简化：直接标准化到0-1
    # 需要在外部先生成这几列的分位
    w = cfg.get('weights', {'rs60':0.4,'near_high':0.3,'liquidity':0.2,'atrp':0.1})
    score = (w.get('rs60',0.4)*row['RS60_q'] +
             w.get('near_high',0.3)*row['NearHigh_q'] +
             w.get('liquidity',0.2)*row['Liquidity_q'] +
             w.get('atrp',0.1)*row['ATRP_q'])
    return float(score)

def compute_weekly_gate(index_dfs: Dict[str, pd.DataFrame]) -> Tuple[str, pd.DataFrame]:
    summary = []
    for code, df in index_dfs.items():
        wk = resample_weekly(df[['trade_date','open','high','low','close','amount_rmb']].copy())
        wk['ma20w'] = wk['close'].rolling(20, min_periods=20).mean()
        cond = False
        if len(wk) >= 21:
            last = wk.iloc[-1]
            prev = wk.iloc[-2]
            cond = (last['close'] > last['ma20w']) and (last['ma20w'] > prev['ma20w'])
        summary.append({'index': code, 'pass': cond})
    df_sum = pd.DataFrame(summary)
    ok = (df_sum['pass'].sum() >= (2 if len(summary)>=3 else 1))
    gate = "允许进攻" if ok else "谨慎/防守"
    return gate, df_sum

def focus_template(df: pd.DataFrame, topN: int=30) -> pd.DataFrame:
    # 枢轴草案：近20日高；当日量能阈值：1.8×20日均额；近枢轴程度： (pivot - close)/ATR
    out = df.copy()
    out['pivot_draft'] = out['hhvN']  # N=near_high_lookback
    out['amount_threshold'] = 1.8 * out['amount_ma20']
    out['near_pivot_atr'] = (out['pivot_draft'] - out['close']) / (out['atr14'] + 1e-9)
    # 越接近 0 越好（略高/略低都可），用绝对值排序
    out['near_abs'] = out['near_pivot_atr'].abs()
    out = out.sort_values(['Score','near_abs'], ascending=[False, True]).head(topN)
    # 执行卡字段
    cols = ['ts_code','name','close','pivot_draft','atr14','amount_ma20',
            'amount_threshold','near_pivot_atr','ma10','ma21','ma50','ma200',
            'ema10','ema21','atrp','rsi14','near_high','RS20','RS60','Score']
    return out[cols]

