"""
选股信号与技术面打分
结合动量、波动率、成交量进行排序打分
"""
import pandas as pd
import numpy as np
from .dataio import fetch_panel


def make_signals(codes, start: str, end: str = ""):
    """
    生成入场与出场信号
    
    :param codes: 股票代码列表
    :param start: 开始日期
    :param end: 结束日期
    :return: (closes, entries, exits, score)
        - closes: DataFrame 收盘价面板
        - entries: DataFrame bool 入场信号（均线+动量+波动+成交量）
        - exits: DataFrame bool 出场信号（均线反转）
        - score: DataFrame float 排序打分（动量百分位 - 波动百分位）
    """
    print(f"[signals] 生成 {len(codes)} 只股票的选股信号...")
    
    panels = fetch_panel(codes, start, end)
    
    # 提取面板数据
    closes = pd.concat({k: v["close"] for k, v in panels.items()}, axis=1).dropna(how="all")
    vols = pd.concat({k: v["volume"] for k, v in panels.items()}, axis=1).reindex_like(closes)
    
    # 技术指标
    # 均线
    ma5 = closes.rolling(5, min_periods=1).mean()
    ma20 = closes.rolling(20, min_periods=1).mean()
    
    # 动量（5日涨跌幅）
    mom5 = closes.pct_change(5)
    
    # 波动率（20日收益率标准差）
    vol20 = closes.pct_change().rolling(20, min_periods=1).std()
    
    # 成交量比（相对20日均值）
    vr = vols / vols.rolling(20, min_periods=1).mean()
    
    # 排序打分
    q_mom = mom5.rank(axis=1, pct=True)  # 动量百分位排名
    q_vol = vol20.rank(axis=1, pct=True)  # 波动百分位排名
    score = q_mom - q_vol  # 高动量低波动优先
    
    # 入场条件（多条件AND）
    entries = (
        (ma5 > ma20)  # 短期均线上穿长期
        & (q_mom > 0.6)  # 动量排名前40%
        & (q_vol < 0.8)  # 波动排名后20%（偏低）
        & (vr > 1)  # 成交量放大
    )
    
    # 出场条件（单条件）
    exits = ma5 < ma20  # 短期均线回破长期
    
    print(f"[signals] 完成，面板 shape={closes.shape}")
    return closes, entries.fillna(False), exits.fillna(False), score.fillna(0)


if __name__ == "__main__":
    from datetime import datetime, timedelta
    
    codes = ["000001", "000002", "600000"]
    start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")
    
    closes, entries, exits, score = make_signals(codes, start)
    print(f"\nEntries 形状: {entries.shape}, True 比例: {entries.sum().sum() / entries.size:.2%}")
    print(f"Score 范围: [{score.min().min():.2f}, {score.max().max():.2f}]")
