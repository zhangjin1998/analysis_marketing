# 部署与验证清单

## ✅ 项目完成度检查

### 📊 代码统计
- **总代码行数：** 1036 行 Python
- **模块数量：** 7 个核心模块 + 3 个运行脚本
- **文档数量：** 4 个 markdown 文档

### 📁 项目结构
```
✅ src/                    (7个模块)
   ├── dataio.py         (119行) - 数据获取与缓存
   ├── breadth.py        (138行) - 市场宽度与情绪
   ├── signals.py        (73行)  - 选股信号生成
   ├── risk.py           (110行) - 风险管理与仓位
   ├── backtest.py       (143行) - 组合回测引擎
   ├── orders.py         (133行) - 订单导出
   └── __init__.py       (5行)   - 包初始化

✅ scripts/               (3个脚本)
   ├── run_breadth.py    (39行)  - 市场宽度构建
   ├── run_daily.py      (116行) - 日度选股订单
   └── backtest_analysis.py (160行) - 回测分析

✅ 配置与文档
   ├── requirements.txt           - 依赖列表
   ├── config_example.py          - 参数配置模板
   ├── .gitignore                 - Git规则
   ├── README.md                  - 完整文档
   ├── QUICKSTART.md              - 快速指南
   ├── PROJECT_SUMMARY.md         - 项目总结
   └── DEPLOYMENT.md              - 本文件
```

---

## 🚀 快速部署（5分钟）

### 1️⃣ 环境准备
```bash
# 进入项目目录
cd /path/to/a-share-agent

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows
```

### 2️⃣ 安装依赖
```bash
# 推荐：使用清华镜像（快10倍）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 备选：默认源
pip install -r requirements.txt
```

**依赖验证：**
```bash
python -c "import akshare, pandas, numpy, sklearn; print('✓ 依赖安装成功')"
```

### 3️⃣ 首次初始化（必须）
```bash
# 构建2年市场宽度数据（耗时10-30分钟）
python scripts/run_breadth.py

# 期望输出：
# ✓ 宽度数据已成功保存到 data/market/breadth.parquet
```

### 4️⃣ 验证运行
```bash
# 生成今日信号与订单
python scripts/run_daily.py

# 期望输出：
# ✓ 订单已导出: data/orders_today.csv
```

**成功标志：**
- ✅ `data/market/breadth.parquet` 已生成
- ✅ `data/orders_today.csv` 已生成
- ✅ 无错误输出

---

## 📋 功能验证清单

### ✅ 数据获取模块 (dataio.py)
- [ ] `get_universe()` - 能获取A股宇宙
- [ ] `fetch_hist_qfq()` - 能获取单只股票数据
- [ ] `fetch_panel()` - 能获取多只股票面板
- [ ] `save/load_parquet()` - 能正确缓存数据

**快速验证：**
```python
from src.dataio import get_universe
uni = get_universe(top_n=10)
print(f"✓ 获取{len(uni)}只股票")
```

### ✅ 市场宽度模块 (breadth.py)
- [ ] `compute_breadth()` - 能计算市场指标
- [ ] `build_breadth()` - 能构建2年数据
- [ ] 输出包含 regime 列
- [ ] regime 值为 Bull/Neutral/Bear

**快速验证：**
```python
from src.breadth import build_breadth
df = build_breadth(top_n=10, lookback_days=365)
print(f"✓ 宽度数据: {df.shape}, regime={df['regime'].iloc[-1]}")
```

### ✅ 选股信号模块 (signals.py)
- [ ] `make_signals()` - 能生成入场/出场信号
- [ ] entries 为 bool DataFrame
- [ ] exits 为 bool DataFrame
- [ ] score 为 float DataFrame (范围 [-1, 1])

**快速验证：**
```python
from src.signals import make_signals
from datetime import datetime, timedelta

codes = ['000001', '000858']
end = datetime.today().strftime("%Y%m%d")
start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")

closes, entries, exits, score = make_signals(codes, start, end)
print(f"✓ 信号生成: entries={entries.shape}, True数={entries.sum().sum()}")
```

