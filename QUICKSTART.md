# A股短线交易系统 - 快速启动指南 ⚡

**5分钟内启动完整的选股与订单系统**

---

## 📦 安装步骤

### 1️⃣ 克隆或初始化项目

```bash
cd a-share-agent
```

### 2️⃣ 创建虚拟环境（推荐）

```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3️⃣ 安装依赖

```bash
# 使用清华镜像（国内推荐，快10倍）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或默认源（可能较慢）
pip install -r requirements.txt
```

**预计时间：** 3-10分钟（取决于网络）

---

## 🚀 首次运行

### 第一步：构建市场宽度数据（必须，一次性）

```bash
python scripts/run_breadth.py
```

**做了什么：**
- 获取A股前100个流动性最好的股票
- 计算2年历史的市场宽度、涨跌统计、情绪周期
- 输出：`data/market/breadth.parquet`

**预期耗时：** 10-30分钟（取决于网络）

**成功标志：**
```
✓ 宽度数据已成功保存到 data/market/breadth.parquet
```

---

### 第二步：生成今日选股与订单

```bash
python scripts/run_daily.py
```

**做了什么：**
1. 生成100只股票的技术面选股信号
2. 根据市场情绪过滤（熊市拒绝交易）
3. 按打分选出前20个标的
4. 计算仓位缩放因子
5. 导出CSV订单文件

**输出文件：**
- `data/orders_today.csv` - 可直接用于交易

**预期耗时：** 3-5分钟

**成功标志：**
```
✓ 订单已导出: data/orders_today.csv
✓ 市场状态: Bull/Neutral/Bear
✓ 仓位建议: XX%
```

---

## 📋 输出文件说明

### 1. `data/market/breadth.parquet` 

市场宽度指标表，每行一个交易日，包含：
| 列 | 含义 |
|---|---|
| `up_count` | 上涨家数 |
| `down_count` | 下跌家数 |
| `ad_ratio` | 涨跌比 |
| `breadth_score_ema` | 情绪得分 |
| `regime` | 市场状态 (Bull/Neutral/Bear) |

### 2. `data/orders_today.csv`

订单文件，直接用于交易，包含：
```
code,name,target_weight,order_type,timestamp
000001,平安银行,0.0526,buy,2024-10-31 15:20:00
000858,五粮液,0.0526,buy,2024-10-31 15:20:00
...
```

**使用方法：**
- 复制到交易软件或API调用
- 按 `target_weight` 分配资金
- `order_type` 都是 `buy`（买入）

---

## 🔄 每日运行节奏

### 交易日收盘后

**15:10** - 运行第一个脚本
```bash
python scripts/run_breadth.py
```

**15:20** - 运行第二个脚本（依赖第一个的结果）
```bash
python scripts/run_daily.py
```

### 自动化调度（可选）

**Linux/macOS crontab:**

```bash
crontab -e
```

添加以下两行：

```
10 15 * * 1-5 cd /path/to/a-share-agent && source .venv/bin/activate && python scripts/run_breadth.py
20 15 * * 1-5 cd /path/to/a-share-agent && source .venv/bin/activate && python scripts/run_daily.py
```

**Windows 任务计划程序:**

1. 打开"任务计划程序"
2. 创建基本任务
3. 触发条件：每个工作日 15:10 和 15:20
4. 操作：运行脚本
   ```
   C:\path\to\a-share-agent\.venv\Scripts\python.exe C:\path\to\a-share-agent\scripts\run_breadth.py
   ```

---

## 🧪 测试与验证

### 快速测试（无需真实交易）

```python
# 创建 test_demo.py
from src.dataio import get_universe
from src.signals import make_signals
from datetime import datetime, timedelta

# 获取前10个标的测试
uni = get_universe(top_n=10)
codes = uni["代码"].tolist()

# 生成去年数据的信号
end = datetime.today().strftime("%Y%m%d")
start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")

closes, entries, exits, score = make_signals(codes, start, end)

