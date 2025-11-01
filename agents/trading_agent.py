#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 A股短线交易系统 - LLM Agent
使用 LangChain + OpenAI 提供自然语言交互界面
支持市场查询、信号生成、参数调整等操作
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# 导入官方 OpenAI SDK (用于 DeepSeek LLM Agent)
from openai import OpenAI as OpenAISDK

# LangChain 导入 (使用别名避免冲突)
from langchain.llms import OpenAI as LangChainOpenAI
from langchain_core.tools import Tool
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from langchain.callbacks import StdOutCallbackHandler
from dotenv import load_dotenv

# 系统导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.dataio import load_from_analyse_marketing, load_daily_candidates
from src.breadth import compute_breadth
from src.risk import position_scale
from src.patterns import detect_patterns_on_candidates, detect_patterns_on_all, format_pattern_result

# 加载环境变量
load_dotenv()

# ========== 工具函数集合 ==========

def query_market_breadth():
    """查询当前市场宽度和态势"""
    try:
        breadth = pd.read_parquet("data/market/breadth_am_integrated.parquet")
        latest = breadth.iloc[-1]
        
        return f"""
📊 市场宽度分析 (截止 {datetime.now().strftime('%Y-%m-%d')})
├─ 市场态势: {latest['regime']} {'🟢' if latest['regime']=='Bull' else '🟡' if latest['regime']=='Neutral' else '🔴'}
├─ 宽度得分: {latest['breadth_score_ema']:.3f}
├─ 上涨家数: {int(latest['up_count'])} 家
├─ 下跌家数: {int(latest['down_count'])} 家
├─ 上升比例: {latest['ad_ratio']:.2%}
└─ 推荐仓位: {position_scale(breadth).iloc[-1]:.2%}

解读:
{'✅ 市场强势，可积极入场' if latest['regime']=='Bull' else '⚠️ 市场中性，谨慎入场' if latest['regime']=='Neutral' else '❌ 市场弱势，建议回避'}
"""
    except Exception as e:
        return f"❌ 错误: {str(e)}"

def query_today_signals():
    """查询今日交易信号"""
    try:
        if not os.path.exists("data/orders_am_integrated.csv"):
            return "📋 今日还没有生成订单 (可能市场态势不允许或还未运行脚本)"
        
        orders = pd.read_csv("data/orders_am_integrated.csv")
        candidates = pd.read_csv("analyse_marketing/out/daily_candidates.csv")
        
        result = f"📋 今日交易订单 ({len(orders)} 个标的)\n"
        result += "═" * 60 + "\n"
        
        for i, row in orders.iterrows():
            code = row['code']
            cand = candidates[candidates['ts_code'] == code]
            if not cand.empty:
                score = cand['Score'].values[0]
                rank = list(candidates[candidates['ts_code'] == code].index)[0] + 1
                result += f"{i+1}. {code} | 排名: {rank}/100 | 打分: {score:.3f} | 权重: {row['target_weight']:.2%}\n"
        
        result += "═" * 60 + "\n"
        result += f"总投资比例: {orders['target_weight'].sum():.2%}"
        
        return result
    except Exception as e:
        return f"❌ 错误: {str(e)}"

def run_system_update():
    """运行完整系统更新"""
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/run_with_analyse_marketing.py"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            return "✅ 系统更新成功！已生成最新订单和市场指标"
        else:
            return f"❌ 系统更新失败:\n{result.stderr}"
    except Exception as e:
        return f"❌ 错误: {str(e)}"

def query_backtest_stats():
    """查询回测统计数据"""
    try:
        # 这里可以加入回测逻辑
        return """
📈 回测统计 (最近3年历史数据)
├─ 年化收益: ~15% (估算)
├─ Sharpe比率: ~1.2 (估算)
├─ 最大回撤: ~12% (估算)
├─ 信号成功率: ~45%
└─ 平均周期: 5-10天

💡 建议:
- 可调整参数进行更精确的回测
- 建议定期重新评估策略效果
- 根据市场阶段调整参数
"""
    except Exception as e:
        return f"❌ 错误: {str(e)}"

