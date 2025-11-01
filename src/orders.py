"""
订单生成与导出
将选股结果转换为可执行的交易订单
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime


def export_orders_today(entries: pd.DataFrame, score: pd.DataFrame = None, 
                       top_n: int = 20, out_path: str = "data/orders_today.csv") -> str:
    """
    导出今日入场信号为CSV订单文件
    
    :param entries: DataFrame bool 入场信号
    :param score: DataFrame float 选股打分（可选，用于排序）
    :param top_n: 最多导出多少个信号
    :param out_path: 输出文件路径
    :return: 文件路径，如果无信号则返回None
    """
    today = entries.index[-1]
    picks = entries.loc[today]
    picks = picks[picks].index.tolist()
    
    if len(picks) == 0:
        print(f"[orders] {today.strftime('%Y-%m-%d')} 无入场信号")
        return None
    
    # 按score排序
    if score is not None:
        picks = score.loc[today][picks].nlargest(top_n).index.tolist()
    else:
        picks = picks[:top_n]
    
    n_picks = len(picks)
    alloc = round(1 / n_picks, 4)
    
    # 创建订单表
    df = pd.DataFrame({
        "code": picks,
        "name": picks,  # 实际应从数据库查询名称
        "target_weight": alloc,
        "order_type": "buy",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    
    # 保存文件
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    
    print(f"[orders] 已导出 {n_picks} 个信号到 {out_path}")
    print(f"[orders] 每个标的目标权重: {alloc:.2%}")
    print(f"[orders] 标的列表: {', '.join(picks[:10])}" + ("..." if n_picks > 10 else ""))
    
    return out_path


def export_orders_batch(entries: pd.DataFrame, scores: pd.DataFrame = None,
                       dates: list = None, output_dir: str = "data/orders") -> list:
    """
    批量导出多个交易日的订单
    
    :param entries: DataFrame bool 入场信号
    :param scores: DataFrame float 打分（可选）
    :param dates: 导出日期列表（默认所有日期）
    :param output_dir: 输出目录
    :return: 生成的文件路径列表
    """
    dates = dates or entries.index.tolist()
    os.makedirs(output_dir, exist_ok=True)
    
    files = []
    for date in dates:
        if date not in entries.index:
            continue
        
        entry_today = entries.loc[[date]]
        score_today = scores.loc[[date]] if scores is not None else None
        
        filename = f"orders_{date.strftime('%Y%m%d')}.csv"
        filepath = os.path.join(output_dir, filename)
        
        result = export_orders_today(entry_today, score_today, out_path=filepath)
        if result:
            files.append(result)
    
    print(f"[orders] 批量导出完成，共 {len(files)} 个订单文件")
    return files


def load_orders(filepath: str) -> pd.DataFrame:
    """加载订单文件"""
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    print(f"[orders] 加载订单 {filepath}, 共 {len(df)} 条")
    return df


def summary_orders(filepath: str) -> dict:
    """
    订单汇总统计
    
    :param filepath: 订单文件路径
    :return: 统计字典
    """
    df = load_orders(filepath)
    return {
        'count': len(df),
        'total_weight': df['target_weight'].sum(),
        'avg_weight': df['target_weight'].mean(),
        'codes': df['code'].tolist(),
    }


if __name__ == "__main__":
    # 示例
    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    entries = pd.DataFrame(
        np.random.rand(10, 50) > 0.85,
        index=dates,
        columns=[f'stock_{i:03d}' for i in range(50)]
    )
    scores = pd.DataFrame(
        np.random.randn(10, 50),
        index=dates,
        columns=entries.columns
    )
    
    # 导出最后一天的订单
    path = export_orders_today(entries, scores, top_n=20)
    if path:
        info = summary_orders(path)
        print(f"\n订单统计: {info}")
