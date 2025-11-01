# 📅 A股交易系统 - 日常使用流程

## ⚡ 快速开始（交易日收盘后）

```bash
# 进入项目目录
cd /home/deeproute/zj/cg/a-share-agent

# 第1步：更新最新市场数据（15:10 运行）
python3 scripts/update_breadth_today.py

# 第2步：启动 AI Agent（15:20 运行）
export DEEPSEEK_API_KEY="sk-0252c421598b44a9be3cbe68425dfa0d"
python3 scripts/run_agent.py

# 第3步：输入自然语言问题
🧑 你: 现在市场怎么样？
🤖 Agent: [自动返回分析结果]
```

---

## 📊 支持的所有问题

### 📈 市场分析
```
输入: 现在市场怎么样？ / 市场情况如何？ / 市场态势
返回: 
  • 市场态势 (Bull/Neutral/Bear)
  • 宽度得分
  • 上涨/下跌家数
  • 推荐仓位
```

### 💰 股票推荐
```
输入: 今天有什么股票？ / 推荐什么标的？ / 有什么买入信号？
返回:
  • 前 5 个推荐标的
  • 排名和打分
  • 权重配置
  • 总投资比例
```

### ⚙️ 系统参数
```
输入: 系统参数是什么？ / 参数配置 / 规则是什么？
返回:
  • 动量阈值
  • 波动阈值
  • Top-K 个数
  • 调整方法
```

### 📉 历史表现
```
输入: 历史表现怎么样？ / 回测数据 / 表现统计
返回:
  • 年化收益
  • 夏普比率
  • 最大回撤
  • 胜率
```

### 🔄 系统更新
```
输入: 更新系统数据 / 重新计算 / 刷新数据
返回:
  • 更新进度
  • 更新完成确认
```

### 📖 帮助
```
输入: help / 帮助 / ?
返回: 使用说明和示例
```

---

## 🔑 关键命令

### 快速更新数据
```bash
python3 scripts/update_breadth_today.py
```
结果:
- 加载 analyse_marketing 的最新缓存（4666 个股票）
- 计算市场宽度指标
- 更新 breadth_am_integrated.parquet
- 显示最新市场数据

### 启动 AI Agent
```bash
export DEEPSEEK_API_KEY="sk-0252c421598b44a9be3cbe68425dfa0d"
export TRADING_MODEL="deepseek"
python3 scripts/run_agent.py
```
结果:
- ✅ 已加载模型: deepseek
- ✅ LLM Agent 已加载 (使用 DeepSeek API)
- 等待用户输入

### 查看最新订单
```bash
cat data/orders_am_integrated.csv
```

---

## 📊 数据流程

```
11月1日 收盘后
    ↓
15:10 - 运行更新脚本
├─ python3 scripts/update_breadth_today.py
├─ 刷新 analyse_marketing 缓存数据
├─ 重新计算市场宽度
└─ 更新 breadth_am_integrated.parquet
    ↓
15:20 - 启动 AI Agent
├─ python3 scripts/run_agent.py
├─ DeepSeek LLM 已加载
└─ 等待用户问题
    ↓
16:00 - 用户交互
├─ 自然语言输入问题
├─ AI 自动调用工具
├─ 返回中文分析结果
└─ [继续交互或退出]
```

---

## ✅ 如何验证系统正常工作

### 检查 1：数据已更新
```bash
python3 << 'PYEOF'
import pandas as pd
df = pd.read_parquet("data/market/breadth_am_integrated.parquet")
print(f"最新数据: {df.index[-1]}")
print(f"上涨家数: {int(df.iloc[-1]['up_count'])}")
print(f"下跌家数: {int(df.iloc[-1]['down_count'])}")
PYEOF
```

### 检查 2：AI Agent 工作正常
启动后输入: `现在市场怎么样？`

看到这样的输出说明正常:
```
[LLM] DeepSeek 返回: 我来为您查询...
[LLM] 触发工具: query_market_breadth
✨ Agent: 📊 市场宽度分析...
```