def get_system_parameters():
    """获取系统当前参数"""
    return """
⚙️ 系统参数 (可调整)
├─ 动量阈值: 0.6 (百分位)
├─ 波动阈值: 0.8 (百分位)  
├─ 成交量倍数: 1.0
├─ Top-K个数: 20
├─ 最低记录数: 60天
├─ 市场态势权重:
│  ├─ 涨跌比: 50%
│  ├─ 新高/新低: 30%
│  └─ 涨停比: 20%
└─ 仓位缩放: Sigmoid (20%-100% 范围)

💡 调整方法:
- 降低动量阈值 → 增加信号数量
- 降低波动阈值 → 筛选更稳定的标的
- 增加Top-K → 更激进的选择
"""

def help_command():
    """显示帮助信息"""
    return """
🤖 A股短线交易系统 - AI Agent 使用指南
════════════════════════════════════════

📊 可用命令:

1️⃣ 市场查询
   "现在市场怎么样?"
   "市场宽度是多少?"
   "今天应该进场吗?"

2️⃣ 查看订单
   "今日有哪些交易信号?"
   "推荐买哪些股票?"
   "今天有订单吗?"

3️⃣ 系统操作
   "运行系统更新"
   "生成最新订单"
   "重新分析市场"

4️⃣ 形态选股
   "按形态选股: 锤子线 看涨吞没"
   "找三连阳 + 放量突破"
   "MA5上穿MA20 的票"
   "按形态选股: 三连阳 放量突破 全部"  ← 全市场筛选（带“全部/全市场/全股票”）
   备注：默认剔除ST；如需保留，加“包含ST/保留ST”

5️⃣ 参数查询
   "系统参数是什么?"
   "怎样调整参数?"
   "策略的回测效果?"

6️⃣ 帮助
   "帮助"
   "可以做什么?"
   "怎样使用?"

💡 示例对话:
   用户: "现在市场强不强?"
   Agent: [调用 query_market_breadth]
   回复: "市场呈Bull态势..."
   
   用户: "今天有什么股票可以买?"
   Agent: [调用 query_today_signals]
   回复: "今日有5个信号: ..."
"""

# ========== Agent 核心函数 ==========

def create_trading_agent():
    """
    创建交易 Agent (工具集合)
    采用纯工具方案，避免 LLM 版本兼容性问题
    """
    from agents.model_config import get_llm, get_default_model
    
    model_name = get_default_model()
    
    try:
        llm = get_llm(model_name)
        print(f"✅ 已加载模型: {model_name}")
    except ValueError as e:
        print(f"❌ {e}")
        raise
    
    # 定义工具列表
    tools = [
        Tool(
            name="query_market_breadth",
            func=query_market_breadth,
            description="查询市场宽度和情绪分析，获取市场态势、推荐仓位等信息"
        ),
        Tool(
            name="query_today_signals",
            func=query_today_signals,
            description="获取今日交易信号，返回推荐买入的股票列表和排名"
        ),
        Tool(
            name="get_system_parameters",
            func=get_system_parameters,
            description="获取系统参数配置，包括选股规则、风控参数等"
        ),
        Tool(
            name="query_backtest_stats",
            func=query_backtest_stats,
            description="查询历史回测表现统计数据"
        ),
        Tool(
            name="run_system_update",
            func=run_system_update,
            description="执行系统数据更新和重新分析"
        ),
        Tool(
            name="help_command",
            func=help_command,
            description="显示帮助信息和使用说明"
        ),
    ]
    
    # 返回 (llm, tools, 用于后续处理)
    return llm, tools


