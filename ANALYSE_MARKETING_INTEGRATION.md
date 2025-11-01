# 与 analyse_marketing 集成 - 完整指南

## 🎯 概述

本指南说明如何将短线交易系统与 `analyse_marketing` 项目集成，使用其真实数据源和智能候选池来增强选股效果。

---

## 📊 架构图

```
analyse_marketing                          短线交易系统
(上游：候选池生成)                          (下游：交易执行)

① TuShare数据 ──→
② 指数篮子 ──→  
③ 日线缓存 ──→  [analyse_marketing]  
                      ↓
                 daily_candidates.csv
                 (100个候选)
                      ↓
④ 面板加载 ←─────────────────────
⑤ 市场宽度计算
⑥ 技术信号生成
⑦ 风控过滤 & Top-20筛选
⑧ 订单导出
                      ↓
                 orders_am_integrated.csv
                 (今日交易信号)
```

---

## 🚀 快速开始（5分钟）

### 步骤1：准备 analyse_marketing 数据

```bash
# 进入 analyse_marketing 目录
cd analyse_marketing

# 首次全量拉取数据（需TuShare Token）
export TUSHARE_TOKEN='你的token'
python3 main.py --start 20230101 --export ./out

# 后续日更（用缓存数据）
python3 main.py --start 20240101 --export ./out --offline
```

### 步骤2：运行集成脚本

```bash
# 返回项目根目录
cd ..

# 运行集成版本
python3 scripts/run_with_analyse_marketing.py
```

### 步骤3：查看订单

```bash
cat data/orders_am_integrated.csv
```

---

## 📂 文件结构

### 输入（从 analyse_marketing）

```
analyse_marketing/
├─ cache/daily/                    # TuShare 缓存 (parquet 格式)
│  ├─ 000001_SZ.parquet           # 平安银行
│  ├─ 000858_SZ.parquet           # 五粮液
│  ├─ ...
│  └─ ~4500 个股票文件
│
└─ out/
   ├─ daily_candidates.csv        # 日度候选池（100个精选标的）
   ├─ base_pool.csv               # 基础池（300个）
   └─ focus_template.csv          # 盘前Focus模板
```

### 输出（短线系统生成）

```
data/
├─ market/
│  └─ breadth_am_integrated.parquet   # 市场宽度指标
│
└─ orders_am_integrated.csv           # 今日交易订单
```

---

## 🔌 集成接口说明

### 1. 加载analyse_marketing数据

```python
from src.dataio import load_from_analyse_marketing

# 加载所有缓存数据
panels = load_from_analyse_marketing(
    cache_dir="../analyse_marketing/cache/daily",
    min_records=252  # 最少需要252个交易日
)

# 返回: dict {ts_code: DataFrame}
```

**DataFrame 格式：**
```
                 open    high     low   close    volume    pct_chg
date                                                                
2023-01-02    10.500   10.800   10.400  10.700  50000000      0.50
2023-01-03    10.700   10.900   10.600  10.800  52000000      0.93
...
```

### 2. 加载候选池

```python
from src.dataio import load_daily_candidates

# 加载 analyse_marketing 的每日候选池
candidates = load_daily_candidates(
    output_dir="../analyse_marketing/out"
)

# 返回: list ['000001.SZ', '000858.SZ', ...]
```

### 3. 数据格式转换

```python
from src.dataio import convert_tushare_format

# 将 TuShare 格式转换为标准格式
df_standard = convert_tushare_format(df_tushare)
```

---

## 🎯 集成工作流

### 完整流程

```
运行脚本: python3 scripts/run_with_analyse_marketing.py

    ↓ 步骤1: 加载数据
    加载 4500+ 只股票的面板数据（analyse_marketing 缓存）
    → 面板形状: N日 × 4500列
    
    ↓ 步骤2: 加载候选池
    从 daily_candidates.csv 获取 100 个精选标的
    → 面板过滤: N日 × 100列
    
    ↓ 步骤3: 计算市场宽度
    基于候选池计算市场态势 (Bull/Neutral/Bear)
    → 输出: breadth_am_integrated.parquet
    
    ↓ 步骤4: 生成选股信号
    MA交叉、动量、波动、成交量四重条件
    → 入场信号: M 个
    
    ↓ 步骤5: 风控过滤
    - 熊市拒绝交易
    - Top-20 精选
    - 仓位缩放
    
    ↓ 步骤6: 导出订单
    → 输出: orders_am_integrated.csv
```

---

## 💻 Python API 用法

### 完整示例

```python
import pandas as pd
from src.dataio import (
    load_from_analyse_marketing,
    load_daily_candidates
)
from src.breadth import compute_breadth
from src.signals import make_signals
from src.risk import apply_regime_filter, position_scale
from src.orders import export_orders_today

# 1. 加载数据
panels = load_from_analyse_marketing(
    cache_dir="../analyse_marketing/cache/daily"
)

# 2. 加载候选池（可选）
candidates = load_daily_candidates()
if candidates:
    panels = {k: v for k, v in panels.items() 
              if k in candidates}

# 3. 构建面板
closes = pd.concat({k: v["close"] for k, v in panels.items()}, 
                   axis=1).dropna(how="all")

# 4. 计算市场宽度
breadth = compute_breadth(panels)

# 5. 生成信号
closes_std, entries, exits, score = make_signals(
    list(closes.columns), 
    start_date="20230101"
)

# 6. 风控过滤
entries_filtered = apply_regime_filter(entries, breadth)
scale = position_scale(breadth)

# 7. 导出订单
export_orders_today(entries_filtered, score=score, top_n=20)
```

---

## ⚙️ 配置参数

在 `scripts/run_with_analyse_marketing.py` 中可以调整：

### 数据加载参数

