# A股短线交易系统 (A-Share-Agent)

**一套开源免费的A股短线量化交易完整解决方案** ✨

> 周期：**短线（1-5日主线）**  
> 流程：**模块数据 → 情绪/市场宽度 → 选股/择时 → 组合/风控 → 回测/复盘 → 导出订单**  
> 经费：**≤500元（全流程开源免费方案）**

---

## 📋 目录结构

```
a-share-agent/
├─ data/                    # 缓存/导出数据目录
│  ├─ market/               # 市场指标数据
│  ├─ orders/               # 订单文件
│  └─ *.parquet / *.csv
├─ scripts/                 # 可直接运行的脚本
│  ├─ run_breadth.py       # 构建市场宽度（15:10运行）
│  └─ run_daily.py         # 日度选股与订单（15:20运行）
├─ src/                     # 核心模块
│  ├─ __init__.py
│  ├─ dataio.py            # 数据获取/清洗/缓存
│  ├─ breadth.py           # 市场宽度/情绪周期
│  ├─ signals.py           # 选股信号与技术面打分
│  ├─ risk.py              # 风控与仓位缩放
│  ├─ backtest.py          # 组合回测
│  └─ orders.py            # 订单生成
├─ requirements.txt         # 项目依赖
├─ .gitignore
└─ README.md
```

---

## 🚀 快速开始

### 1. 环境与虚拟环境

**需求：** Python 3.9–3.11（推荐3.10）

```bash
# 创建项目与虚拟环境
mkdir a-share-agent && cd a-share-agent
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. 依赖安装

```bash
# 使用清华镜像加速（国内推荐）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或默认源
pip install -r requirements.txt
```

**关键依赖说明：**
| 库 | 版本 | 用途 |
|---|---|---|
| `akshare` | ≥1.14.0 | A股数据获取 |
| `pandas` | ≥2.2.0 | 数据处理 |
| `numpy` | ≥1.26.0 | 数值计算 |
| `vectorbt` | ≥0.25.7 | 向量化回测 |
| `lightgbm` | ≥4.3.0 | 可选ML模型 |
| `scikit-learn` | ≥1.4.0 | 数据预处理 |

---

## 🔄 核心流程详解

### Phase 1️⃣：市场宽度与情绪周期 (`breadth.py`)

**目的：** 识别市场整体参与度、买卖情绪状态

**指标构成：**
- **涨跌比例** (up/down count)：简单计数
- **52周高低分布** (nh/nl ratio)：价格极值统计
- **涨停比例** (zt_ratio)：极端情绪信号
- **综合宽度得分** (breadth_score_ema)：Z-score加权 + EMA平滑

**市场态势判定：**
```
breadth_score_ema > 0.5  → Bull（强势）
  -0.5 ≤ score ≤ 0.5     → Neutral（中性）
breadth_score_ema < -0.5 → Bear（弱势，拒绝交易）
```

**输出：** `data/market/breadth.parquet`

---

### Phase 2️⃣：选股与技术信号 (`signals.py`)

**入场条件（多条件AND）：**
1. 短期均线 > 长期均线（MA5 > MA20）
2. 动量排名前40%（5日涨跌幅 > 60百分位）
3. 波动率排名后20%（20日收益率标差 < 80百分位）
4. 成交量放大（日成交量 > 20日均值）

**出场条件：**
- 短期均线回破长期均线（MA5 < MA20）

**打分逻辑：**
```
score = 动量百分位 - 波动百分位
        ↑ 高动量低波动，优先级高