### ✅ 风控模块 (risk.py)
- [ ] `apply_regime_filter()` - 能过滤熊市信号
- [ ] `position_scale()` - 能计算仓位缩放 [20%, 100%]
- [ ] 返回值类型正确

**快速验证：**
```python
from src.risk import position_scale
import pandas as pd

breadth = pd.read_parquet("data/market/breadth.parquet")
scale = position_scale(breadth)
print(f"✓ 仓位缩放: 最小={scale.min():.2%}, 最大={scale.max():.2%}")
```

### ✅ 回测模块 (backtest.py)
- [ ] `simple_backtest()` - 能执行无依赖回测
- [ ] 返回 DataFrame 包含 value/return 列
- [ ] 支持费率和滑点参数

**快速验证：**
```python
from src.backtest import simple_backtest
import pandas as pd
import numpy as np

# 生成随机测试数据
dates = pd.date_range('2024-01-01', periods=100, freq='D')
closes = pd.DataFrame(
    np.random.randn(100, 5).cumsum(0) + 100,
    index=dates, columns=['s1', 's2', 's3', 's4', 's5']
)
entries = pd.DataFrame(np.random.rand(100, 5) > 0.8, index=dates, columns=closes.columns)
exits = pd.DataFrame(np.random.rand(100, 5) > 0.9, index=dates, columns=closes.columns)

result = simple_backtest(closes, entries, exits)
print(f"✓ 回测完成: shape={result.shape}, 年化={result['cumret'].iloc[-1]:.2%}")
```

### ✅ 订单模块 (orders.py)
- [ ] `export_orders_today()` - 能导出CSV订单
- [ ] CSV 编码为 utf-8-sig
- [ ] 包含所需列：code, name, target_weight, order_type, timestamp

**快速验证：**
```python
from src.orders import export_orders_today, summary_orders
import pandas as pd

# 假设已有entries和score
path = export_orders_today(entries, score, top_n=5, out_path="data/test_orders.csv")
if path:
    info = summary_orders(path)
    print(f"✓ 订单导出: {info['count']}个标的, 总权重={info['total_weight']:.2%}")
```

---

## 🔧 自动化部署

### Linux Crontab 部署

```bash
# 编辑 crontab
crontab -e

# 添加以下两行
10 15 * * 1-5 cd /home/user/a-share-agent && source .venv/bin/activate && python scripts/run_breadth.py >> logs/breadth.log 2>&1
20 15 * * 1-5 cd /home/user/a-share-agent && source .venv/bin/activate && python scripts/run_daily.py >> logs/daily.log 2>&1

# 验证
crontab -l
```

### Windows 任务计划程序部署

1. 打开"任务计划程序"
2. 点击"创建基本任务"
3. **常规标签：**
   - 名称：`A-Share-Agent Breadth`
   - 描述：每日15:10运行宽度计算

4. **触发条件标签：**
   - 类型：每日
   - 时间：15:10
   - 重复间隔：工作日（周一-周五）

5. **操作标签：**
   - 程序或脚本：`C:\path\to\.venv\Scripts\python.exe`
   - 参数：`scripts/run_breadth.py`
   - 起始于：`C:\path\to\a-share-agent`

6. 重复上述步骤，创建15:20的 `run_daily.py` 任务

---

## 🐛 常见问题排查

### Q: 运行脚本时报 "ModuleNotFoundError: No module named 'akshare'"

**检查清单：**
1. [ ] 虚拟环境已激活：`which python` 显示 `.venv/bin/python`
2. [ ] 依赖已安装：`pip list | grep akshare`
3. [ ] 重新安装：`pip install akshare`

### Q: "ConnectionError: Failed to connect to akshare"

**检查清单：**
1. [ ] 网络连接正常
2. [ ] 尝试 ping akshare 服务：`python -c "import akshare as ak; print(ak.__version__)"`
3. [ ] 避开高峰期（15:00-16:00）
4. [ ] 使用 VPN 或代理

### Q: 脚本运行速度很慢

**优化方案：**
1. [ ] 减少 `top_n` (从100改为50)
2. [ ] 减少 `lookback_days` (从365*2改为365)
3. [ ] 检查网络连接
4. [ ] 清理缓存：`rm -rf data/*.parquet`

### Q: 导出的订单为空

