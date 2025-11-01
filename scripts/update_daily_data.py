#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 TuShare daily 接口更新最新的日线数据到 analyse_marketing 缓存
支持自动重试和动态延迟调整以应对API限流
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import tushare as ts
from datetime import datetime, timedelta
import time

# ========== 配置 ==========
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')
if not TUSHARE_TOKEN:
    print("❌ 错误: 未设置 TUSHARE_TOKEN 环境变量")
    print("   请运行: export TUSHARE_TOKEN='your_token'")
    sys.exit(1)

pro = ts.pro_api(TUSHARE_TOKEN)
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "analyse_marketing", "cache", "daily")
os.makedirs(CACHE_DIR, exist_ok=True)

print(f"📊 更新日线数据到最新")
print(f"   缓存目录: {CACHE_DIR}")

# ========== 1. 加载候选池 ==========
candidate_file = os.path.join(os.path.dirname(__file__), "..", "analyse_marketing", "out", "daily_candidates.csv")
if not os.path.exists(candidate_file):
    print(f"❌ 找不到候选池文件: {candidate_file}")
    print("   请先运行: cd analyse_marketing && python3 main.py --start 20250101 --export ./out --offline")
    sys.exit(1)

candidates_df = pd.read_csv(candidate_file)
candidate_codes = candidates_df['ts_code'].tolist()

print(f"✓ 加载候选池: {len(candidate_codes)} 个标的")

# ========== 2. 确定日期范围 ==========
end_date = datetime.today().strftime("%Y%m%d")
start_date = (datetime.today() - timedelta(days=365*3)).strftime("%Y%m%d")

print(f"✓ 日期范围: {start_date} ~ {end_date}")

# ========== 3. 更新每个标的的日线数据（带重试机制）==========
print(f"\n📥 开始更新日线数据...")
success_count = 0
fail_count = 0
failed_codes = []

for i, code in enumerate(candidate_codes, 1):
    retries = 0
    max_retries = 3
    delay = 0.5  # 初始延迟
    
    while retries < max_retries:
        try:
            # 获取数据
            df = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
            
            if df is None or len(df) == 0:
                fail_count += 1
                failed_codes.append(code)
                print(f"  ⚠️  [{i:3d}/{len(candidate_codes)}] {code}: 无数据")
                break
            
            # 重命名列以匹配标准格式
            df_std = df[['trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount']].copy()
            df_std.columns = ['trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
            df_std['trade_date'] = pd.to_datetime(df_std['trade_date'])
            df_std['pct_chg'] = df_std['close'].pct_change().fillna(0) * 100
            
            # 保存到 parquet
            cache_file = os.path.join(CACHE_DIR, f"{code}.parquet")
            df_std.to_parquet(cache_file, index=False)
            
            success_count += 1
            if i % 10 == 0:
                print(f"  ✓ 已更新 {i}/{len(candidate_codes)} 个标的...")
            
            # 成功后重置延迟
            delay = 0.5
            break
            
        except Exception as e:
            error_msg = str(e)
            retries += 1
            
            # 检查是否为限流错误
            if '每分钟最多访问' in error_msg or '访问频率过高' in error_msg:
                if retries < max_retries:
                    delay = min(delay * 2, 5.0)  # 指数增长延迟，最多5秒
                    print(f"  ⏳ [{i:3d}/{len(candidate_codes)}] {code}: API限流，{delay}秒后重试... (第{retries}次)")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  ❌ [{i:3d}/{len(candidate_codes)}] {code}: 重试{max_retries}次仍失败")
                    fail_count += 1
                    failed_codes.append(code)
                    break
            else:
                # 其他错误
                fail_count += 1
                failed_codes.append(code)
                print(f"  ⚠️  [{i:3d}/{len(candidate_codes)}] {code}: {error_msg[:40]}")
                break
    
    # 正常延迟（避免限流）
    if retries == 0:  # 成功的请求
        time.sleep(0.3)

print(f"\n✅ 更新完成!")
print(f"   成功: {success_count} / {len(candidate_codes)} 个")
print(f"   失败: {fail_count} / {len(candidate_codes)} 个")

if failed_codes:
    print(f"\n⚠️  失败的标的:")
    for code in failed_codes:
        print(f"   - {code}")
    
    print(f"\n💡 可以稍后重新运行脚本以重试失败的标的:")
    print(f"   TUSHARE_TOKEN='b09f3c651f9fa367d9861d845052e8b4bb461543980a2daad4fff9c7' python3 scripts/update_daily_data.py")

print(f"\n✨ 现在可以运行交易系统:")
print(f"   python3 scripts/run_with_analyse_marketing.py")