### 检查 3：最新交易信号
```bash
cat data/orders_am_integrated.csv
```

---

## 🚨 常见问题排查

### Q: 显示 "❌ 错误: 文件不存在"
**A:** 需要先运行数据更新脚本
```bash
python3 scripts/update_breadth_today.py
```

### Q: AI 没有返回结果
**A:** 确保设置了 API Key
```bash
export DEEPSEEK_API_KEY="sk-0252c421598b44a9be3cbe68425dfa0d"
```

### Q: 数据显示的是旧日期
**A:** 需要刷新缓存数据
```bash
python3 scripts/update_breadth_today.py
```

### Q: 推荐的股票太少或太多
**A:** 修改参数后重新运行
```bash
# 编辑 src/signals.py
# 修改 Top-K 个数、阈值等
python3 scripts/run_agent.py
```

---

## 📅 推荐的自动化方案

### Linux/Mac - crontab 自动化

编辑 crontab:
```bash
crontab -e
```

添加以下行:
```bash
# 每个交易日 15:10 更新数据
10 15 * * 1-5 cd /home/deeproute/zj/cg/a-share-agent && python3 scripts/update_breadth_today.py >> logs/update.log 2>&1

# 每个交易日 15:20 启动 AI Agent
20 15 * * 1-5 cd /home/deeproute/zj/cg/a-share-agent && export DEEPSEEK_API_KEY=sk-0252c421598b44a9be3cbe68425dfa0d && python3 scripts/run_agent.py >> logs/agent.log 2>&1
```

### Windows - 任务计划程序

1. 创建 `update_daily.bat`:
```batch
cd /home/deeproute/zj/cg/a-share-agent
python3 scripts/update_breadth_today.py
```

2. 创建 `start_agent.bat`:
```batch
cd /home/deeproute/zj/cg/a-share-agent
set DEEPSEEK_API_KEY=sk-0252c421598b44a9be3cbe68425dfa0d
python3 scripts/run_agent.py
```

3. 在任务计划程序中:
   - 15:10 运行 update_daily.bat
   - 15:20 运行 start_agent.bat

---

## 📈 系统状态检查

```bash
# 检查 DeepSeek API 连接
python3 -c "
from openai import OpenAI
client = OpenAI(api_key='sk-0252c421598b44a9be3cbe68425dfa0d', base_url='https://api.deepseek.com')
response = client.chat.completions.create(model='deepseek-chat', messages=[{'role': 'user', 'content': '你好'}])
print('✅ DeepSeek API 连接正常')
"

# 检查数据完整性
python3 scripts/update_breadth_today.py

# 检查最新订单
wc -l data/orders_am_integrated.csv
```

---

## 🎯 一日三餐式交易流程

### 早上 9:30 (开盘前)
```bash
# 回顾昨日数据
cat data/orders_am_integrated.csv
python3 scripts/run_agent.py  # 查询系统参数
```

### 中午 11:30
```bash
# 中途检查市场
python3 scripts/run_agent.py  # 询问"现在市场怎么样？"
```

### 收盘后 15:30
```bash
# 生成新订单
python3 scripts/update_breadth_today.py
python3 scripts/run_agent.py
# 输入: 今天有什么股票？
# 执行交易
```

---

## 💡 最佳实践

✅ **每日必做**
- 收盘后立即运行更新脚本
- 检查最新的交易信号
- 记录系统推荐和实际交易结果

✅ **每周必做**
- 查看历史表现统计
- 对比实际收益 vs 回测数据
- 调整参数（如需要）

✅ **每月必做**
- 完整的数据重新计算
- 参数优化和调优
- 系统文档更新

❌ **避免**
- 手工修改 .parquet 文件
- 跳过数据更新步骤
- 使用过期的缓存数据
- 同时运行多个 Agent 实例

---

## 📞 需要帮助？

```bash
# 查看帮助信息
python3 scripts/run_agent.py
# 输入: help

# 查看日志
tail -100 logs/agent.log

# 检查最新错误
grep ERROR logs/update.log
```

---

**祝交易顺利！📈✨**

