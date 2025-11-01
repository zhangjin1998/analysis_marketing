"""
组合回测引擎
基于vectorbt进行高性能向量化回测
"""
import pandas as pd
import numpy as np

try:
    import vectorbt as vbt
    VECTORBT_AVAILABLE = True
except ImportError:
    VECTORBT_AVAILABLE = False
    print("[backtest] 警告: vectorbt 未安装，回测功能将受限")


def backtest_portfolio(closes: pd.DataFrame, entries: pd.DataFrame, exits: pd.DataFrame,
                       fees=0.0003, slip=0.0005, init_cash=100_000) -> dict:
    """
    回测投资组合，生成绩效报告
    
    :param closes: DataFrame 收盘价面板
    :param entries: DataFrame bool 入场信号
    :param exits: DataFrame bool 出场信号
    :param fees: float 交易手续费比例 (默认0.03%)
    :param slip: float 滑点 (默认0.05%)
    :param init_cash: float 初始资金 (默认10万)
    :return: dict 包含回测结果统计
    """
    if not VECTORBT_AVAILABLE:
        print("[backtest] vectorbt 不可用，返回空回测结果")
        return {}
    
    print(f"[backtest] 开始回测 (初始资金: ¥{init_cash:,.0f}, 费率: {fees:.2%}, 滑点: {slip:.2%})...")
    
    try:
        pf = vbt.Portfolio.from_signals(
            closes,
            entries,
            exits,
            fees=fees,
            slippage=slip,
            init_cash=init_cash,
            freq="1D"
        )
        
        stats = pf.stats()
        print(f"[backtest] 回测完成")
        return {
            'portfolio': pf,
            'stats': stats,
            'returns': pf.returns(),
            'drawdown': pf.drawdown(),
        }
    
    except Exception as e:
        print(f"[backtest] 回测失败: {e}")
        return {}


def simple_backtest(closes: pd.DataFrame, entries: pd.DataFrame, exits: pd.DataFrame,
                    init_cash=100_000, fees=0.0003) -> pd.DataFrame:
    """
    简化版回测（无vectorbt依赖）
    手工计算净值、收益、回撤等指标
    
    :param closes: DataFrame 收盘价
    :param entries: DataFrame bool 入场信号
    :param exits: DataFrame bool 出场信号
    :param init_cash: 初始资金
    :param fees: 费率
    :return: DataFrame 日度PnL与净值
    """
    print(f"[backtest] 简化回测 (无vectorbt依赖)...")
    
    dates = closes.index
    portfolio_value = [init_cash]
    daily_returns = [0.0]
    holdings = set()  # 当前持仓代码集合
    position_prices = {}  # code -> entry_price
    
    for i in range(1, len(dates)):
        date = dates[i]
        prev_date = dates[i - 1]
        
        # 处理出场信号
        exit_codes = [c for c in holdings if exits.loc[prev_date, c]]
        for code in exit_codes:
            holdings.discard(code)
            if code in position_prices:
                del position_prices[code]
        
        # 处理入场信号
        entry_codes = [c for c in closes.columns if entries.loc[prev_date, c] and c not in holdings]
        for code in entry_codes:
            if len(holdings) < 20:  # 最多20个持仓
                holdings.add(code)
                position_prices[code] = closes.loc[prev_date, code] * (1 + fees)
        
        # 计算日度PnL
        pnl = 0.0
        for code in holdings:
            entry_price = position_prices[code]
            exit_price = closes.loc[date, code] * (1 - fees)
            pnl += (exit_price - entry_price) / entry_price
        
        if len(holdings) > 0:
            daily_pct = pnl / len(holdings)
        else:
            daily_pct = 0.0
        
        portfolio_value.append(portfolio_value[-1] * (1 + daily_pct))
        daily_returns.append(daily_pct)
    
    result = pd.DataFrame({
        'date': dates,
        'value': portfolio_value[:len(dates)],
        'return': daily_returns[:len(dates)],
    }).set_index('date')
    
    result['cumret'] = (1 + result['return']).cumprod() - 1
    
    # 计算关键指标
    total_ret = (result['value'].iloc[-1] - init_cash) / init_cash
    sharpe = result['return'].mean() / result['return'].std() * np.sqrt(252) if result['return'].std() > 0 else 0
    max_dd = (result['value'].cummax() - result['value']).max() / result['value'].cummax().max()
    
    print(f"[backtest] 总收益: {total_ret:.2%}, 夏普: {sharpe:.2f}, 最大回撤: {max_dd:.2%}")
    return result


if __name__ == "__main__":
    # 示例数据
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    closes = pd.DataFrame(
        np.random.randn(252, 10).cumsum(0) + 100,
        index=dates,
        columns=[f'stock_{i}' for i in range(10)]
    )
    entries = pd.DataFrame(np.random.rand(252, 10) > 0.8, index=dates, columns=closes.columns)
    exits = pd.DataFrame(np.random.rand(252, 10) > 0.9, index=dates, columns=closes.columns)
    
    result = simple_backtest(closes, entries, exits, init_cash=100_000)
    print(f"\n回测结果:\n{result.tail()}")
