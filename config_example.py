"""
配置文件示例 - 参数调优中心
可复制为 config.py 然后在各模块中导入
"""

# ========== 数据配置 ==========
DATA_CONFIG = {
    "universe": {
        "top_n": 100,              # 宇宙规模（流动性排名）
        "exclude_st": True,         # 排除ST股
        "lookback_days": 365 * 2,  # 历史回溯天数
    },
    "cache": {
        "format": "parquet",        # 缓存格式：parquet / csv
        "compression": "snappy",    # 压缩方式
    },
}

# ========== 技术指标配置 ==========
TECHNICAL_CONFIG = {
    "moving_average": {
        "fast": 5,                  # 短期均线周期
        "slow": 20,                 # 长期均线周期
    },
    "momentum": {
        "period": 5,                # 动量计算周期
        "percentile_threshold": 0.6, # 动量百分位阈值（>60%为强动量）
    },
    "volatility": {
        "period": 20,               # 波动率计算周期
        "percentile_threshold": 0.8, # 波动百分位阈值（<80%为低波动）
    },
    "volume": {
        "period": 20,               # 成交量均线周期
        "ratio_threshold": 1.0,     # 成交量倍数阈值
    },
}

# ========== 信号配置 ==========
SIGNAL_CONFIG = {
    "entry_conditions": {
        "ma_crossover": True,       # 均线交叉条件启用
        "momentum_filter": True,    # 动量过滤启用
        "volatility_filter": True,  # 波动过滤启用
        "volume_filter": True,      # 成交量过滤启用
    },
    "exit_conditions": {
        "ma_breakdown": True,       # 均线回破出场
        "max_hold_days": 5,         # 最大持仓天数（可选）
        "stop_loss_pct": None,      # 止损比例，如0.05表示5%
        "take_profit_pct": None,    # 止盈比例
    },
}

# ========== 市场宽度/情绪配置 ==========
BREADTH_CONFIG = {
    "indicators": {
        "ad_ratio_weight": 0.5,     # 涨跌比权重
        "nh_nl_ratio_weight": 0.3,  # 52周高低比权重
        "limit_up_weight": 0.2,     # 涨停比例权重
    },
    "smoothing": {
        "ema_span": 5,              # EMA平滑窗口
    },
    "regime": {
        "bull_threshold": 0.5,      # Bull状态阈值（>0.5）
        "bear_threshold": -0.5,     # Bear状态阈值（<-0.5）
        "neutral_range": (-0.5, 0.5), # Neutral范围
    },
}

# ========== 风控配置 ==========
RISK_CONFIG = {
    "regime_filter": {
        "enabled": True,
        "reject_bear": True,        # 熊市是否拒绝所有交易
    },
    "top_k_selection": {
        "enabled": True,
        "k": 20,                    # 每日最多选K个标的
    },
    "position_scaling": {
        "enabled": True,
        "min_scale": 0.2,           # 最低仓位缩放（20%）
        "max_scale": 1.0,           # 最高仓位缩放（100%）
        "use_sigmoid": True,        # 使用Sigmoid平滑缩放
    },
    "max_positions": 20,            # 最大同时持仓数
    "max_position_weight": 0.1,     # 单个标的最大权重（10%）
}

# ========== 回测配置 ==========
BACKTEST_CONFIG = {
    "engine": "simple",             # simple 或 vectorbt
    "init_cash": 100_000,           # 初始资金（元）
    "trading_days": 252,            # 年交易天数
    "commissions": {
        "fees": 0.0003,             # 手续费率（0.03%）
        "slippage": 0.0005,         # 滑点（0.05%）
        "tax": 0.001,               # 印花税（0.1%，仅卖出）
    },
    "validation": {
        "min_trades": 10,           # 最少交易笔数
        "min_days": 20,             # 最少交易天数
    },
}

# ========== 订单配置 ==========
ORDER_CONFIG = {
    "export": {
        "format": "csv",            # 导出格式
        "encoding": "utf-8-sig",    # 编码
        "top_n": 20,                # 最多导出N个信号
    },
    "allocation": {
        "method": "equal",          # equal 等权 或 weighted 加权
        "weight_by": "score",       # 加权依据：score 或其他
    },
}