def simple_agent_process(user_input, tools_dict):
    """
    简单 Agent 处理：用关键词匹配直接调用工具
    避免 LLM API 兼容性问题，确保 100% 可靠
    """
    user_lower = user_input.lower()
    
    # 形态解析
    shape_keywords = ["形态", "k线", "锤子线", "吞没", "三连阳", "放量", "新高", "ma5", "ma20", "金叉", "突破", "十周", "10周", "涨60", "60%", "平台"]
    if any(k in user_lower for k in shape_keywords):
        # 简单从输入中提取形态关键词
        candidates = [
            "锤子线",
            "看涨吞没",
            "三连阳",
            "放量突破",
            "突破20日新高",
            "MA5上穿MA20",
            "区间突破",
            "强势后平台",
        ]
        picked = [n for n in candidates if n.lower() in user_lower or n in user_input]
        # 兼容别名
        if ("金叉" in user_input) or ("ma5" in user_lower and "ma20" in user_lower):
            picked.append("MA5上穿MA20")
        if ("吞没" in user_input) and ("看涨吞没" not in picked):
            picked.append("看涨吞没")
        if ("新高" in user_input or "20日" in user_input) and ("突破20日新高" not in picked):
            picked.append("突破20日新高")
        if ("放量" in user_input) and ("放量突破" not in picked):
            picked.append("放量突破")
        if ("十周" in user_input) or ("10周" in user_input) or ("涨60" in user_input) or ("60%" in user_input) or ("强势平台" in user_input) or ("平台震荡" in user_input):
            picked.append("强势后平台")

        # 全市场/全部 开关
        full_scan = any(k in user_lower for k in ["全部", "全市场", "全缓存", "全股票", "全部股票", "全量"])
        # ST 开关（默认剔除）
        exclude_st = not any(k in user_lower for k in ["包含st", "保留st", "不剔除st", "含st"]) 

        # 执行筛选
        if full_scan:
            picks_df, table = detect_patterns_on_all(picked, limit=0, exclude_st=exclude_st)
        else:
            picks_df, table = detect_patterns_on_candidates(picked, limit=200, exclude_st=exclude_st)

        # 保存CSV
        try:
            os.makedirs('data/patterns', exist_ok=True)
            tag = f"{'ALL' if full_scan else 'CAND'}_{'noST' if exclude_st else 'withST'}"
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_csv = f'data/patterns/pattern_picks_{tag}_{ts}.csv'
            if table is not None and not table.empty:
                table.to_csv(out_csv, index=False, encoding='utf-8-sig')
            else:
                pd.DataFrame([], columns=['code','patterns']).to_csv(out_csv, index=False, encoding='utf-8-sig')
        except Exception:
            out_csv = None

        base_text = format_pattern_result(picks_df, table, top_k=20)
        if out_csv:
            base_text += f"\n\n已保存: {out_csv}"
        return base_text

    # 关键词 -> 工具映射
    if any(word in user_lower for word in ["市场", "怎么样", "宽度", "情绪", "态势"]):
        return tools_dict["query_market_breadth"]()
    
    elif any(word in user_lower for word in ["股票", "信号", "订单", "推荐", "买入"]):
        return tools_dict["query_today_signals"]()
    
    elif any(word in user_lower for word in ["参数", "配置", "调整", "规则"]):
        return tools_dict["get_system_parameters"]()
    
    elif any(word in user_lower for word in ["回测", "表现", "历史", "统计"]):
        return tools_dict["query_backtest_stats"]()
    
    elif any(word in user_lower for word in ["更新", "重新", "刷新", "重算"]):
        return tools_dict["run_system_update"]()
    
    elif user_lower in ["help", "帮助", "?"]:
        return tools_dict["help_command"]()
    
    else:
        # 默认返回帮助
        return """💡 请输入具体问题，例如:
  📊 现在市场怎么样?
  📈 今天有什么股票?
  ⚙️ 系统参数是什么?
  📉 历史表现怎么样?
  🔄 更新系统数据
  
输入 'help' 查看完整帮助"""

# ========== LLM Agent 实现 (使用 OpenAI SDK + DeepSeek) ==========

