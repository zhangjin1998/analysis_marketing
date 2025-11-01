"""
市场宽度与情绪周期
衡量市场整体参与度、涨跌家数比、52周高低分布、涨停比例，
进而识别市场强弱、买卖情绪周期
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .dataio import get_universe, fetch_panel, save_parquet, load_parquet


def _limit_up_threshold(code: str) -> float:
    """
    涨停判定阈值（%）
    创业/科创：20%，其余：10%
    """
    if code.startswith("300") or code.startswith("688"):
        return 19.5
    return 9.8


def compute_breadth(panels: dict) -> pd.DataFrame:
    """
    计算市场宽度指标
    
    :param panels: dict {code: DataFrame}
    :return: DataFrame with 日期索引, 包含以下指标:
        - up_count: 上涨家数
        - down_count: 下跌家数
        - total: 有效股票数
        - nh_252: 52周创高股数
        - nl_252: 52周创低股数
        - limit_up: 涨停股数
        - ad_ratio: (上涨-下跌)/总数
        - nh_ratio: 创高比例
        - nl_ratio: 创低比例
        - zt_ratio: 涨停比例
        - breadth_score: 原始宽度得分（Z-score加权）
        - breadth_score_ema: 5日EMA平滑后的得分
        - regime: 市场状态 (Bull/Neutral/Bear)
    """
    print("[breadth] 计算市场宽度指标...")
    
    # 合并收盘价与涨幅
    closes = pd.concat({k: v["close"] for k, v in panels.items()}, axis=1).dropna(how="all")
    pct = pd.concat({k: v["pct_chg"] for k, v in panels.items()}, axis=1).reindex_like(closes)
    
    # 1. 涨跌统计
    up_count = (pct > 0).sum(axis=1)
    down_count = (pct < 0).sum(axis=1)
    total = pct.notna().sum(axis=1).clip(lower=1)
    
    # 2. 52周高低
    roll_max = closes.rolling(252, min_periods=60).max()
    roll_min = closes.rolling(252, min_periods=60).min()
    nh_252 = (closes >= (roll_max * 0.999)).sum(axis=1)  # 接近52周高
    nl_252 = (closes <= (roll_min * 1.001)).sum(axis=1)  # 接近52周低
    
    # 3. 涨停统计
    th_map = {c: _limit_up_threshold(c) for c in panels.keys()}
    th_df = pd.DataFrame(index=pct.index, columns=pct.columns)
    for c, th in th_map.items():
        if c in th_df.columns:
            th_df[c] = th
    limit_up = (pct >= th_df).sum(axis=1)
    
    # 4. 比例与指标
    ad_ratio = (up_count - down_count) / total
    nh_ratio = nh_252 / total
    nl_ratio = nl_252 / total
    zt_ratio = limit_up / total
    
    # 5. Z-score归一化
    def zscore(s: pd.Series):
        m = s.rolling(252, min_periods=60).mean()
        sd = s.rolling(252, min_periods=60).std().replace(0, np.nan)
        return (s - m) / sd
    
    score = (
        0.5 * zscore(ad_ratio).clip(-3, 3)
        + 0.3 * zscore(nh_ratio - nl_ratio).clip(-3, 3)
        + 0.2 * zscore(zt_ratio).clip(-3, 3)
    )
    score_ema = score.ewm(span=5, adjust=False, min_periods=5).mean()
    
    # 6. 市场态势判定
    regime = pd.Series(index=score_ema.index, dtype="object")
    regime[score_ema > 0.5] = "Bull"
    regime[score_ema < -0.5] = "Bear"
    regime[(score_ema <= 0.5) & (score_ema >= -0.5)] = "Neutral"
    
    out = pd.DataFrame(
        {
            "up_count": up_count,
            "down_count": down_count,
            "total": total,
            "nh_252": nh_252,
            "nl_252": nl_252,
            "limit_up": limit_up,
            "ad_ratio": ad_ratio,
            "nh_ratio": nh_ratio,
            "nl_ratio": nl_ratio,
            "zt_ratio": zt_ratio,
            "breadth_score": score,
            "breadth_score_ema": score_ema,
            "regime": regime,
        }
    ).dropna()
    
    print(f"[breadth] 完成，数据行数: {len(out)}")
    return out


def build_breadth(top_n=120, lookback_days=365 * 2):
    """
    构建完整的市场宽度数据集
    
    :param top_n: 选取流动性最好的前N个股票
    :param lookback_days: 回溯天数（年数 × 365）
    :return: breadth DataFrame
    """
    end = datetime.today()
    start = (end - timedelta(days=lookback_days)).strftime("%Y%m%d")
    
    print(f"[breadth] 构建宽度数据 (top_n={top_n}, 周期={start}~今日)...")
    
    uni = get_universe(top_n=top_n)
    panels = fetch_panel(uni["代码"].tolist(), start=start)
    breadth = compute_breadth(panels)
    
    save_parquet(breadth, "market/breadth.parquet")
    return breadth


if __name__ == "__main__":
    df = build_breadth(top_n=100, lookback_days=365 * 2)
    print("\n最近3个交易日市场状态：")
    print(df[["up_count", "down_count", "breadth_score_ema", "regime"]].tail(3))
