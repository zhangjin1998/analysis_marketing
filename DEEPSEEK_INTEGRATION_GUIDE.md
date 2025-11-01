# 🇨🇳 国内大模型集成指南 - DeepSeek/通义千问等

## 快速开始 (5分钟)

### 推荐方案：使用 DeepSeek (最便宜，质量最好)

#### 第 1 步: 获取 DeepSeek API Key (2分钟)

```bash
# 1. 访问 DeepSeek 官网
https://platform.deepseek.com

# 2. 用微信/支付宝注册 (无需信用卡)

# 3. 创建 API Key
   Dashboard → API Keys → 创建新密钥

# 4. 免费额度: ¥500 (足够用 3-6 个月!)
```

#### 第 2 步: 修改配置 (2分钟)

编辑 `.env` 文件:

```bash
# 原来的 (删除或注释)
# OPENAI_API_KEY=sk-xxx...

# 改成这个 (新增)
DEEPSEEK_API_KEY=sk-xxx...    # 从 DeepSeek 获得
TRADING_MODEL=deepseek         # 使用 DeepSeek
```

#### 第 3 步: 修改代码 (1分钟)

编辑 `agents/trading_agent.py` 第 215 行:

```python
# 从这个:
llm = OpenAI(
    temperature=0.3,
    max_tokens=2000,
    model="gpt-3.5-turbo"
)

# 改成这个:
from agents.model_config import get_llm
model_name = os.getenv("TRADING_MODEL", "deepseek")
llm = get_llm(model_name)
```

#### 第 4 步: 启动 (立刻)

```bash
python3 scripts/run_agent.py

# 输入: 现在市场怎么样?
# 它就会用 DeepSeek 回复了！✨
```

---

## 高级方案：多模型切换 (灵活配置)

### 方案 2: 支持在多个模型间切换

#### 安装依赖

```bash
pip install tabulate  # 用于显示模型列表
```

#### 查看所有可用模型

```bash
python3 agents/model_config.py
```

输出:
```
🤖 可用的 AI 模型
┌──────────┬──────────┬──────────────────┬──────┬──────────────┬──────────────────┐
│ 模型     │ 提供商   │ 成本             │ 速度 │ 质量         │ 备注             │
├──────────┼──────────┼──────────────────┼──────┼──────────────┼──────────────────┤
│ deepseek │ openai   │ $0 (¥500免费)   │ 快   │ ⭐⭐⭐⭐⭐ │ 推荐首选...      │
│ openai   │ openai   │ $5-20/月         │ 中   │ ⭐⭐⭐⭐⭐ │ 国际标准...      │
│ qwen     │ openai   │ $0 (免费额度)   │ 很快 │ ⭐⭐⭐⭐   │ 国内免费...      │
│ spark    │ openai   │ $$ 低            │ 快   │ ⭐⭐⭐⭐   │ 成本低...        │
│ baidu    │ baidu    │ $ 低             │ 快   │ ⭐⭐⭐⭐   │ 功能完整...      │
│ claude   │ anthropic│ $$$ 中           │ 中   │ ⭐⭐⭐⭐⭐ │ 推理能力...      │
└──────────┴──────────┴──────────────────┴──────┴──────────────┴──────────────────┘

📋 模型 API Key 配置状态检查
══════════════════════════════════════════════════════════════
✅ deepseek      (openai    ) -> DEEPSEEK_API_KEY
❌ openai        (openai    ) -> OPENAI_API_KEY
❌ qwen          (openai    ) -> QWEN_API_KEY
❌ spark         (openai    ) -> SPARK_API_KEY
❌ baidu         (baidu     ) -> BAIDU_API_KEY
❌ claude        (anthropic ) -> ANTHROPIC_API_KEY
══════════════════════════════════════════════════════════════

📊 默认模型:  deepseek
```

#### 在不同模型间切换

```bash
# 使用 DeepSeek (默认)
python3 scripts/run_agent.py

# 使用 OpenAI
TRADING_MODEL=openai python3 scripts/run_agent.py

# 使用阿里通义千问
TRADING_MODEL=qwen python3 scripts/run_agent.py

# 使用 Claude
TRADING_MODEL=claude python3 scripts/run_agent.py
```

#### 配置所有 API Key

编辑 `.env`:

```env
# 默认使用的模型
TRADING_MODEL=deepseek

# ========== DeepSeek (推荐 ★★★★★) ==========
DEEPSEEK_API_KEY=sk-xxx...    # https://platform.deepseek.com

# ========== OpenAI (国际标准) ==========
OPENAI_API_KEY=sk-xxx...      # https://platform.openai.com/api-keys

# ========== 阿里通义千问 (免费) ==========
QWEN_API_KEY=xxx...           # https://dashscope.aliyun.com

# ========== 讯飞星火 (成本低) ==========
SPARK_API_KEY=xxx...          # https://console.xfyun.cn

# ========== 百度文心 (功能完整) ==========
BAIDU_API_KEY=xxx...          # https://console.bce.baidu.com

# ========== Anthropic Claude (推理最强) ==========
ANTHROPIC_API_KEY=sk-xxx...   # https://console.anthropic.com
```

---

## 各模型详细对比

### 🏆 DeepSeek (最推荐)

**为什么选择？**
- ✅ 质量: 超越 GPT-3.5，接近 GPT-4
- ✅ 成本: 超便宜 ($0.00001/1K tokens)
- ✅ 中文: 专为中文优化，理解深入
- ✅ 速度: 国内服务器，延迟低
- ✅ 免费: ¥500 免费额度

**获取 API Key:**
1. 访问: https://platform.deepseek.com
2. 微信/支付宝注册
3. 创建 API Key
4. 复制 Key，填入 .env

