# 📊 真实全市场数据 - 已启用

## ✅ 数据规模

- **总股票数**: 4666 只（全市场）
- **历史数据**: 1651 个交易日
- **数据来源**: `analyse_marketing/cache/daily/`

## 📈 最新市场数据（2025-11-01）

```
📊 市场宽度分析
├─ 上涨家数: 1040 家
├─ 下跌家数: 1072 家
├─ 市场态势: Neutral 🟡
├─ 宽度得分: -0.399
└─ 推荐仓位: 60.16%
```

## 🔄 每日更新流程

### 方式 1：手动更新（推荐）

```bash
# 收盘后执行
python3 scripts/update_breadth_today.py
```

**过程**:
1. 加载全部 4666 只股票的缓存数据
2. 计算市场宽度指标（1651 个交易日）
3. 生成最新的市场态势判断
4. 更新 `breadth_am_integrated.parquet`

**耗时**: 约 30-60 秒（取决于系统性能）

### 方式 2：自动更新（可选）

Linux/Mac crontab:
```bash
# 每个交易日 15:15 自动更新
15 15 * * 1-5 cd /path/to/a-share-agent && python3 scripts/update_breadth_today.py
```

Windows 任务计划程序:
```batch
python3 scripts/update_breadth_today.py
# 设置每个交易日 15:15 运行
```

## 📊 数据验证

### 检查数据完整性

```bash
python3 << 'EOF'
import pandas as pd
df = pd.read_parquet("data/market/breadth_am_integrated.parquet")

print(f"✅ 数据行数: {len(df)}")
print(f"✅ 最新数据: {df.index[-1]}")
print(f"✅ 上涨家数: {int(df.iloc[-1]['up_count'])}")
print(f"✅ 下跌家数: {int(df.iloc[-1]['down_count'])}")
print(f"✅ 总计: {int(df.iloc[-1]['up_count'] + df.iloc[-1]['down_count'])}")
