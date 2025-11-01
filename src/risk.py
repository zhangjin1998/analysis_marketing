"""
风险管理与仓位动态缩放
根据市场情绪与宽度调整总体敞口
"""
import pandas as pd
import numpy as np


def apply_regime_filter(entries: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    """
    根据市场态势对入场信号进行过滤
    熊市状态直接拒绝所有入场信号
    
    :param entries: DataFrame bool 原始入场信号
    :param breadth: DataFrame 市场宽度指标，包含 'regime' 列 (Bull/Neutral/Bear)
    :return: DataFrame bool 过滤后的入场信号
    """
    print("[risk] 应用市场态势过滤...")
    
    reg = breadth["regime"].reindex(entries.index).ffill()
    filtered = entries & (reg != "Bear")
    
    print(f"[risk] 过滤前 True 数: {entries.sum().sum()}, 过滤后: {filtered.sum().sum()}")
    return filtered


def position_scale(breadth: pd.DataFrame) -> pd.Series:
    """
    根据市场情绪动态调整仓位缩放因子
    
    利用breadth_score_ema (Z-score EMA)
    - Bull 时期 (>0.5): 70-100%
    - Neutral 时期: 40-70%
    - Bear 时期 (<-0.5): 20-50%
    
    使用Sigmoid函数平滑过渡，保证单调性
    
    :param breadth: DataFrame with 'breadth_score_ema' 列
    :return: Series 每日仓位缩放因子 [0, 1]
    """
    score = breadth["breadth_score_ema"]
    
    # Sigmoid: 1 / (1 + exp(-x)) 映射 [-3, 3] -> [0, 1]
    sig = 1 / (1 + np.exp(-score))
    
    # 线性变换到 [20%, 100%]
    # sig 在 [0, 1] 时，(0.2 + sig) 在 [0.2, 1.2]
    # 再 clip 到 [0, 1] 确保仓位不超过100%
    scale = (0.2 + sig).clip(0, 1)
    
    print(f"[risk] 仓位缩放因子统计 - 均值: {scale.mean():.2%}, 最小: {scale.min():.2%}, 最大: {scale.max():.2%}")
    return scale


def position_size(score: pd.DataFrame, entries: pd.DataFrame, scale: pd.Series, 
                   n_positions: int = 10) -> pd.DataFrame:
    """
    根据信号强度与仓位因子计算持仓权重
    
    :param score: DataFrame 选股打分
    :param entries: DataFrame bool 入场信号
    :param scale: Series 仓位缩放因子
    :param n_positions: 最大同时持仓数
    :return: DataFrame 权重矩阵 [0, 1]，每行和不超过 scale
    """
    print(f"[risk] 计算持仓权重 (最多{n_positions}个)...")
    
    # 取score最高的n_positions个且满足入场条件的股票
    mask_top = score.apply(lambda s: s.rank(ascending=False) <= n_positions, axis=1)
    entries_ok = entries & mask_top
    
    # 按score排序后计算权重
    weights = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    
    for date in score.index:
        active = entries_ok.loc[date]
        if active.sum() > 0:
            # 活跃股票按score排序
            active_idx = score.loc[date][active].nlargest(n_positions).index
            n_active = len(active_idx)
            
            if n_active > 0:
                # 等权分配
                base_weight = 1.0 / n_active
                total_weight = base_weight * n_active * scale[date]  # 受缩放因子影响
                actual_weight = total_weight / n_active  # 归一化到缩放目标
                
                weights.loc[date, active_idx] = actual_weight
    
    return weights


if __name__ == "__main__":
    import numpy as np
    
    # 示例
    score = pd.DataFrame(np.random.randn(100, 50))
    breadth = pd.DataFrame(
        {"breadth_score_ema": np.linspace(-2, 2, 100)},
        index=score.index
    )
    breadth["regime"] = "Neutral"
    breadth.loc[breadth["breadth_score_ema"] > 0.5, "regime"] = "Bull"
    breadth.loc[breadth["breadth_score_ema"] < -0.5, "regime"] = "Bear"
    
    entries = score > 0
    
    filtered = apply_regime_filter(entries, breadth)
    scale_factors = position_scale(breadth)
    print(f"\n仓位缩放因子尾部:\n{scale_factors.tail()}")
