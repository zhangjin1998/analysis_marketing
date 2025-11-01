"""
数据获取与缓存层
支持：akshare / CSV本地 / analyse_marketing数据源
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import sys

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# 尝试导入 akshare (可选)
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


def today_str(fmt="%Y%m%d"):
    """返回今天的日期字符串"""
    return datetime.today().strftime(fmt)


def get_universe(top_n=120, exclude_st=True):
    """
    获取沪深京A股宇宙
    
    :param top_n: 按成交额排序取前N个
    :param exclude_st: 是否排除ST股
    :return: DataFrame with 代码, 名称, 成交额
    """
    print(f"[dataio] 获取A股宇宙 (top_n={top_n})...")
    try:
        spot = ak.stock_zh_a_spot_em()
        if exclude_st:
            spot = spot[~spot["名称"].str.contains("ST", na=False)]
        uni = spot.sort_values("成交额", ascending=False).head(top_n)[["代码", "名称", "成交额"]]
        return uni.reset_index(drop=True)
    except Exception as e:
        print(f"[dataio] 获取宇宙失败: {e}")
        raise


def fetch_hist_qfq(code: str, start: str, end: str = "") -> pd.DataFrame:
    """
    获取单只股票日线前复权数据
    
    :param code: 股票代码 (e.g., '000001')
    :param start: 开始日期 (e.g., '20220101')
    :param end: 结束日期，默认今天
    :return: DataFrame with date index, columns: open, high, low, close, volume, pct_chg
    """
    end = end or today_str()
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"
        )
        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "涨跌幅": "pct_chg",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        
        # 如果原始数据无涨幅，从close计算
        if "pct_chg" not in df or df["pct_chg"].isna().all():
            df["pct_chg"] = (df["close"].pct_change().fillna(0).values * 100)
        
        return df[["open", "high", "low", "close", "volume", "pct_chg"]]
    except Exception as e:
        print(f"[dataio] 获取 {code} 数据失败: {e}")
        raise


def fetch_panel(codes, start: str, end: str = "") -> dict:
    """
    获取多只股票的面板数据
    
    :param codes: 股票代码列表
    :param start: 开始日期
    :param end: 结束日期
    :return: dict {code: DataFrame}，只保留数据充足的标的（>=252个交易日）
    """
    end = end or today_str()
    out = {}
    failed = []
    
    print(f"[dataio] 拉取 {len(codes)} 只股票面板数据 ({start} ~ {end})...")
    for i, c in enumerate(codes, 1):
        try:
            d = fetch_hist_qfq(c, start, end)
            if len(d) >= 252:  # 至少1年数据
                out[c] = d
            if i % 20 == 0:
                print(f"  已拉取 {i}/{len(codes)}")
        except Exception:
            failed.append(c)
            continue
    
    print(f"[dataio] 成功: {len(out)}/{len(codes)}, 失败: {len(failed)}")
    return out


def save_parquet(df: pd.DataFrame, path: str):
    """保存DataFrame为Parquet格式"""
    full = os.path.join(DATA_DIR, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    df.to_parquet(full, index=True, compression="snappy")
    print(f"[dataio] 保存到 {full}")


def load_parquet(path: str) -> pd.DataFrame:
    """加载Parquet文件"""
    full = os.path.join(DATA_DIR, path)
    df = pd.read_parquet(full)
    print(f"[dataio] 加载 {full}, shape={df.shape}")
    return df


def load_from_analyse_marketing(cache_dir: str = None, min_records: int = 252) -> dict:
    """
    从 analyse_marketing 项目的缓存加载真实数据
    
    :param cache_dir: analyse_marketing 的 cache 目录路径
    :param min_records: 最少需要的记录数
    :return: dict {code: DataFrame}，仅保留数据充足的标的
    """
    if cache_dir is None:
        cache_dir = "../analyse_marketing/cache/daily"
    
    if not os.path.exists(cache_dir):
        print(f"[dataio] 目录不存在: {cache_dir}")
        return {}
    
    print(f"[dataio] 从 analyse_marketing 加载数据 ({cache_dir})...")
    
    out = {}
    parquet_files = [f for f in os.listdir(cache_dir) if f.endswith('.parquet')]
    
    if not parquet_files:
        print(f"[dataio] 未找到 parquet 文件")
        return {}
    
    print(f"[dataio] 发现 {len(parquet_files)} 个缓存文件")
    
    for i, fname in enumerate(parquet_files, 1):
        try:
            ts_code = fname[:-8].replace('_', '.')  # 000001_SZ.parquet -> 000001.SZ
            fpath = os.path.join(cache_dir, fname)
            
            df = pd.read_parquet(fpath)
            
            if len(df) >= min_records:
                # 标准化字段
                if 'trade_date' in df.columns:
                    df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                elif 'date' not in df.columns:
                    continue
                
                # 确保有必需的OHLCV字段
                if not all(col in df.columns for col in ['open', 'high', 'low', 'close', 'vol']):
                    if 'volume' in df.columns and 'vol' not in df.columns:
                        df['vol'] = df['volume']
                    if not all(col in df.columns for col in ['open', 'high', 'low', 'close', 'vol']):
                        continue
                
                # 计算涨幅（如果没有）
                if 'pct_chg' not in df.columns:
                    df['pct_chg'] = df['close'].pct_change().fillna(0).values * 100
                
                df_clean = df.set_index('date')[['open', 'high', 'low', 'close', 'vol', 'pct_chg']].sort_index()
                df_clean.columns = ['open', 'high', 'low', 'close', 'volume', 'pct_chg']
                
                out[ts_code] = df_clean
                
                if i % 50 == 0:
                    print(f"  已加载 {i}/{len(parquet_files)}")
        
        except Exception as e:
            print(f"  ✗ 加载 {fname} 失败: {e}")
            continue
    
    print(f"[dataio] 成功加载 {len(out)} 个标的（>= {min_records} 记录）")
    return out


def load_daily_candidates(output_dir: str = None) -> list:
    """
    从 analyse_marketing 导出的 daily_candidates.csv 获取候选池
    
    :param output_dir: analyse_marketing 的 out 目录路径
    :return: 股票代码列表 [ts_code, ...]
    """
    if output_dir is None:
        output_dir = "../analyse_marketing/out"
    
    candidates_file = os.path.join(output_dir, "daily_candidates.csv")
    
    if not os.path.exists(candidates_file):
        print(f"[dataio] 候选池文件不存在: {candidates_file}")
        return []
    
    try:
        df = pd.read_csv(candidates_file)
        codes = df['ts_code'].tolist()
        print(f"[dataio] 加载候选池: {len(codes)} 个标的")
        return codes
    except Exception as e:
        print(f"[dataio] 加载候选池失败: {e}")
        return []


def convert_tushare_format(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    将 TuShare 格式的数据转换为标准格式
    
    TuShare 格式：trade_date, open, high, low, close, vol, ...
    标准格式：date(index), open, high, low, close, volume, pct_chg
    """
    if df_raw.empty:
        return df_raw
    
    df = df_raw.copy()
    
    # 日期转换
    if 'trade_date' in df.columns:
        df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    else:
        return pd.DataFrame()
    
    # 字段标准化
    field_map = {
        'vol': 'volume',
        'amount': 'amount_rmb',
    }
    df = df.rename(columns=field_map)
    
    # 计算涨幅
    if 'pct_chg' not in df.columns:
        df['pct_chg'] = (df['close'].pct_change().fillna(0) * 100)
    
    # 取必需字段
    required = ['open', 'high', 'low', 'close', 'volume', 'pct_chg']
    available = [col for col in required if col in df.columns]
    
    df_std = df.set_index('date')[available].sort_index()
    
    return df_std
