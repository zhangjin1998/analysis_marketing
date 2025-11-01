## 分析选股管线（quant-api-pipeline）使用说明

本项目提供从数据获取→技术指标→硬过滤→打分排序→盘前 Focus 模板导出的端到端管线，适合动量/趋势风格的日更选股流程。

### 一分钟上手（TL;DR）

- 安装依赖（Python 3.8+）
```bash
pip install -r requirements.txt
```
- 配置 TuShare Token（免费注册）
```bash
export TUSHARE_TOKEN='你的token'
```
- 检查/调整配置：编辑 `config.yaml`（指数篮子、阈值、输出规模等）
- 运行
```bash
# 首次全量（建议从 2019-01-01 起）
python3 main.py --start 20190101 --export ./out

# 若只想用当前缓存直接出结果（不访问网络）
python3 main.py --start 20190101 --export ./out --offline
```
- 查看输出
  - `out/base_pool.csv`（基础池，周更）
  - `out/daily_candidates.csv`（每日候选池，已打分）
  - `out/focus_template.csv`（盘前 Focus 模板）
  - `out/env_gate_indices.csv`（周线闸门汇总）
  - `out/run.log`（运行日志）

### 目录结构

```text
quant-api-pipeline/
├─ requirements.txt
├─ config.yaml
├─ main.py
├─ indicators.py
├─ pipeline.py
├─ utils.py
├─ README.md
└─ TUNING.md
```

### 配置说明（config.yaml 摘要）
- `style`: 交易风格标签（仅注释用途）
- `style_profile`: 新增风格开关，三选一
  - `balanced`：均衡（默认不改动阈值与权重）
  - `theme`：题材偏好（提升动量/近高位权重，放宽波动与流动性门槛）
  - `whitehorse`：白马/机构（提高流动性、收紧波动，偏执行稳定）
- 其余：
  - `index_basket`：指数篮子（用于闸门与 Universe）
  - `exclude_st`、`include_kcb`、`include_bj`、`min_days_listed`、`min_price`
  - `liquidity_rmb_min`、`near_high_lookback`、`near_high_max`、`rsi14_min`、`atrp_min/max`
  - `weights`：`rs60, near_high, liquidity, atrp`
  - `base_pool_max`、`daily_candidates_max`、`focus_max`
  - `cache_dir`、`sleep_per_call`、`sentiment_stage`

示例：
```yaml
style: theme-momentum
style_profile: theme   # balanced/theme/whitehorse
```

详细调参建议与账户规模推荐值见 `TUNING.md`。

### 运行模式
- 在线模式（默认）
  - 使用 TuShare 拉取日线；指数成分优先 TuShare，回退东财 HTTP；指数历史用于“环境闸门”，无权限则跳过。
- 离线模式（`--offline`）
  - 完全不访问网络，仅用 `cache/daily/*.parquet` 中已有缓存计算并导出结果；适合配额吃紧或快速复算。

### 缓存与增量
- 缓存位置：`cache/daily/{ts_code}.parquet`（文件名中的 `.` 会替换为 `_`）
- 首次全量会逐只拉取历史并写入缓存；后续运行对已有缓存做“增量更新”
- 运行中断后可随时再次执行，程序会基于缓存续跑

### 输出字段
- `base_pool.csv`: `ts_code,name,close,ma10,ma21,ma50,ma200,atr14,atrp,rsi14,hhvN,near_high,amount_ma20,ret20,ret60`
- `daily_candidates.csv`: 上述字段 + `RS20,RS60,Score`
- `focus_template.csv`: `ts_code,name,close,pivot_draft,atr14,amount_ma20,amount_threshold,near_pivot_atr,ma10,ma21,ma50,ma200,ema10,ema21,atrp,rsi14,near_high,RS20,RS60,Score`

### 常见问题（FAQ）
- 权限不足/超频
  - 提示“没有接口访问权限”：指数/指数成分在免费档可能受限，程序已容错跳过；可升级账号或改用 `--offline`。
  - 提示“每分钟最多访问 X 次”：已内置 `sleep_per_call` 与超频重试，必要时调大 `sleep_per_call`。
- 指数成分
  - 优先用 TuShare `index_weight`；无权限回退东财 HTTP。若东财也不可用，则保留全市场基础清单。
- 样本过少
  - 放宽 `near_high_max`（如 0.08）、临时移除 `rsi14_min`，或扩大 Universe（指数篮子更宽）。

### 监控与恢复
```bash
# 实时日志
tail -f ./out/run.log
# 缓存进度（已缓存股票数）
find ./cache/daily -type f | wc -l
# 快速预览结果
head -n 5 ./out/daily_candidates.csv
```

### 小贴士
- 日更时 `--start` 保持最近一年（如 `20240101`）即可
- 若只需要快速看结果，可先 `--offline` 出一版，再让在线任务在后台继续补齐缓存
