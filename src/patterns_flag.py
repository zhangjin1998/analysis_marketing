import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .patterns import list_cache_codes, _load_panel_from_cache, load_st_code_set


def _linreg(y: np.ndarray) -> Tuple[float, float]:
    x = np.arange(len(y))
    if len(y) < 5:
        return 0.0, 0.0
    coef = np.polyfit(x, y, 1)
    y_hat = coef[0] * x + coef[1]
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2) + 1e-9
    r2 = 1 - ss_res / ss_tot
    return coef[0], r2


def _pct_std(prices: np.ndarray) -> float:
    if len(prices) < 3:
        return 0.0
    ret = np.diff(np.log(prices + 1e-9))
    return float(np.nanstd(ret))


def _ma(arr: np.ndarray, w: int) -> np.ndarray:
    if len(arr) < 1:
        return arr
    s = pd.Series(arr)
    return s.rolling(w).mean().to_numpy()


def detect_flag_base_one(ohlc: pd.DataFrame,
                         L_up: int = 90,
                         W_flag_min: int = 7,
                         W_flag_max: int = 25,
                         W_base_min: int = 10,
                         W_base_max: int = 40,
                         require_breakout: bool = False) -> Dict:
    """
    返回命中信息字典，未命中返回空字典。
    规则源自用户给定的量化条件（简化落地版）。
    仅在“窗口截止到最后一日”的场景检测一次（今日判定）。
    """
    if ohlc is None or ohlc.empty:
        return {}
    c = ohlc["close"].astype(float).to_numpy()
    h = ohlc["high"].astype(float).to_numpy()
    l = ohlc["low"].astype(float).to_numpy()
    v = (ohlc["vol"] if "vol" in ohlc.columns else ohlc["close"] * 0 + 1).astype(float).to_numpy()

    n = len(c)
    if n < max(L_up + W_base_max + 10, 120):
        return {}

    # t0：窗口前的近端局部高点（回望 5~10 日内的高点）
    search_back = W_flag_max + 10
    t0_end = n - 1 - 1  # 留出至少1天窗口
    t0_start = max(0, t0_end - search_back)
    seg = c[t0_start:t0_end + 1]
    if len(seg) == 0:
        return {}
    idx_local = int(np.argmax(seg))
    t0 = t0_start + idx_local
    H0 = float(np.max(c[max(0, t0 - 5):t0 + 1]))

    # 上升幅度（翻倍近似）：ret_up >= 0.8 或者 HHV/LLV>=1.8
    lo = float(np.min(c[max(0, t0 - L_up):t0 + 1]))
    if lo <= 0:
        return {}
    ret_up = H0 / lo - 1.0
    ratio_hl = (np.max(c[max(0, t0 - L_up):t0 + 1]) / max(lo, 1e-9))
    if not (ret_up >= 0.8 or ratio_hl >= 1.8):
        return {}

    # 在旗型/平台窗口中检测（窗口尾=最后一日）
    hit = None
    W_candidates = list(range(W_flag_min, W_flag_max + 1)) + list(range(W_base_min, W_base_max + 1))
    W_candidates = sorted(set(W_candidates))

    for W in W_candidates:
        s = n - W
        e = n - 1
        if s < 1 or t0 >= s:  # 要求 t0 在窗口前
            continue
        cw = c[s:e + 1]
        vw = v[s:e + 1]
        minW, maxW = float(np.min(cw)), float(np.max(cw))
        midW = (maxW + minW) / 2.0
        width = (maxW - minW) / max(midW, 1e-9)
        slope, r2 = _linreg(cw)
        slope_pct = slope / max(np.mean(cw), 1e-9)

        # 量能与波动收缩
        pre10 = v[max(0, t0 - 10):t0 + 1]
        pre10 = pre10 if len(pre10) else vw
        vol_shrink_flag = np.mean(vw) / max(np.mean(pre10), 1e-9)
        pre20 = v[max(0, s - 20):s]
        pre60 = c[max(0, s - 60):s]
        std_w = _pct_std(cw)
        std_pre10 = _pct_std(c[max(0, s - 10):s])
        std_pre60 = _pct_std(pre60) if len(pre60) else std_w
        std_shrink_flag = std_w / max(std_pre10, 1e-9)
        std_shrink_base = std_w / max(std_pre60, 1e-9)

        # MA20 约束
        ma20 = _ma(c, 20)
        ma20_win = float(ma20[e]) if not np.isnan(ma20[e]) else np.mean(c[max(0, e - 19):e + 1])
        ma20_prev = float(ma20[e - 5]) if e - 5 >= 0 and not np.isnan(ma20[e - 5]) else np.mean(c[max(0, e - 24):e - 4])
        ma20_slope_pct = (ma20_win - ma20_prev) / max(ma20_prev, 1e-9) / max(5, 1)

        # 旗型条件
        drawdown = (H0 - minW) / max(H0, 1e-9)
        cond_flag = (
            (W_flag_min <= W <= W_flag_max) and
            (0.05 <= drawdown <= 0.30) and
            (-0.006 <= slope_pct <= 0.001) and
            (r2 >= 0.2) and
            (vol_shrink_flag <= 0.8) and
            (std_shrink_flag <= 0.8) and
            (minW >= 0.97 * ma20_win)
        )

        # 平台条件
        cond_base = (
            (W_base_min <= W <= W_base_max) and
            (width <= 0.12) and
            (abs(slope_pct) <= 0.001) and
            (abs(ma20_slope_pct) <= 0.0005) and
            (std_shrink_base <= 0.6) and
            (np.mean(vw) / max(np.mean(pre20) if len(pre20) else np.mean(vw), 1e-9) <= 0.7)
        )

        if cond_flag or cond_base:
            # 突破确认（可选）
            if require_breakout:
                upper = maxW
                vol_ok = v[-1] >= 1.5 * np.mean(vw)
                price_ok = (c[-1] > upper) or (h[-1] > upper)
                if not (vol_ok and price_ok):
                    continue
            hit = {
                "type": "flag" if cond_flag else "base",
                "W": W,
                "ret_up": ret_up,
                "width": width,
                "drawdown": drawdown,
                "slope_pct": slope_pct,
                "r2": r2,
                "vol_shrink_flag": vol_shrink_flag,
                "std_shrink_flag": std_shrink_flag,
                "std_shrink_base": std_shrink_base,
                "ma20_slope_pct": ma20_slope_pct,
                "upper": maxW,
                "lower": minW,
            }
            break

    return hit or {}


def scan_flag_platform_all(limit: int = 0, exclude_st: bool = True, require_breakout: bool = False) -> pd.DataFrame:
    codes = list_cache_codes(limit=limit)
    if exclude_st:
        st_set = load_st_code_set()
        if st_set:
            codes = [c for c in codes if c not in st_set]

    panels = _load_panel_from_cache(codes)
    rows = []
    for code, ohlc in panels.items():
        try:
            hit = detect_flag_base_one(ohlc, require_breakout=require_breakout)
            if hit:
                rows.append({"code": code, **hit})
        except Exception:
            continue
    return pd.DataFrame(rows)

