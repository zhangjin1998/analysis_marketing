import os
import re
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from functools import lru_cache

CACHE_DAILY_DIR = "analyse_marketing/cache/daily"
CANDIDATE_CSV = "analyse_marketing/out/daily_candidates.csv"


def _list_all_codes(limit: int = 200) -> List[str]:
    """从 analyse_marketing 缓存列出部分代码作为候选（若未产出候选池）。"""
    if os.path.exists(CANDIDATE_CSV):
        try:
            df = pd.read_csv(CANDIDATE_CSV)
            # 兼容不同列名（ts_code / code）
            if "ts_code" in df.columns:
                codes = df["ts_code"].dropna().astype(str).tolist()
            elif "code" in df.columns:
                codes = df["code"].dropna().astype(str).tolist()
            else:
                codes = []
            return codes[:limit] if limit else codes
        except Exception:
            pass

    if not os.path.exists(CACHE_DAILY_DIR):
        return []
    files = [f for f in os.listdir(CACHE_DAILY_DIR) if f.endswith(".parquet")]
    codes = [os.path.splitext(f)[0] for f in files]
    return codes[:limit] if limit else codes


def list_cache_codes(limit: int = 0) -> List[str]:
    """列出缓存中全部股票代码（忽略候选池）。limit=0 表示不限制。"""
    if not os.path.exists(CACHE_DAILY_DIR):
        return []
    files = [f for f in os.listdir(CACHE_DAILY_DIR) if f.endswith(".parquet")]
    codes = [os.path.splitext(f)[0] for f in files]
    return codes if not limit or limit <= 0 else codes[:limit]


def _to_variants(ts_code: str) -> List[str]:
    """ts_code 变体：000001.SZ / 000001_SZ / 原样。"""
    variants = {ts_code}
    if '.' in ts_code:
        variants.add(ts_code.replace('.', '_'))
    if '_' in ts_code:
        variants.add(ts_code.replace('_', '.'))
    return list(variants)


@lru_cache(maxsize=1)
def load_st_code_set(cache_csv: str = "data/patterns/st_codes.csv") -> set:
    """加载/构建 ST 股票代码集合（包含点号与下划线两种变体）。
    需要 TUSHARE_TOKEN；若不可用则返回空集合。
    """
    os.makedirs(os.path.dirname(cache_csv), exist_ok=True)
    try:
        if os.path.exists(cache_csv):
            df = pd.read_csv(cache_csv)
            codes = set(df["ts_code"].astype(str).tolist())
            # 变体
            out = set()
            for c in codes:
                out.update(_to_variants(c))
            return out
    except Exception:
        pass

    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        return set()
    try:
        import tushare as ts
        pro = ts.pro_api(token)
        basics = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,list_date')
        basics = basics.dropna(subset=['ts_code','name'])
        st_df = basics[basics['name'].str.contains('ST')].copy()
        if not st_df.empty:
            st_df.to_csv(cache_csv, index=False, encoding='utf-8-sig')
        codes = set(st_df['ts_code'].astype(str).tolist())
        out = set()
        for c in codes:
            out.update(_to_variants(c))
        return out
    except Exception:
        return set()


def _load_panel_from_cache(codes: List[str]) -> Dict[str, pd.DataFrame]:
    """加载 OHLCV 面板，返回 {code: df[open,high,low,close,volume]}。"""
    panels: Dict[str, pd.DataFrame] = {}
    for code in codes:
        path = os.path.join(CACHE_DAILY_DIR, f"{code}.parquet")
        if not os.path.exists(path):
            # 尝试另一种命名（点号 vs 下划线）
            alt = os.path.join(CACHE_DAILY_DIR, f"{code.replace('.', '_')}.parquet")
            if os.path.exists(alt):
                path = alt
            else:
                continue
        try:
            df = pd.read_parquet(path)
            # 兼容字段名
            col_map = {
                "open": ["open", "OPEN"],
                "high": ["high", "HIGH"],
                "low": ["low", "LOW"],
                "close": ["close", "CLOSE"],
                "vol": ["vol", "volume", "VOL", "VOLUME"],
            }
            norm = {}
            for k, aliases in col_map.items():
                for a in aliases:
                    if a in df.columns:
                        norm[k] = df[a]
                        break
            if len(norm) < 4:
                continue
            nd = pd.DataFrame(norm)
            # 索引为日期/交易日（整数或时间戳都可）
            nd = nd.sort_index()
            panels[code] = nd
        except Exception:
            continue
    return panels