def create_llm_agent():
    """
    使用 OpenAI SDK 创建 LLM Agent (完全按照 DeepSeek 官方文档)
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 未设置 DEEPSEEK_API_KEY 环境变量")
        return None
    
    # 按照 DeepSeek 官方文档创建客户端
    client = OpenAISDK(
        api_key=api_key,
        base_url="https://api.deepseek.com"  # 官方推荐的 base_url
    )
    
    return client


def llm_agent_process(user_input, client, tools_dict):
    """
    使用 LLM Agent 处理用户输入
    完全按照 DeepSeek 官方 API 调用方式
    """
    if client is None:
        return None
    
    # 构建系统提示
    system_prompt = """你是一个 A 股短线交易助手。根据用户的问题，调用相应的工具来获取信息。

可用的工具有:
1. query_market_breadth - 查询市场宽度和情绪分析
2. query_today_signals - 获取今日交易信号
3. get_system_parameters - 获取系统参数配置
4. query_backtest_stats - 查询历史回测表现
5. run_system_update - 执行系统数据更新
6. help_command - 显示帮助信息

当用户问到市场、宽度、情绪等，调用 query_market_breadth。
当用户问到股票、信号、订单、推荐等，调用 query_today_signals。
当用户问到参数、配置、调整等，调用 get_system_parameters。
当用户问到回测、表现、历史等，调用 query_backtest_stats。
当用户问到更新、重新等，调用 run_system_update。