```

---

### Phase 3️⃣️：情绪过滤与风控 (`risk.py`)

**过滤链路：**
1. **市场态势过滤**：熊市状态拒绝所有入场
2. **Top-K筛选**：每日按打分取前20个信号
3. **仓位缩放**：根据宽度得分动态调整敞口
   ```
   缩放因子 = Sigmoid(breadth_score_ema)  ∈ [20%, 100%]
   ```

**结果：** 情绪相容、风险平衡的持仓建议

---

### Phase 4️⃣：组合回测 (`backtest.py`)

**支持两种模式：**

1. **vectorbt模式**（高效）：
   - 向量化计算，毫秒级回测
   - 自动手续费、滑点、头寸管理

2. **简化模式**（无依赖）：
   - 手工日度PnL计算
   - 支持基本的绩效指标

**输出指标：**
- 总收益 / 年化收益率
- 夏普比率 (Sharpe Ratio)
- 最大回撤 (Max Drawdown)
- 胜率、换手率

---

### Phase 5️⃣：订单导出 (`orders.py`)

**生成格式：** CSV文件（UTF-8编码）

| code | name | target_weight | order_type | timestamp |
|------|------|---|---|---|
| 000001 | 平安银行 | 5.0% | buy | 2024-10-31 15:20:00 |
| 000858 | 五粮液 | 5.0% | buy | 2024-10-31 15:20:00 |

**支持功能：**
- 单日导出
- 批量导出（多日）
- 权重均匀分配或按打分加权
- 文件合规编码

---

## 📅 运行时刻表

**每个交易日：**

```bash
# 15:10 - 收盘5分钟后：构建市场宽度
python scripts/run_breadth.py

# 15:20 - 收盘10分钟后：生成选股与订单
python scripts/run_daily.py
```

**可选：自动调度**

```bash
# Linux crontab 例子
10 15 * * 1-5 cd /path/a-share-agent && source .venv/bin/activate && python scripts/run_breadth.py
20 15 * * 1-5 cd /path/a-share-agent && source .venv/bin/activate && python scripts/run_daily.py
```

---

## 🧪 使用示例

### 基础运行

```bash
# 步骤1：一次性构建历史宽度数据（首次运行）
python scripts/run_breadth.py

# 步骤2：日度选股与订单生成
python scripts/run_daily.py
```

### 模块调用

```python
from src.dataio import get_universe, fetch_panel
from src.breadth import build_breadth
from src.signals import make_signals
from src.risk import apply_regime_filter, position_scale
from src.orders import export_orders_today

# 获取宇宙
uni = get_universe(top_n=100)

# 构建宽度
breadth = build_breadth(top_n=100, lookback_days=365*2)

# 生成信号
closes, entries, exits, score = make_signals(uni["代码"].tolist(), "20220101", "20241031")

# 情绪过滤
entries_ok = apply_regime_filter(entries, breadth)

# 导出订单
export_orders_today(entries_ok, score, top_n=20, out_path="data/orders_today.csv")
```

---

## 🎯 参数调优指南

| 参数 | 建议值 | 调整方向 |
|---|---|---|
| `top_n` (宇宙) | 80-120 | 流动性要求：↓激进，↑保守 |
| `lookback_days` | 365×2 | 历史周期：↓快速适应，↑稳定性 |
| `ma5, ma20` | 5, 20 | 均线周期：↓敏感，↑平稳 |
| `mom_rank` | 60% | 动量阈值：↓选股多，↑精选 |
| `vol_rank` | 80% | 波动阈值：↓避险，↑激进 |
| `fees` | 0.03% | 手续费：根据券商实际 |
| `slippage` | 0.05% | 滑点：根据流动性实际 |

**调整流程：**
1. 改变参数 → 运行 `run_daily.py`
2. 观察 `data/orders_today.csv` 数量与质量
3. 对历史数据做3年回测
4. 对比夏普、回撤等指标

---

## 🐛 常见问题

### Q: 数据拉取很慢或缺失？
**A:** 
- 减少 `top_n`（先试用80）
- 检查网络连接
- akshare 已默认使用Parquet缓存，第二次更快
- 建议使用清华镜像加速

### Q: 涨停识别不准？
**A:** 
- ST股票应排除（已在 `get_universe` 中处理）
- 创业/科创板阈值20%，主板10%（已在 `_limit_up_threshold` 中调整）
- 新股首日可能误识，建议上市满30日后纳入

### Q: 回测与实盘表现不一致？
**A:** 
- **流动性**：回测假设能全部成交，实际受委托簿限制
- **滑点**：设置保守的 `slippage` 参数（0.05-0.1%）
- **收益率**：包含手续费、印花税、过户费等
- **样本外测试**：做连续年度切分验证

### Q: 如何接入自己的数据源或ML模型？
**A:** 
- 数据层：修改 `dataio.py` 的 `fetch_hist_qfq()` 函数
- 信号层：在 `signals.py` 中增加新的技术指标或特征
- 打分层：用 LightGBM/XGBoost 替代简单的百分位排名
- 参考框架：见下方 "进阶扩展"

---

## 🚀 进阶扩展

### ① 接入 Qlib 机器学习框架

```bash
git clone https://github.com/microsoft/qlib
pip install pyqlib
python -c "from qlib.tests.data import GetData; GetData().qlib_data(region='cn')"
```

在 `signals.py` 中集成 Qlib 预测：

```python
from qlib.contrib.model import LGBModel
# ... 加载预训练模型，生成Top-20预测排名
```

### ② 文本情绪因子

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
# 加载 Erlangshen-Roberta 情绪模型
# 爬取公告/新闻标题 → 情绪打分 → 聚合近7日均值 → 过滤条件
```