def _body(ohlc: pd.DataFrame) -> pd.Series:
    return (ohlc["close"] - ohlc["open"]).abs()


def _upper_shadow(ohlc: pd.DataFrame) -> pd.Series:
    return ohlc["high"] - ohlc[["open", "close"]].max(axis=1)


def _lower_shadow(ohlc: pd.DataFrame) -> pd.Series:
    return ohlc[["open", "close"]].min(axis=1) - ohlc["low"]


def pattern_hammer(ohlc: pd.DataFrame) -> pd.Series:
    """锤子线（简化版）：下影>=2倍实体，上影较短，实体较小。"""
    body = _body(ohlc)
    upper = _upper_shadow(ohlc)
    lower = _lower_shadow(ohlc)
    body_med = body.rolling(20, min_periods=5).median()
    is_small_body = body <= body_med
    cond = (lower >= 2 * body) & (upper <= body * 0.5) & is_small_body
    return cond.fillna(False)


def pattern_bullish_engulfing(ohlc: pd.DataFrame) -> pd.Series:
    """看涨吞没：今日阳线，实体包住昨日实体。"""
    prev_open = ohlc["open"].shift(1)
    prev_close = ohlc["close"].shift(1)
    today_bull = ohlc["close"] > ohlc["open"]
    prev_body = (prev_close - prev_open).abs()
    today_body = _body(ohlc)
    engulf = (ohlc["open"] <= prev_close) & (ohlc["close"] >= prev_open) & (today_body > prev_body)
    return (today_bull & engulf).fillna(False)


def pattern_three_white_soldiers(ohlc: pd.DataFrame) -> pd.Series:
    """三连阳（简化）：连续三日收阳且收盘依次抬高。"""
    up = ohlc["close"] > ohlc["open"]
    cond = up & up.shift(1) & up.shift(2)
    higher_close = (ohlc["close"] > ohlc["close"].shift(1)) & (ohlc["close"].shift(1) > ohlc["close"].shift(2))
    return (cond & higher_close).fillna(False)


def pattern_ma5_cross_ma20(ohlc: pd.DataFrame) -> pd.Series:
    ma5 = ohlc["close"].rolling(5).mean()
    ma20 = ohlc["close"].rolling(20).mean()
    cross_up = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
    return cross_up.fillna(False)


def pattern_break_20d_high_with_volume(ohlc: pd.DataFrame) -> pd.Series:
    high20 = ohlc["close"].rolling(20).max()
    vr = ohlc["vol"] if "vol" in ohlc.columns else (ohlc["close"] * 0)
    vr = vr.astype(float)
    vol_ma20 = vr.rolling(20).mean()
    cond = (ohlc["close"] >= high20) & (vr >= 1.5 * vol_ma20)
    return cond.fillna(False)


def pattern_break_previous_range(ohlc: pd.DataFrame, lookback: int = 10) -> pd.Series:
    """突破近10日震荡区间（收盘>近10日高点，且近10日振幅较低）。"""
    high_n = ohlc["high"].rolling(lookback).max()
    low_n = ohlc["low"].rolling(lookback).min()
    range_pct = (high_n - low_n) / ohlc["close"].rolling(lookback).mean()
    cond = (ohlc["close"] >= high_n) & (range_pct <= 0.06)
    return cond.fillna(False)


PATTERN_MAP = {
    "锤子线": pattern_hammer,
    "看涨吞没": pattern_bullish_engulfing,
    "三连阳": pattern_three_white_soldiers,
    "MA5上穿MA20": pattern_ma5_cross_ma20,
    "放量突破": pattern_break_20d_high_with_volume,
    "突破20日新高": pattern_break_20d_high_with_volume,
    "区间突破": pattern_break_previous_range,
}


def _normalize_patterns(pattern_names: List[str]) -> List[str]:
    if not pattern_names:
        return []
    names = []
    for p in pattern_names:
        p = p.strip()
        if not p:
            continue
        # 简单归一化
        if p in ("金叉", "ma金叉", "ma5金叉"):
            p = "MA5上穿MA20"
        if p in ("新高突破", "20日新高", "突破新高"):
            p = "突破20日新高"
        if p in ("放量新高", "放量上破"):
            p = "放量突破"
        # 强势后平台（十周上涨>=60% 且近1-3周平台震荡）
        if ("十周" in p) or ("10周" in p) or ("涨60" in p) or ("60%" in p) or ("强势平台" in p) or ("强势后平台" in p) or ("平台震荡" in p and ("十" in p or "10" in p)):
            p = "强势后平台"
        names.append(p)
    return names


