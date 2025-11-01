import numpy as np
import pandas as pd

def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()

def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False, min_periods=n).mean()

def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = true_range(df)
    return tr.rolling(n, min_periods=n).mean()

def rsi_wilder(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).abs()
    loss = (-delta.where(delta < 0, 0.0)).abs()
    avg_gain = gain.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def high_n(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).max()

def low_n(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).min()

def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    # 输入：日线，包含 trade_date(YYYYMMDD 或 datetime), open, high, low, close, amount_rmb
    if not np.issubdtype(df['trade_date'].dtype, np.datetime64):
        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date')
    wk = df.set_index('trade_date').resample('W-FRI').agg({
        'open':'first','high':'max','low':'min','close':'last','amount_rmb':'sum'
    }).dropna()
    wk = wk.reset_index().rename(columns={'trade_date':'week'})
    return wk

def pct_change(series: pd.Series, n: int) -> pd.Series:
    return series.pct_change(n)

def zscore(series: pd.Series) -> pd.Series:
    return (series - series.mean()) / (series.std(ddof=0) + 1e-9)