**排查步骤：**
1. [ ] 检查市场状态：`python -c "import pandas as pd; df = pd.read_parquet('data/market/breadth.parquet'); print(df['regime'].tail())"`
2. [ ] 如果全是 Bear，等待市场回暖
3. [ ] 检查参数：`scripts/run_daily.py` 中的 `top_n` 和阈值
4. [ ] 重新运行 `run_breadth.py`

---

## 📊 性能基准测试

### 预期执行时间

| 步骤 | 首次运行 | 后续运行 | 说明 |
|---|---|---|---|
| run_breadth.py | 10-30分钟 | 3-5分钟 | 取决于网络与top_n |
| run_daily.py | 3-5分钟 | 1-2分钟 | 后续使用缓存数据 |
| backtest_analysis.py | 5-15分钟 | 5-15分钟 | 历史数据量大 |

### 内存使用预估

| 操作 | 内存占用 | 说明 |
|---|---|---|
| 加载 breadth.parquet | ~50MB | 2年×120个股票 |
| 面板数据 (100个股票×3年) | ~200MB | 日线数据 |
| 回测运行 | ~300MB | 包含所有中间结果 |

### 磁盘使用预估

| 文件 | 大小 | 说明 |
|---|---|---|
| data/market/breadth.parquet | ~200KB | 压缩Parquet |
| data/orders_today.csv | ~5KB | 日度订单 |
| 完整项目 | ~50MB | 包括虚拟环境 |

---

## 🔐 安全与最佳实践

### ✅ 数据安全

- [ ] 订单文件不包含真实密钥或API凭证
- [ ] 所有数据本地存储，不上传云端
- [ ] 建议启用文件系统加密（Windows EFS / Linux LUKS）

### ✅ 交易安全

- [ ] ⚠️ **重要：** 不要用真实交易账户直接自动执行订单
- [ ] 建议：先用模拟账户验证1-2周
- [ ] 建议：在交易前手动审查 `data/orders_today.csv`
- [ ] 建议：设置单笔交易上限和每日止损

### ✅ 代码版本管理

```bash
# 初始化 Git 仓库（可选）
git init
git add .
git commit -m "Initial commit: A-Share-Agent v0.1.0"

# 创建本地备份
cp -r a-share-agent a-share-agent.bak
```

---

## 📚 文档导航

| 文档 | 用途 | 推荐阅读 |
|---|---|---|
| **README.md** | 完整功能说明 | 深入学习 |
| **QUICKSTART.md** | 5分钟快速上手 | 新用户必读 |
| **PROJECT_SUMMARY.md** | 架构与算法原理 | 开发维护 |
| **config_example.py** | 参数配置模板 | 参数优化 |
| **DEPLOYMENT.md** | 部署与验证 | 生产环境 |

---

## ✨ 验证清单（最终）

### 部署前检查
- [ ] Python 版本 ≥ 3.9
- [ ] 虚拟环境已创建
- [ ] 依赖已完整安装
- [ ] 网络连接正常

### 功能验证
- [ ] dataio 模块能获取数据
- [ ] breadth 模块能生成宽度指标
- [ ] signals 模块能生成选股信号
- [ ] risk 模块能计算风控指标
- [ ] orders 模块能导出订单文件

### 自动化部署
- [ ] Crontab 或任务计划程序已配置
- [ ] 日志目录已创建
- [ ] 文件权限已设置

### 风险管理
- [ ] 已阅读免责声明
- [ ] 已用小资金验证
- [ ] 已设置止损与上限

---

## 🎉 部署完成

**恭喜！您的A股短线交易系统已部署完成。**

### 接下来的步骤：
1. ✅ 每日 15:10 自动运行 `run_breadth.py`
2. ✅ 每日 15:20 自动运行 `run_daily.py`
3. ✅ 审查 `data/orders_today.csv` 中的订单
4. ✅ 按照建议权重执行交易
5. ✅ 周末复盘上周表现

### 监控指标：
- 📊 **年化收益** > 10%
- 📊 **夏普比率** > 0.8
- 📊 **最大回撤** < 20%
- 📊 **胜率** > 45%

---

**祝交易顺利！** 🚀📈

*版本：v0.1.0 | 更新：2024-10*