```python
# 最少需要的交易日数
min_records = 60  # 默认 252，调小可快速测试

# 候选池筛选
valid_codes = [c for c in closes.columns if c in candidates]
```

### 选股参数

```python
# 在 src/signals.py 中修改
q_mom > 0.6      # 动量阈值（越高越严格）
q_vol < 0.8      # 波动阈值（越低越稳定）
vr > 1           # 成交量倍数
```

### 风控参数

```python
# 在 src/risk.py 中修改
mask_top = score.rank(ascending=False) <= 20  # Top-K数量
position_scale    # 仓位缩放范围 [20%, 100%]
```

---

## 🔄 推荐工作流

### 日常使用

```bash
# 早上（数据准备）
# 1. 可选：更新 analyse_marketing 缓存
cd analyse_marketing
python3 main.py --start 20240101 --export ./out --offline
cd ..

# 下午收盘后（15:20）
# 2. 运行集成选股
python3 scripts/run_with_analyse_marketing.py

# 3. 查看订单
cat data/orders_am_integrated.csv

# 4. 将订单导入交易软件并执行
```

### 参数优化

```bash
# 修改参数后
# 1. 调整 scripts/run_with_analyse_marketing.py 中的参数
# 2. 重新运行脚本
# 3. 观察订单数量和质量变化
# 4. 用历史数据做回测验证
```

---

## 📊 输出文件格式

### orders_am_integrated.csv

```
code,target_weight,order_type,timestamp
000001.SZ,0.1667,buy,2024-10-31 15:20:00
000858.SZ,0.1667,buy,2024-10-31 15:20:00
600000.SH,0.1667,buy,2024-10-31 15:20:00
```

### breadth_am_integrated.parquet

```
                 up_count  down_count  ad_ratio  breadth_score_ema regime
date                                                                      
2023-01-02            45          55      -0.1             0.012  Neutral
2023-01-03            50          50       0.0             0.025  Neutral
...
2024-10-31            48          52      -0.04           0.156  Neutral
```

---

## 🐛 故障排查

### 问题1：找不到 analyse_marketing 数据

**症状：** `✗ 无法加载面板数据`

**解决：**
```bash
# 1. 检查路径
ls -la ../analyse_marketing/cache/daily/

# 2. 如果为空，需要先运行 analyse_marketing
cd analyse_marketing
export TUSHARE_TOKEN='your_token'
python3 main.py --start 20230101
```

### 问题2：候选池与面板数据不匹配

**症状：** `⚠️  候选池中的代码与面板数据不匹配`

**原因：** 候选池是 `000001.SZ` 格式，但缓存是 `000001_SZ` 格式

**解决：** 脚本已自动处理，无需干预

### 问题3：订单为空

**症状：** `⚠️  今日无入场信号`

**原因：**
- 市场态势为 Bear（熊市）
- 信号条件过严格
- 数据更新不及时

**解决：**
```bash
# 1. 查看市场状态
grep "市场态势" 脚本输出

# 2. 放宽参数后重试
# 在 run_with_analyse_marketing.py 中修改阈值

# 3. 更新 analyse_marketing 缓存
cd analyse_marketing
python3 main.py --start 20240101 --export ./out
```

---

## 📈 性能指标

### 预期数据量

| 指标 | 数值 |
|---|---|
| TuShare 缓存文件数 | ~4500 |
| 每日候选池 | 50-150 |
| 最终交易订单 | 5-20 |

### 预期运行时间

| 操作 | 时间 |
|---|---|
| 加载 4500 个缓存文件 | 10-30秒 |
| 计算市场宽度 | 5秒 |
| 生成信号 | 10秒 |
| 风控过滤 | 2秒 |
| 总耗时 | 30-50秒 |

---

## 🔗 系统集成图

```
外部系统 ────────────────────────────────────────
    ↓
analyse_marketing (上游)
    ├─ TuShare 数据源
    ├─ 指数篮子管理
    ├─ 日线缓存管理
    ├─ 候选池生成 ────────┐
    └─ 市场环境评估       │
                         │
                         ↓
                    ┌──────────────┐
                    │ 集成脚本      │
                    │ (本项目)      │
                    └──────────────┘
                    ├─ 面板数据处理
                    ├─ 市场宽度计算
                    ├─ 技术信号生成
                    ├─ 风控过滤
                    └─ 订单导出
                         │
                         ↓
                    交易执行
                    ├─ 同花顺
                    ├─ 东方财富
                    └─ 其他交易平台
```

---

## 📚 相关文件

- `scripts/run_with_analyse_marketing.py` - 集成运行脚本
- `src/dataio.py` - 数据加载接口
- `REAL_DATA_GUIDE.md` - 真实数据使用指南
- `../analyse_marketing/` - 上游项目

---

## ✅ 集成清单

完成以下步骤确保集成成功：

- [ ] analyse_marketing 已运行，生成了缓存数据
- [ ] cache/daily/ 目录下有 .parquet 文件
- [ ] out/ 目录下有 daily_candidates.csv
- [ ] 短线系统能正常加载面板数据
- [ ] 生成了 orders_am_integrated.csv
- [ ] 订单中包含有效的股票代码和权重

---

## 🎁 示例命令

```bash
# 完整的一条龙运行

# 1. 进入项目目录
cd /path/to/a-share-agent

# 2. 更新 analyse_marketing 缓存（可选）
cd analyse_marketing
export TUSHARE_TOKEN='your_token'
python3 main.py --start 20240101 --export ./out --offline
cd ..

# 3. 运行集成脚本
python3 scripts/run_with_analyse_marketing.py

# 4. 查看结果
cat data/orders_am_integrated.csv

# 5. 导入交易软件并执行
```

---

**祝交易顺利！** 📈

*版本: v0.1.0 | 更新: 2024-10*