**成本估算:**
```
¥500 免费额度
≈ 50 万次查询
≈ 3-6 个月使用时长
```

---

### 🚀 阿里通义千问 (次选)

**为什么选择？**
- ✅ 免费: 完全免费额度
- ✅ 中文: 中文理解优秀
- ✅ 快速: 响应很快
- ✅ 稳定: 大厂产品

**获取 API Key:**
1. 访问: https://dashscope.aliyun.com
2. 登录阿里云账号
3. 创建 API Key
4. 选择模型: qwen-plus

**配置:**
```bash
TRADING_MODEL=qwen
QWEN_API_KEY=sk-xxx...
```

---

### 💎 Claude (推理最强)

**为什么选择？**
- ✅ 推理: 逻辑推理能力最强
- ✅ 质量: 整体质量最高
- ✅ 安全: 安全性最好

**获取 API Key:**
1. 访问: https://console.anthropic.com
2. 信用卡注册 (国际)
3. 创建 API Key
4. 填入 .env

**配置:**
```bash
TRADING_MODEL=claude
ANTHROPIC_API_KEY=sk-xxx...
```

---

### 🌍 OpenAI (国际标准)

**为什么选择？**
- ✅ 标准: 业界标准
- ✅ 稳定: 最稳定
- ✅ 成熟: 生态最完整

**获取 API Key:**
1. 访问: https://platform.openai.com/api-keys
2. 信用卡注册
3. 创建 API Key
4. 填入 .env

**配置:**
```bash
TRADING_MODEL=openai
OPENAI_API_KEY=sk-xxx...
```

---

## 成本对比表

| 模型 | 免费额度 | 付费价格 | 推荐度 | 中文支持 |
|------|--------|--------|-------|--------|
| DeepSeek | ¥500 | $0.00001/1K | ⭐⭐⭐⭐⭐ | 优秀 ✅ |
| 通义千问 | 免费 | 免费 | ⭐⭐⭐⭐ | 优秀 ✅ |
| Claude | $5 | $0.003/1K | ⭐⭐⭐⭐ | 中等 |
| OpenAI | $5 | $0.0015/1K | ⭐⭐⭐⭐ | 中等 |
| 讯飞星火 | 免费 | $$ 低 | ⭐⭐⭐ | 优秀 ✅ |
| 百度文心 | 免费 | $ 低 | ⭐⭐⭐ | 优秀 ✅ |

---

## 故障排查

### 问题 1: API Key 无效

```
❌ ValueError: API key is invalid
```

**解决:**
1. 确认 Key 正确复制 (无多余空格)
2. 确认 Key 未过期
3. 确认 Key 有额度
4. 在官网测试一下

### 问题 2: 网络超时

```
❌ Connection timeout
```

**解决:**
```bash
# 国内用户，使用国内代理加速
DEEPSEEK_PROXY=https://api.deepseek.com
OPENAI_PROXY=https://api-proxy.com  # 可选代理
```

### 问题 3: 模型名称错误

```
❌ Model not found: xxx
```

**解决:**
```bash
# 查看可用模型
python3 agents/model_config.py

# 使用正确的模型名
TRADING_MODEL=deepseek  # 不要 deepseek-chat，直接 deepseek
```

---

## 推荐配置方案

### 方案 A: 成本最优

```env
TRADING_MODEL=deepseek
DEEPSEEK_API_KEY=sk-xxx...

# 成本: ¥0 (¥500免费额度)
# 质量: ⭐⭐⭐⭐⭐
# 中文: 优秀
```

### 方案 B: 完全免费

```env
TRADING_MODEL=qwen
QWEN_API_KEY=sk-xxx...

# 成本: ¥0 (完全免费)
# 质量: ⭐⭐⭐⭐
# 中文: 优秀
```

### 方案 C: 多模型备用

```env
TRADING_MODEL=deepseek

DEEPSEEK_API_KEY=sk-xxx...    # 主用
QWEN_API_KEY=sk-xxx...        # 备用 1
OPENAI_API_KEY=sk-xxx...      # 备用 2

# 实现故障自动切换
```

---

## 代码示例

### 简单切换

```python
# 使用 DeepSeek
from agents.model_config import get_llm
llm = get_llm("deepseek")

# 使用通义千问
llm = get_llm("qwen")

# 使用 Claude
llm = get_llm("claude")
```

### 动态切换 (推荐)

```python
import os
from agents.model_config import get_llm

# 从环境变量读取
model_name = os.getenv("TRADING_MODEL", "deepseek")
llm = get_llm(model_name)

# 现在可以通过环境变量灵活切换！
```

### 列出所有模型

```python
from agents.model_config import list_models, check_models

# 显示模型对比表
print(list_models())

# 检查 API Key 配置
check_models()
```

---

## FAQ

**Q: 哪个模型最便宜？**
A: DeepSeek! ¥500 免费额度，成本最低。

**Q: 哪个模型质量最好？**
A: Claude 和 GPT-4，但 DeepSeek 性价比最高。

**Q: 推荐用哪个？**
A: 首选 DeepSeek (最便宜，质量接近 GPT-4)
   备选 OpenAI (国际标准，稳定)
   备选 Claude (推理最强)

**Q: 能同时用多个吗？**
A: 可以！设置多个 API Key，环境变量切换。

**Q: 国外用户怎么办？**
A: 推荐 OpenAI 或 Claude，都支持国际。

**Q: 能离线用吗？**
A: 可以。用 Ollama + DeepSeek 开源模型本地运行。

---

## 更新历史

- 2025-11-01: 初始版本，支持 6 个模型

---

**祝交易顺利！** 🚀📈