# ========== 日志配置 ==========
LOG_CONFIG = {
    "level": "INFO",                # DEBUG / INFO / WARNING / ERROR
    "file": "logs/a-share-agent.log",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# ========== 调度配置（可选） ==========
SCHEDULE_CONFIG = {
    "breadth": {
        "time": "15:10",            # 每日运行时间
        "weekdays": "1-5",          # 周一至周五
    },
    "daily": {
        "time": "15:20",
        "weekdays": "1-5",
    },
    "update_universe": {
        "frequency": "weekly",      # weekly / monthly
        "day": "Monday",
    },
}

# ========== 预设方案 ==========

# 保守方案：低风险、稳健性优先
PROFILE_CONSERVATIVE = {
    "DATA_CONFIG": {
        **DATA_CONFIG,
        "universe": {**DATA_CONFIG["universe"], "top_n": 80, "lookback_days": 365*3},
    },
    "TECHNICAL_CONFIG": {
        **TECHNICAL_CONFIG,
        "momentum": {**TECHNICAL_CONFIG["momentum"], "percentile_threshold": 0.7},
        "volatility": {**TECHNICAL_CONFIG["volatility"], "percentile_threshold": 0.7},
    },
    "RISK_CONFIG": {
        **RISK_CONFIG,
        "position_scaling": {**RISK_CONFIG["position_scaling"], "min_scale": 0.3},
    },
    "BACKTEST_CONFIG": {
        **BACKTEST_CONFIG,
        "commissions": {**BACKTEST_CONFIG["commissions"], "fees": 0.0005, "slippage": 0.001},
    },
}

# 激进方案：高收益、快速反应
PROFILE_AGGRESSIVE = {
    "DATA_CONFIG": {
        **DATA_CONFIG,
        "universe": {**DATA_CONFIG["universe"], "top_n": 150, "lookback_days": 365},
    },
    "TECHNICAL_CONFIG": {
        **TECHNICAL_CONFIG,
        "momentum": {**TECHNICAL_CONFIG["momentum"], "percentile_threshold": 0.5},
        "volatility": {**TECHNICAL_CONFIG["volatility"], "percentile_threshold": 0.9},
    },
    "RISK_CONFIG": {
        **RISK_CONFIG,
        "position_scaling": {**RISK_CONFIG["position_scaling"], "min_scale": 0.1},
    },
    "BACKTEST_CONFIG": {
        **BACKTEST_CONFIG,
        "commissions": {**BACKTEST_CONFIG["commissions"], "fees": 0.0001, "slippage": 0.0002},
    },
}

# 平衡方案：适合多数用户（默认）
PROFILE_BALANCED = {
    "DATA_CONFIG": DATA_CONFIG,
    "TECHNICAL_CONFIG": TECHNICAL_CONFIG,
    "SIGNAL_CONFIG": SIGNAL_CONFIG,
    "BREADTH_CONFIG": BREADTH_CONFIG,
    "RISK_CONFIG": RISK_CONFIG,
    "BACKTEST_CONFIG": BACKTEST_CONFIG,
    "ORDER_CONFIG": ORDER_CONFIG,
    "LOG_CONFIG": LOG_CONFIG,
}

# ========== 快速切换 ==========

# 选择活跃方案（可选值：balanced / conservative / aggressive）
ACTIVE_PROFILE = "balanced"

if ACTIVE_PROFILE == "conservative":
    CONFIG = PROFILE_CONSERVATIVE
elif ACTIVE_PROFILE == "aggressive":
    CONFIG = PROFILE_AGGRESSIVE
else:
    CONFIG = PROFILE_BALANCED

if __name__ == "__main__":
    print("A股短线交易系统 - 配置示例")
    print("=" * 60)
    print(f"当前方案: {ACTIVE_PROFILE.upper()}")
    print("=" * 60)
    
    import json
    print(json.dumps(CONFIG, indent=2, ensure_ascii=False, default=str))
    
    print("\n" + "=" * 60)
    print("使用方法：")
    print("1. 复制此文件为 config.py")
    print("2. 在各模块中导入：from config import CONFIG")
    print("3. 使用配置参数调整策略")
    print("=" * 60)