def detect_patterns_on_candidates(pattern_names: List[str], limit: int = 200, exclude_st: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    在候选池上检测形态。
    返回：
      picks: DataFrame(index=date, columns=code, boolean) 最新一行为筛选结果
      table: DataFrame 纵向列出 code 与命中形态
    """
    names = _normalize_patterns(pattern_names)
    if not names:
        names = ["MA5上穿MA20", "锤子线", "看涨吞没"]

    codes = _list_all_codes(limit=limit)
    if exclude_st:
        st_set = load_st_code_set()
        if st_set:
            codes = [c for c in codes if c not in st_set]
    panels = _load_panel_from_cache(codes)
    if not panels:
        return pd.DataFrame(), pd.DataFrame()

    # 对每只股票计算每个形态布尔序列
    last_index = None
    pattern_hits: Dict[str, Dict[str, bool]] = {}
    picks_matrix = {}

    for code, ohlc in panels.items():
        hit_dict: Dict[str, bool] = {}
        per_code_flags = []
        for name in names:
            fn = PATTERN_MAP.get(name)
            if fn is None:
                continue
            flags = fn(ohlc)
            per_code_flags.append(flags)
            if last_index is None and len(flags.index) > 0:
                last_index = flags.index[-1]
            hit_dict[name] = bool(flags.iloc[-1]) if len(flags) else False
        pattern_hits[code] = hit_dict
        # 联合条件：所选形态全部满足
        if per_code_flags:
            all_ok = per_code_flags[0]
            for f in per_code_flags[1:]:
                all_ok = all_ok & f
            picks_matrix[code] = all_ok

    if not picks_matrix:
        return pd.DataFrame(), pd.DataFrame()

    picks_df = pd.DataFrame(picks_matrix)
    # 仅保留最后一行用于选股
    if last_index is not None and last_index in picks_df.index:
        picks_df = picks_df.loc[[last_index]]

    # 汇总表：仅列出命中的形态
    rows = []
    if picks_df.shape[0] > 0:
        latest = picks_df.iloc[-1]
        for code, is_pick in latest.items():
            if bool(is_pick):
                hit_list = [n for n, v in pattern_hits.get(code, {}).items() if v]
                rows.append({"code": code, "patterns": ", ".join(hit_list)})
    table = pd.DataFrame(rows)
    return picks_df, table


def detect_patterns_on_all(pattern_names: List[str], limit: int = 0, exclude_st: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """在全缓存股票上检测形态。limit=0 表示不限制。"""
    names = _normalize_patterns(pattern_names)
    if not names:
        names = ["MA5上穿MA20", "锤子线", "看涨吞没"]

    codes = list_cache_codes(limit=limit)
    if exclude_st:
        st_set = load_st_code_set()
        if st_set:
            codes = [c for c in codes if c not in st_set]
    panels = _load_panel_from_cache(codes)
    if not panels:
        return pd.DataFrame(), pd.DataFrame()

    last_index = None
    pattern_hits: Dict[str, Dict[str, bool]] = {}
    picks_matrix = {}

    for code, ohlc in panels.items():
        hit_dict: Dict[str, bool] = {}
        per_code_flags = []
        for name in names:
            fn = PATTERN_MAP.get(name)
            if fn is None:
                continue
            flags = fn(ohlc)
            per_code_flags.append(flags)
            if last_index is None and len(flags.index) > 0:
                last_index = flags.index[-1]
            hit_dict[name] = bool(flags.iloc[-1]) if len(flags) else False
        pattern_hits[code] = hit_dict
        if per_code_flags:
            all_ok = per_code_flags[0]
            for f in per_code_flags[1:]:
                all_ok = all_ok & f
            picks_matrix[code] = all_ok

    if not picks_matrix:
        return pd.DataFrame(), pd.DataFrame()

    picks_df = pd.DataFrame(picks_matrix)
    if last_index is not None and last_index in picks_df.index:
        picks_df = picks_df.loc[[last_index]]

    rows = []
    if picks_df.shape[0] > 0:
        latest = picks_df.iloc[-1]
        for code, is_pick in latest.items():
            if bool(is_pick):
                hit_list = [n for n, v in pattern_hits.get(code, {}).items() if v]
                rows.append({"code": code, "patterns": ", ".join(hit_list)})
    table = pd.DataFrame(rows)
    return picks_df, table


def format_pattern_result(picks_df: pd.DataFrame, table: pd.DataFrame, top_k: int = 20) -> str:
    if picks_df is None or picks_df.empty:
        return "今日未命中所选形态"
    latest = picks_df.iloc[-1]
    picked_codes = [c for c, v in latest.items() if bool(v)]
    if not picked_codes:
        return "今日未命中所选形态"
    picked_codes = picked_codes[:top_k]
    lines = ["📋 形态选股结果", f"共 {len(picked_codes)} 只，展示前 {min(top_k, len(picked_codes))} 只:"]
    for i, code in enumerate(picked_codes, 1):
        patterns = None
        if table is not None and not table.empty:
            row = table[table["code"] == code]
            if not row.empty:
                patterns = row.iloc[0]["patterns"]
        lines.append(f"{i}. {code}  | 命中: {patterns or '-'}")
    return "\n".join(lines)


# ===== 扩展形态：强势后平台 =====

def pattern_strong_run_then_platform(ohlc: pd.DataFrame, run_days: int = 75, run_thresh: float = 0.60,
                                     plat_min_days: int = 5, plat_max_days: int = 15,
                                     plat_range_thresh: float = 0.08,
                                     overall_range_days: int = 15, overall_range_cap: float = 0.20) -> pd.Series:
    """
    条件：
    1) 近 run_days（~10周≈50个交易日）累计涨幅 >= run_thresh（60%）
    2) 近 1-3 周（5-15日）高低振幅/均价 <= plat_range_thresh（8%）
    """
    close = ohlc["close"].astype(float)
    # 强势段：近 run_days（≈15周）最大涨幅（相对 run_days 前收盘）
    # 定义： (近run_days内最高收盘 / run_days前收盘 - 1) >= run_thresh
    past = close.shift(run_days)
    win_max = close.rolling(run_days).max()
    run_ret_max = (win_max / past) - 1.0
    strong = run_ret_max >= run_thresh

    # 峰值后的回撤上限（近 run_days 窗口内）：
    # 计算窗口内：从峰值（窗口最高收盘）到其后的最低收盘的回撤比例 ≤ 25%
    def dd_after_peak(arr: np.ndarray) -> float:
        if arr.size == 0:
            return np.nan
        i = int(np.argmax(arr))
        peak = arr[i]
        if peak <= 0 or i == arr.size - 1:
            # 没有后续或异常，按0回撤处理
            after_min = arr[-1]
        else:
            after_min = float(np.min(arr[i:]))
        if peak <= 0:
            return 0.0
        return (peak - after_min) / peak

    dd_series = close.rolling(run_days, min_periods=run_days).apply(dd_after_peak, raw=True)
    dd_ok = dd_series <= 0.25
    # 平台段：在 5/10/15 天窗口中任一满足低振幅
    conds = []
    for w in (plat_min_days, (plat_min_days + plat_max_days)//2, plat_max_days):
        high_n = ohlc["high"].rolling(w).max()
        low_n = ohlc["low"].rolling(w).min()
        mean_n = close.rolling(w).mean()
        range_pct = (high_n - low_n) / mean_n
        conds.append(range_pct <= plat_range_thresh)
    platform = conds[0]
    for c in conds[1:]:
        platform = platform | c

    # 总体波动上限：最近 overall_range_days 天最高-最低不超过 overall_range_cap（20%）
    hi_all = ohlc["high"].rolling(overall_range_days).max()
    lo_all = ohlc["low"].rolling(overall_range_days).min()
    overall_ok = ((hi_all - lo_all) / lo_all) <= overall_range_cap

    return (strong & platform & overall_ok & dd_ok).fillna(False)


# 注册到映射与别名
PATTERN_MAP["强势后平台"] = pattern_strong_run_then_platform
PATTERN_MAP["强势平台"] = pattern_strong_run_then_platform
PATTERN_MAP["十周涨60平台"] = pattern_strong_run_then_platform
PATTERN_MAP["10周涨60平台"] = pattern_strong_run_then_platform