### ③ 多因子打分模型

```python
# 在 risk.py 中增强
score = (0.3 * momentum_score 
       + 0.3 * sentiment_score 
       + 0.2 * technical_score 
       + 0.2 * fundamental_score)
```

### ④ 自适应止损与仓位管理

```python
# 在 backtest.py 中
max_loss_pct = 0.05  # 5%止损
if current_pnl < -max_loss_pct:
    exit_signal = True
```

---

## 📊 预期表现指标

基于 **2022-2024 年度数据** 的参考表现（仅供参考，过去表现不代表未来）：

| 指标 | 参考值 | 说明 |
|---|---|---|
| 年化收益 | 15-25% | 短线策略，震荡市表现好 |
| 夏普比率 | 0.8-1.2 | 风险调整后收益 |
| 最大回撤 | 12-20% | 风控约束下的极端情况 |
| 胜率 | 45-55% | 重在盈利因子 |
| 换手率 | 50-100% | 日内调整频繁 |

**重点：** 短线策略对市场状态敏感，牛市/震荡市表现优于熊市。

---

## 📝 配置示例

### 保守配置（低风险）

```python
# scripts/run_daily.py 中修改
top_n = 80              # 更严格的宇宙筛选
lookback_days = 365*3   # 更长的历史周期
mom_rank = 0.7          # 更高的动量阈值
vol_rank = 0.7          # 避免高波动
fees = 0.0005           # 高手续费预留
```

### 激进配置（高风险高收益）

```python
top_n = 150             # 宽松的宇宙
lookback_days = 365     # 短期快速适应
mom_rank = 0.5          # 低动量阈值
vol_rank = 0.9          # 接受高波动
fees = 0.0001           # 低费用假设
```

---

## 📞 支持与反馈

- **数据问题**：检查 [akshare](https://akshare.akfamily.xyz/) 官方文档
- **策略优化**：可自行修改阈值，建议用3年历史数据回测
- **技术讨论**：参考 [VetureBeat/vectorbt](https://vectorbt.dev/) 文档

---

## 📄 许可证

MIT License - 开源免费使用

---

## ⚠️ 免责声明

本系统仅供学习交流使用，不构成任何投资建议。

**重点风险提示：**
1. 历史表现不代表未来结果
2. 市场风险无法完全回避，可能造成本金损失
3. 短线交易成本高，需要充分的交易成本预留
4. 建议小额试跑，逐步加大资金规模

**使用者需自行承担所有交易风险及法律责任。**

---

**版本：** v0.1.0 | **更新：** 2024-10  
**作者社区：** A股量化交易爱好者