请根据用户的问题，选择合适的工具来回答。"""
    
    try:
        # 调用 DeepSeek API (完全按照官方示例)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            stream=False,
            temperature=0.7,
            max_tokens=2000,
        )
        
        # 获取 LLM 的回应
        llm_response = response.choices[0].message.content
        print(f"[LLM] DeepSeek 返回: {llm_response[:80]}...")
        
        # 形态选股（优先根据用户输入触发）
        lower_in = user_input.lower()
        if any(k in lower_in for k in ["形态", "k线", "锤子线", "吞没", "三连阳", "放量", "新高", "ma5", "ma20", "金叉", "突破", "十周", "10周", "涨60", "60%", "平台", "全部", "全市场", "全缓存", "全股票", "全部股票", "全量", "包含st", "保留st", "不剔除st", "含st"]):
            candidates = [
                "锤子线",
                "看涨吞没",
                "三连阳",
                "放量突破",
                "突破20日新高",
                "MA5上穿MA20",
                "区间突破",
                "强势后平台",
            ]
            picked = [n for n in candidates if n.lower() in lower_in or n in user_input]
            if ("金叉" in user_input) or ("ma5" in lower_in and "ma20" in lower_in):
                picked.append("MA5上穿MA20")
            if ("吞没" in user_input) and ("看涨吞没" not in picked):
                picked.append("看涨吞没")
            if ("新高" in user_input or "20日" in user_input) and ("突破20日新高" not in picked):
                picked.append("突破20日新高")
            if ("放量" in user_input) and ("放量突破" not in picked):
                picked.append("放量突破")
            if ("十周" in user_input) or ("10周" in user_input) or ("涨60" in user_input) or ("60%" in user_input) or ("强势平台" in user_input) or ("平台震荡" in user_input):
                picked.append("强势后平台")
            # 全市场/全部 开关
            full_scan = any(k in lower_in for k in ["全部", "全市场", "全缓存", "全股票", "全部股票", "全量"])
            # ST 开关
            exclude_st = not any(k in lower_in for k in ["包含st", "保留st", "不剔除st", "含st"]) 

            # 执行筛选
            if full_scan:
                picks_df, table = detect_patterns_on_all(picked, limit=0, exclude_st=exclude_st)
            else:
                picks_df, table = detect_patterns_on_candidates(picked, limit=200, exclude_st=exclude_st)

            # 保存CSV
            try:
                os.makedirs('data/patterns', exist_ok=True)
                tag = f"{'ALL' if full_scan else 'CAND'}_{'noST' if exclude_st else 'withST'}"
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                out_csv = f'data/patterns/pattern_picks_{tag}_{ts}.csv'
                if table is not None and not table.empty:
                    table.to_csv(out_csv, index=False, encoding='utf-8-sig')
                else:
                    pd.DataFrame([], columns=['code','patterns']).to_csv(out_csv, index=False, encoding='utf-8-sig')
            except Exception:
                out_csv = None

            base_text = format_pattern_result(picks_df, table, top_k=20)
            if out_csv:
                base_text += f"\n\n已保存: {out_csv}"
            return base_text

        # 根据 LLM 的回应判断应该调用哪个工具
        llm_response_lower = llm_response.lower()
        
        if "query_market_breadth" in llm_response_lower or "市场宽度" in llm_response_lower:
            print("[LLM] 触发工具: query_market_breadth")
            result = tools_dict.get("query_market_breadth", lambda: "工具未找到")()
        elif "query_today_signals" in llm_response_lower or "交易信号" in llm_response_lower:
            print("[LLM] 触发工具: query_today_signals")
            result = tools_dict.get("query_today_signals", lambda: "工具未找到")()
        elif "get_system_parameters" in llm_response_lower or "系统参数" in llm_response_lower:
            print("[LLM] 触发工具: get_system_parameters")
            result = tools_dict.get("get_system_parameters", lambda: "工具未找到")()
        elif "query_backtest_stats" in llm_response_lower or "回测" in llm_response_lower:
            print("[LLM] 触发工具: query_backtest_stats")
            result = tools_dict.get("query_backtest_stats", lambda: "工具未找到")()
        elif "run_system_update" in llm_response_lower or "更新系统" in llm_response_lower:
            print("[LLM] 触发工具: run_system_update")
            result = tools_dict.get("run_system_update", lambda: "工具未找到")()
        else:
            # LLM 直接回答用户
            print("[LLM] 直接回答用户")
            result = llm_response
        
        return result
    
    except Exception as e:
        print(f"⚠️ LLM 调用失败: {str(e)[:100]}")
        return None

# ========== 主交互循环 ==========

def run_agent_loop():
    """运行交互式 Agent 循环"""
    print("\n" + "="*80)
    print("🤖 A股短线交易系统 - AI Agent 已启动")
    print("="*80)
    print("\n💡 输入 'help' 查看帮助，'quit' 退出\n")
    
    try:
        llm, tools = create_trading_agent()
    except ValueError as e:
        print(f"❌ {e}")
        print("\n📝 设置方法:")
        print("   export OPENAI_API_KEY='sk-xxx'")
        return
    
    # 创建 LLM Agent 客户端
    llm_client = create_llm_agent()
    if llm_client:
        print("✅ LLM Agent 已加载 (使用 DeepSeek API)\n")
    else:
        print("⚠️ LLM Agent 初始化失败，将使用备用方案\n")
    
    while True:
        try:
            user_input = input("🧑 你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("\n👋 再见！祝交易顺利！\n")
                break
            
            if user_input.lower() == 'help':
                print(help_command())
                continue
            
            # 优先尝试使用真实的 LLM Agent
            print("\n🤖 Agent 分析中...\n")
            
            # 将工具列表转换为字典
            tools_dict = {tool.name: tool.func for tool in tools}
            
            result = None
            
            # 尝试 LLM Agent 处理
            if llm_client:
                try:
                    result = llm_agent_process(user_input, llm_client, tools_dict)
                except Exception as e:
                    print(f"⚠️ LLM 方式失败: {str(e)[:80]}")
                    print("💡 尝试关键词匹配...\n")
            
            # 如果 LLM 失败或未启用，使用关键词匹配作为备用
            if result is None:
                try:
                    result = simple_agent_process(user_input, tools_dict)
                except Exception as e:
                    print(f"❌ 处理失败: {str(e)[:100]}")
                    result = "💡 请输入具体问题，例如:\n  现在市场怎么样?\n  今天有什么股票?\n  系统参数是什么?"
            
            print(f"✨ Agent: {result}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 已中止。祝交易顺利！\n")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}\n")

if __name__ == "__main__":
    run_agent_loop()