print(f"✓ 成功生成 {closes.shape} 的面板数据")
print(f"✓ 入场信号数: {entries.sum().sum()}")
```

运行：
```bash
python test_demo.py
```

---

## ⚠️ 常见错误排查

### ❌ "ModuleNotFoundError: No module named 'akshare'"

**解决：**
```bash
pip install akshare -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### ❌ "ConnectionError: Failed to get data"

**原因：** 网络连接或 akshare 服务中断

**解决：**
- 检查网络连接
- 稍后重试（akshare 服务可能有延迟）
- 尝试使用VPN

### ❌ "FileNotFoundError: data/market/breadth.parquet"

**原因：** 未运行 `run_breadth.py`

**解决：**
```bash
python scripts/run_breadth.py
```

### ❌ "ValueError: Could not read data..."

**原因：** 数据不存在或股票停牌/退市

**解决：**
- 减少 `top_n` 参数（改为80）
- 手动检查 akshare 数据源
- 查看是否有新股或退市导致宇宙变化

---

## 📊 查看运行结果

### 查看最后生成的订单

```python
import pandas as pd

# 读取订单
orders = pd.read_csv("data/orders_today.csv", encoding="utf-8-sig")
print(orders.to_string())

# 统计
print(f"\n订单数: {len(orders)}")
print(f"总权重: {orders['target_weight'].sum():.2%}")
print(f"平均权重: {orders['target_weight'].mean():.2%}")
```

### 查看市场状态

```python
import pandas as pd

# 读取宽度数据
breadth = pd.read_parquet("data/market/breadth.parquet")

# 最近3个交易日
print(breadth[["up_count", "down_count", "breadth_score_ema", "regime"]].tail(3))
```

---

## 🎯 下一步

### 1. 参数调优

编辑 `scripts/run_daily.py`，修改：
- `top_n`：宇宙规模（80-150）
- `fees`：手续费假设（0.0001-0.0005）

然后重新运行，观察 `data/orders_today.csv` 的数量与质量。

### 2. 回测验证

```bash
python scripts/backtest_analysis.py
```

查看历史3年的绩效指标（年化、夏普、回撤）。

### 3. 实盘模拟

用真实或模拟账户，按订单权重交易，观察1-2周表现。

### 4. 深度学习阅读

详见 `README.md` 的"进阶扩展"章节，了解如何：
- 接入 Qlib ML 框架
- 添加文本情绪因子
- 自定义止损逻辑

---

## 📱 技术栈速查

| 组件 | 用途 | 学习资源 |
|---|---|---|
| **akshare** | A股数据 | [官方文档](https://akshare.akfamily.xyz/) |
| **pandas** | 数据处理 | [官方教程](https://pandas.pydata.org/docs/) |
| **vectorbt** | 回测引擎 | [官方文档](https://vectorbt.dev/) |
| **Python 3.10** | 编程语言 | [官方文档](https://www.python.org/doc/) |

---

## 🤔 常见问题

**Q: 为什么我的订单经常为空？**
A: 市场熊市 (regime=Bear) 时会拒绝所有订单。检查 `breadth_score_ema < -0.5` 的日期。

**Q: 能否修改策略参数？**
A: 可以！编辑 `src/signals.py` 的均线周期、动量阈值等，或 `src/risk.py` 的过滤条件。

**Q: 如何接入真实交易API？**
A: 用 `data/orders_today.csv` 的代码和权重调用券商API（如东方财富、同花顺等）。

**Q: 支持A股以外的市场吗？**
A: 目前针对A股优化。要扩展至港股/美股，需修改 `dataio.py` 的数据源。

---

## 💡 贴士

1. **第一次数据拉取会很慢**，但后续利用Parquet缓存，速度快100倍
2. **避免交易日 15:00-15:10** 拉取数据，此时akshare压力大
3. **建议用小资金试跑**，从1000元开始，验证策略可靠性
4. **定期更新宽度数据**，每周至少运行一次 `run_breadth.py`
5. **监控 夏普比率 > 0.8、最大回撤 < 20%**，这是稳定策略的标志

---

## 📞 获取帮助

- 📖 详见 `README.md` 完整文档
- 🐛 问题排查：检查错误日志和输出信息
- 💬 社区讨论：A股量化交易相关论坛

---

**祝你交易愉快！** 🚀📈
